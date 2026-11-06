"""WS4 - Range scheduling and road-closure rules. Owner: scheduling child session.

Contract:
  GET  /api/schedule/events?site=YTC&from=&to=   -> list[ScheduleEvent] (ATEC roles)
  POST /api/schedule/check   ProposedEvent       -> ScheduleCheck (ATEC roles; no write)
  POST /api/schedule/events  ProposedEvent       -> ScheduleEvent (g3, range_scheduler; 409 on hard conflict)
  GET  /api/schedule/closures?at=ISO             -> list[RoadClosure] active at that time
Python entry points used by WS2:
  check_event(ev: ProposedEvent) -> ScheduleCheck
  create_event(ev: ProposedEvent, request_id=None, recommendation_id=None) -> ScheduleEvent

Events returned by this router also carry `sdz`, `closures` and both closure-km figures so maps can draw them.
`closures` without `at` returns every scheduled closure.
"""
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from shapely.geometry import shape

from .. import refdata, sdz
from ..auth import ATEC_ROLES, require
from ..db import row, tx
from ..schemas import Conflict, ProposedEvent, RoadClosure, ScheduleCheck, ScheduleEvent

router = APIRouter(prefix="/api", tags=["scheduling"])

HARD_CONFLICTS = {"equipment", "personnel", "range_busy", "sdz_overlap"}
SCHEDULER_ROLES = ("g3", "range_scheduler")


class ScheduleEventDetail(ScheduleEvent):
    sdz: Optional[dict] = None
    closures: list[RoadClosure] = []
    closed_km_with_gates: float = 0
    closed_km_without_gates: float = 0


