"""Deterministic rules-based planner: test request -> RecommendationPayload.

Ranks ATEC sites and YTC range complexes by test-function coverage, picks YTC equipment and crew that
cover the requested functions, finds a free weekday window inside the requested dates and, for
indirect fire, a weapon class, firing point and target area within range."""
import math
from datetime import date, datetime, timedelta

from shapely.geometry import LineString, Point, Polygon, shape

from . import refdata
from .db import row, tx
from .schemas import ProposedEvent, RecommendationPayload

DETAIL_SITE = "YTC"
DAY_START, DAY_END = "07:00:00", "15:00:00"
SEARCH_DAYS = 45
HAZARDOUS = {"live_fire_indirect", "live_fire_direct", "missile_flight", "munitions_lethality",
             "fuze_performance", "c_ied", "mine_countermine", "survivability", "aircraft_armament"}
SDZ_FUNCTIONS = {"live_fire_indirect", "munitions_lethality", "fuze_performance"}
LEAD_ROLES = ("Test Director", "Test Officer", "Airdrop Test Officer")
WEAPON_HINTS = [("105", "105mm_howitzer"), ("mortar", "120mm_mortar"), ("120mm", "120mm_mortar"),
                ("gmlrs", "gmlrs"), ("rocket", "gmlrs"), ("155", "155mm_howitzer")]


def _label(code):
    return next((t["label"] for t in refdata.taxonomy()["test_functions"] if t["code"] == code), code)


def _labels(codes):
    return ", ".join(_label(c) for c in sorted(codes))


def _weapon(code):
    return next(w for w in refdata.taxonomy()["weapon_classes"] if w["code"] == code)


def _site(code):
    return next(s for s in refdata.sites() if s["code"] == code)


def _name(fid):
    f = refdata.feature(fid)
    return f["properties"]["name"] if f else fid


def _km(a: Point, b: Point) -> float:
    return math.hypot((a.x - b.x) * 111.32 * math.cos(math.radians((a.y + b.y) / 2)), (a.y - b.y) * 110.57)


def _events():
    with tx() as con:
        return [row(r) for r in con.execute("SELECT * FROM schedule_events WHERE status != 'cancelled'")]


def _overlaps(ev, start, end):
    return ev["start"] < end and start < ev["end"]


def _parse_day(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "")).date()
    except ValueError:
        return None


def _candidates(funcs):
    """(site, range complex) candidates with coverage; YTC range complexes are scheduled in detail."""
    out = []
    for rc in refdata.features("range_complex"):
        p = rc["properties"]
        if p["range_type"] == "impact_area":
            continue
        cov = funcs & set(p["test_functions"])
        if cov:
            out.append({"site_code": DETAIL_SITE, "range_complex_id": rc["id"], "range_name": p["name"], "covered": cov})
    for s in refdata.sites():
        cov = funcs & set(s["test_functions"])
        if s["code"] != DETAIL_SITE and cov:
            out.append({"site_code": s["code"], "range_complex_id": f"{s['code'].lower()}-site",
                        "range_name": f"{s['name']} (site-level)", "covered": cov})
    # Full coverage first, then YTC detail over site-level, then breadth.
    out.sort(key=lambda c: (-len(c["covered"]), c["site_code"] != DETAIL_SITE, c["range_complex_id"]))
    return out


def _cover(pool, funcs, key, prefer):
    """Greedy set cover of funcs over pool[key]; ties broken by prefer(item) (lower is better)."""
    chosen, left = [], set(funcs)
    while left:
        best = min(pool, key=lambda x: (-len(left & set(x[key])), prefer(x)), default=None)
        if not best or not left & set(best[key]):
            break
        chosen.append(best)
        left -= set(best[key])
        pool = [x for x in pool if x is not best]
    return chosen, left