def _ts(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        raise HTTPException(422, f"Invalid timestamp: {value}")


def _overlaps(a: ProposedEvent, b: ProposedEvent) -> bool:
    return _ts(a.start) < _ts(b.end) and _ts(b.start) < _ts(a.end)


def _name(fid) -> str:
    f = refdata.feature(fid)
    return f["properties"]["name"] if f else str(fid)


def _validate(ev: ProposedEvent):
    def kind_of(fid):
        f = refdata.feature(fid)
        return f and f["properties"]["kind"]

    if _ts(ev.end) <= _ts(ev.start):
        raise HTTPException(422, "Event end must be after start")
    if kind_of(ev.range_complex_id) != "range_complex":
        raise HTTPException(422, f"Unknown range complex: {ev.range_complex_id}")
    if not sdz.weapon_class(ev.weapon_class):
        raise HTTPException(422, f"Unknown weapon class: {ev.weapon_class}")
    if ev.weapon_class != "none":
        if kind_of(ev.firing_point_id) != "firing_point":
            raise HTTPException(422, "A firing point is required for a weapon with a surface danger zone")
        if kind_of(ev.target_area_id) != "target_area":
            raise HTTPException(422, "A target area is required for a weapon with a surface danger zone")
    eq = {e["id"] for e in refdata.equipment()}
    ppl = {p["id"] for p in refdata.personnel()}
    unknown = [i for i in ev.equipment_ids if i not in eq] + [i for i in ev.personnel_ids if i not in ppl]
    if unknown:
        raise HTTPException(422, f"Unknown equipment/personnel: {', '.join(unknown)}")


def _geometry(ev: ProposedEvent):
    zone = sdz.event_sdz(ev.weapon_class, ev.firing_point_id, ev.target_area_id)
    return zone, sdz.closed_segments(zone)


def _closures(ev: ProposedEvent, segments) -> list[RoadClosure]:
    weapon = sdz.weapon_class(ev.weapon_class)["label"]
    return [RoadClosure(segment_id=f["id"], road=f["properties"]["road"], gate_from=f["properties"]["gate_from"],
                        gate_to=f["properties"]["gate_to"], length_km=f["properties"]["length_km"], start=ev.start,
                        end=ev.end, reason=f"{weapon} SDZ: {ev.title} ({_name(ev.firing_point_id)} -> "
                                           f"{_name(ev.target_area_id)})")
            for f in segments]


def _segment_label(f) -> str:
    p = f["properties"]
    return f"{p['road']} {_name(p['gate_from']) if p['gate_from'] else 'start'} -> " \
           f"{_name(p['gate_to']) if p['gate_to'] else 'end'}"


def _names(ids, catalog) -> str:
    by_id = {x["id"]: x["name"] for x in catalog}
    return ", ".join(by_id.get(i, i) for i in sorted(ids))


def find_conflicts(ev: ProposedEvent, zone, segments, others: list[ScheduleEvent]) -> list[Conflict]:
    """Conflicts between a proposed event (with its SDZ / closed segments) and time-overlapping events."""
    out: list[Conflict] = []
    my_rc = shape(refdata.feature(ev.range_complex_id)["geometry"])
    for o in others:
        if not _overlaps(ev, o):
            continue
        add = lambda kind, detail: out.append(Conflict(kind=kind, event_id=o.id, detail=f"{detail} (event #{o.id} {o.title})"))
        same_rc = o.range_complex_id == ev.range_complex_id
        if same_rc:
            add("range_busy", f"{_name(ev.range_complex_id)} is already scheduled")
        if shared := set(ev.equipment_ids) & set(o.equipment_ids):
            add("equipment", f"Equipment double-booked: {_names(shared, refdata.equipment())}")
        if shared := set(ev.personnel_ids) & set(o.personnel_ids):
            add("personnel", f"Personnel double-booked: {_names(shared, refdata.personnel())}")
        o_zone, o_segs = _geometry(o)
        o_rc = shape(refdata.feature(o.range_complex_id)["geometry"])
        if zone is not None and o_zone is not None and zone.intersects(o_zone):
            add("sdz_overlap", "Surface danger zone overlaps another event's SDZ")
        elif not same_rc and zone is not None and zone.intersects(o_rc):
            add("sdz_overlap", f"Surface danger zone covers {_name(o.range_complex_id)}")
        elif not same_rc and o_zone is not None and o_zone.intersects(my_rc):
            add("sdz_overlap", f"{_name(ev.range_complex_id)} lies inside another event's SDZ")
        if not same_rc:
            for f in segments:
                if shape(f["geometry"]).intersects(o_rc):
                    add("road_needed", f"{_name(o.range_complex_id)} is accessed via {_segment_label(f)}, closed by this event")
            for f in o_segs:
                if shape(f["geometry"]).intersects(my_rc):
                    add("road_needed", f"{_name(ev.range_complex_id)} is accessed via {_segment_label(f)}, closed by another event")
    return out


def _load_events(site: Optional[str] = None) -> list[ScheduleEvent]:
    with tx() as con:
        q, args = "SELECT * FROM schedule_events WHERE status != 'cancelled'", []
        if site:
            q, args = q + " AND site_code = ?", [site]
        rows = con.execute(q + " ORDER BY start, id", args).fetchall()
    return [ScheduleEvent(**row(r)) for r in rows]


def _detail(ev: ScheduleEvent) -> ScheduleEventDetail:
    zone, segments = _geometry(ev)
    with_gates, without = sdz.closure_km(segments)
    return ScheduleEventDetail(**ev.model_dump(), sdz=sdz.geojson(zone), closures=_closures(ev, segments),
                               closed_km_with_gates=with_gates, closed_km_without_gates=without)


def check_event(ev: ProposedEvent, exclude_event_id: Optional[int] = None) -> ScheduleCheck:
    """SDZ, gate-aware road closures and conflicts for a proposed event. Does not write."""
    _validate(ev)
    zone, segments = _geometry(ev)
    with_gates, without = sdz.closure_km(segments)
    others = [o for o in _load_events(ev.site_code) if o.id != exclude_event_id]
    return ScheduleCheck(sdz=sdz.geojson(zone), closures=_closures(ev, segments), closed_km_with_gates=with_gates,
                         closed_km_without_gates=without, conflicts=find_conflicts(ev, zone, segments, others))


def create_event(ev: ProposedEvent, request_id=None, recommendation_id=None) -> ScheduleEvent:
    """Insert a schedule event. Raises HTTPException(409, {message, conflicts, check}) on a hard conflict."""
    check = check_event(ev)
    hard = [c for c in check.conflicts if c.kind in HARD_CONFLICTS]
    if hard:
        raise HTTPException(409, {"message": f"{len(hard)} hard conflict(s); event not scheduled",
                                  "conflicts": [c.model_dump() for c in hard], "check": check.model_dump()})
    with tx() as con:
        cur = con.execute(
            "INSERT INTO schedule_events (site_code,range_complex_id,title,start,end,weapon_class,firing_point_id,"
            "target_area_id,equipment_ids,personnel_ids,request_id,recommendation_id,status) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'scheduled')",
            (ev.site_code, ev.range_complex_id, ev.title, ev.start, ev.end, ev.weapon_class, ev.firing_point_id,
             ev.target_area_id, json.dumps(ev.equipment_ids), json.dumps(ev.personnel_ids), request_id,
             recommendation_id))
        new_id = cur.lastrowid
    event = ScheduleEvent(**ev.model_dump(), id=new_id, request_id=request_id, recommendation_id=recommendation_id)
    return _detail(event)


@router.get("/schedule/events", response_model=list[ScheduleEventDetail], dependencies=[Depends(require(*ATEC_ROLES))])
def list_events(site: str = "YTC", from_: Optional[str] = Query(None, alias="from"), to: Optional[str] = None):
    events = _load_events(site)
    if from_:
        events = [e for e in events if _ts(e.end) > _ts(from_)]
    if to:
        events = [e for e in events if _ts(e.start) < _ts(to)]
    return [_detail(e) for e in events]


@router.post("/schedule/check", response_model=ScheduleCheck, dependencies=[Depends(require(*ATEC_ROLES))])
def post_check(ev: ProposedEvent):
    return check_event(ev)


@router.post("/schedule/events", response_model=ScheduleEventDetail, status_code=201,
             dependencies=[Depends(require(*SCHEDULER_ROLES))])
def post_event(ev: ProposedEvent):
    return create_event(ev)


@router.get("/schedule/closures", response_model=list[RoadClosure], dependencies=[Depends(require(*ATEC_ROLES))])
def closures(at: Optional[str] = None, site: str = "YTC"):
    events = _load_events(site)
    if at:
        t = _ts(at)
        events = [e for e in events if _ts(e.start) <= t < _ts(e.end)]
    return [c for e in events for c in _closures(e, _geometry(e)[1])]