def _pick_equipment(funcs, rc_id):
    """Cover the functions within each equipment category (e.g. a gun AND instrumentation)."""
    site_eq = [e for e in refdata.equipment() if e["site_code"] == DETAIL_SITE and funcs & set(e["supports_functions"])]
    prefer = lambda e: (0 if e["range_complex_id"] == rc_id else 1 if e["range_complex_id"] is None else 2, e["id"])  # noqa: E731
    chosen, covered = [], set()
    for cat in sorted({e["category"] for e in site_eq}):
        picked, _ = _cover([e for e in site_eq if e["category"] == cat], funcs, "supports_functions", prefer)
        chosen += picked
        covered |= {f for e in picked for f in e["supports_functions"]}
    return chosen, funcs - covered


def _pick_personnel(funcs):
    staff = [p for p in refdata.personnel() if p["site_code"] == DETAIL_SITE and p["qualifications"]]
    leads, left = _cover([p for p in staff if p["role"] in LEAD_ROLES], funcs, "qualifications",
                         lambda p: (LEAD_ROLES.index(p["role"]), p["id"]))
    support, left = _cover([p for p in staff if p["role"] not in LEAD_ROLES + ("Range Safety Officer",)],
                           left, "qualifications", lambda p: p["id"])
    crew = leads + support
    rso = None
    if funcs & HAZARDOUS:
        rso = next((p for p in staff if p["role"] == "Range Safety Officer" and funcs & set(p["qualifications"])), None)
        if rso:
            crew.append(rso)
            left -= set(rso["qualifications"])
    return crew, left, rso


def _weapon_class(req, equipment_ids):
    text = f"{req.get('system_name', '')} {req.get('description', '')}".lower()
    for hint, code in WEAPON_HINTS:
        if hint in text:
            return code
    if req["mission_area"] == "missile":
        return "gmlrs"
    return "155mm_howitzer" if "eq-m777-1" in equipment_ids or req["mission_area"] == "artillery" else "none"


def _wedge(fp: Point, ta: Point, weapon):
    """Approximate surface danger zone wedge (WS4 owns the authoritative SDZ)."""
    bearing = math.atan2(ta.y - fp.y, (ta.x - fp.x) * math.cos(math.radians(fp.y)))
    half = math.radians(weapon["sdz_half_angle_deg"])
    reach = _km(fp, ta) + 2
    pts = [(fp.x, fp.y)]
    for i in range(9):
        a = bearing - half + 2 * half * i / 8
        pts.append((fp.x + reach * math.cos(a) / (111.32 * math.cos(math.radians(fp.y))), fp.y + reach * math.sin(a) / 110.57))
    return Polygon(pts)


def _pick_firing(rc_id, weapon, start, end, events):
    """In-range (firing point, target area) pair, free in the window, fewest road segments under the SDZ."""
    fps = [f for f in refdata.features("firing_point") if f["properties"]["range_complex_id"] == rc_id]
    tas = refdata.features("target_area")
    segs = refdata.features("road_segment")
    busy = {e.get("firing_point_id") for e in events if _overlaps(e, start, end)} | \
           {e.get("target_area_id") for e in events if _overlaps(e, start, end)}
    best = None
    for fp in fps:
        for ta in tas:
            p, c = shape(fp["geometry"]), shape(ta["geometry"]).centroid
            dist = _km(p, c)
            if dist > weapon["max_range_km"]:
                continue
            sdz = _wedge(p, c, weapon)
            hit = [s for s in segs if sdz.intersects(shape(s["geometry"]))]
            key = (fp["id"] in busy or ta["id"] in busy, len(hit), dist)
            if best is None or key < best[0]:
                best = (key, fp["id"], ta["id"], dist, hit)
    return best


def _window(req, rc_id, equipment_ids, personnel_ids, events):
    today = date.today()
    lo = max(_parse_day(req.get("desired_start")) or today + timedelta(days=1), today + timedelta(days=1))
    hi = _parse_day(req.get("desired_end")) or lo + timedelta(days=SEARCH_DAYS)
    first = None
    d = lo
    while d <= max(hi, lo):
        if d.weekday() < 5:
            start, end = f"{d}T{DAY_START}", f"{d}T{DAY_END}"
            first = first or (start, end)
            clash = [e for e in events if _overlaps(e, start, end) and (
                e["range_complex_id"] == rc_id or set(e["equipment_ids"]) & set(equipment_ids)
                or set(e["personnel_ids"]) & set(personnel_ids))]
            if not clash:
                return start, end, True
        d += timedelta(days=1)
    if first is None:
        d = lo
        while d.weekday() >= 5:
            d += timedelta(days=1)
        first = (f"{d}T{DAY_START}", f"{d}T{DAY_END}")
    return first[0], first[1], False


def _check(payload: RecommendationPayload, title: str):
    """Attach WS4's schedule check when available; degrade gracefully while it is a stub."""
    from .routers import scheduling
    fn = getattr(scheduling, "check_event", None)
    if fn is None or payload.site_code != DETAIL_SITE:
        return None
    try:
        return fn(to_event(payload, title))
    except NotImplementedError:
        return None


def to_event(payload: RecommendationPayload, title: str) -> ProposedEvent:
    return ProposedEvent(site_code=payload.site_code, range_complex_id=payload.range_complex_id, title=title,
                         start=payload.proposed_start, end=payload.proposed_end, weapon_class=payload.weapon_class,
                         firing_point_id=payload.firing_point_id, target_area_id=payload.target_area_id,
                         equipment_ids=payload.equipment_ids, personnel_ids=payload.personnel_ids)


def event_title(req) -> str:
    return f"{req['system_name']} ({req.get('company_uei', '')})".replace(" ()", "")


def attach_schedule_check(payload: RecommendationPayload, req) -> RecommendationPayload:
    payload.risks = [r for r in payload.risks if not r.startswith("Schedule conflict")]
    check = _check(payload, event_title(req))
    if check is not None:
        payload.schedule_check = check
        for c in check.conflicts:
            payload.risks.append(f"Schedule conflict ({c.kind.replace('_', ' ')}): {c.detail}")
    return payload


def recommend(req: dict) -> RecommendationPayload:
    funcs = set(req["test_functions"])
    cands = _candidates(funcs)
    if not cands:
        raise ValueError("No ATEC site supports the requested test functions")
    primary = cands[0]
    events = _events()
    reasoning, risks = [], []

    site = _site(primary["site_code"])
    site_cov = funcs & set(site["test_functions"])
    reasoning.append(f"{site['name']} supports {len(site_cov)} of {len(funcs)} requested test functions ({_labels(site_cov)}).")
    rc_cov = primary["covered"]
    if primary["site_code"] == DETAIL_SITE:
        reasoning.append(f"{primary['range_name']} is rated for {_labels(rc_cov)}.")
    if funcs - rc_cov:
        risks.append(f"Coverage gap at {primary['range_name']}: {_labels(funcs - rc_cov)}.")

    equipment, personnel, eq_gap, crew_gap, rso = [], [], set(), set(), None
    if primary["site_code"] == DETAIL_SITE:
        equipment, eq_gap = _pick_equipment(funcs, primary["range_complex_id"])
        personnel, crew_gap, rso = _pick_personnel(funcs)
        for e in equipment:
            where = (f"stationed at {_name(e['range_complex_id'])}" if e["range_complex_id"] else "mobile asset")
            reasoning.append(f"{e['name']} ({where}) supports {_labels(funcs & set(e['supports_functions']))}.")
            if e["range_complex_id"] not in (None, primary["range_complex_id"]):
                risks.append(f"{e['name']} must be relocated from {_name(e['range_complex_id'])}.")
        for p in personnel:
            reasoning.append(f"{p['name']} ({p['role']}) is qualified for {_labels(funcs & set(p['qualifications']))}.")
        if eq_gap:
            risks.append(f"No YTC equipment listed for {_labels(eq_gap)}; customer may need to provide instrumentation.")
        if crew_gap:
            risks.append(f"No qualified YTC crew for {_labels(crew_gap)}.")
        if funcs & HAZARDOUS:
            risks.append(f"Hazardous test ({_labels(funcs & HAZARDOUS)}): a Range Safety Officer must be on range"
                         + (f" ({rso['name']} assigned)." if rso else " - none qualified at YTC, request one."))
    else:
        risks.append(f"{site['name']} has no detailed range, equipment or crew data in this demo; coordinate with the site.")

    eq_ids, crew_ids = [e["id"] for e in equipment], [p["id"] for p in personnel]
    start, end, free = _window(req, primary["range_complex_id"], eq_ids, crew_ids, events)
    if free:
        reasoning.append(f"{start[:10]} {DAY_START[:5]}-{DAY_END[:5]} is the first weekday in the requested window "
                         "with the range, equipment and crew free.")
    else:
        risks.append(f"No conflict-free weekday found in the requested window; proposing {start[:10]} - deconflict before approval.")
    if req.get("desired_end") and _parse_day(req["desired_end"]) and start[:10] > req["desired_end"][:10]:
        risks.append("Proposed date falls after the requested end date.")

    weapon_class, fp_id, ta_id = "none", None, None
    if funcs & SDZ_FUNCTIONS and primary["range_complex_id"] == "rc-kofa":
        weapon_class = _weapon_class(req, eq_ids)
        weapon = _weapon(weapon_class)
        pick = _pick_firing(primary["range_complex_id"], weapon, start, end, events)
        if pick:
            (busy, _, _), fp_id, ta_id, dist, hit = pick
            reasoning.append(f"{weapon['label']} from {_name(fp_id)} to {_name(ta_id)}: {dist:.1f} km, within "
                             f"{weapon['max_range_km']} km max range.")
            if busy:
                risks.append(f"{_name(fp_id)} or {_name(ta_id)} is already in use during the proposed window.")
            if hit:
                roads = sorted({s["properties"]["road"] for s in hit})
                km = sum(s["properties"]["length_km"] for s in hit)
                risks.append(f"Estimated danger zone crosses {', '.join(roads)} ({len(hit)} gated segment(s), "
                             f"{km:.1f} km); road closure between gates required during firing.")
            else:
                reasoning.append("Estimated danger zone clears public roads (US-95, Castle Dome Mine Rd, Cibola Rd).")
        else:
            risks.append(f"No firing point / target area pair within {weapon['max_range_km']} km for {weapon['label']}.")

    eq_cov = 1 - len(eq_gap) / len(funcs) if primary["site_code"] == DETAIL_SITE else 0
    crew_cov = 1 - len(crew_gap) / len(funcs) if primary["site_code"] == DETAIL_SITE else 0
    score = 0.5 * len(rc_cov) / len(funcs) + 0.25 * eq_cov + 0.25 * crew_cov - (0 if free else 0.1)

    alternatives = []
    for c in cands[1:]:
        if len(alternatives) == 2:
            break
        alternatives.append({"site_code": c["site_code"], "site_name": _site(c["site_code"])["name"],
                             "range_complex_id": c["range_complex_id"], "range_name": c["range_name"],
                             "coverage": round(len(c["covered"]) / len(funcs), 2),
                             "note": f"Covers {_labels(c['covered'])}"
                                     + (f"; missing {_labels(funcs - c['covered'])}" if funcs - c["covered"] else "")})

    payload = RecommendationPayload(
        site_code=primary["site_code"], range_complex_id=primary["range_complex_id"], proposed_start=start,
        proposed_end=end, equipment_ids=eq_ids, personnel_ids=crew_ids, weapon_class=weapon_class,
        firing_point_id=fp_id, target_area_id=ta_id, score=round(max(score, 0), 2), reasoning=reasoning,
        risks=risks, alternatives=alternatives)
    return attach_schedule_check(payload, req)
