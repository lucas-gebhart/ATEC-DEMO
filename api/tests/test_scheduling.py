import os

os.environ.setdefault("ATEC_DB", "/tmp/atec_test.db")

import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from shapely.geometry import Point, shape  # noqa: E402

from app import refdata, sdz  # noqa: E402
from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import scheduling  # noqa: E402
from app.schemas import ProposedEvent, ScheduleEvent  # noqa: E402

c = TestClient(app)
G3 = {"Authorization": "Bearer g3.planner"}
SCHED = {"Authorization": "Bearer ytc.scheduler"}
VIEWER = {"Authorization": "Bearer atec.hq"}
INDUSTRY = {"Authorization": "Bearer acme.industry"}
US95 = "US Hwy 95"


@pytest.fixture(autouse=True)
def fresh_db():
    init_db(reset=True)
    yield
    init_db(reset=True)


def shoot(**kw):
    """The seeded 155mm event shape, moved to a free day with fresh resources unless overridden."""
    base = dict(range_complex_id="rc-kofa", title="155mm demo shoot", start="2026-12-15T07:00:00",
                end="2026-12-15T15:00:00", weapon_class="155mm_howitzer", firing_point_id="fp-k1",
                target_area_id="ta-k-north", equipment_ids=[], personnel_ids=[])
    return {**base, **kw}


SEEDED_TIME = dict(start="2026-12-08T08:00:00", end="2026-12-08T12:00:00")


# --- sdz.py geometry -------------------------------------------------------------------------

def test_projection_round_trip_and_scale():
    p = Point(-114.3, 33.1)
    back = sdz.to_lonlat(sdz.to_km(p))
    assert abs(back.x - p.x) < 1e-9 and abs(back.y - p.y) < 1e-9
    one_deg_lat = sdz.to_km(Point(-114.2, 34.0)).y - sdz.to_km(Point(-114.2, 33.0)).y
    assert 110.5 < one_deg_lat < 111.5


def test_sdz_fan_points_at_target_and_respects_max_range():
    w = sdz.weapon_class("155mm_howitzer")
    fp, ta = Point(0, 0), Point(10, 0).buffer(2)
    zone = sdz.sdz_km(fp, ta, w)
    assert zone.contains(Point(5, 0)) and zone.contains(ta)
    assert not zone.contains(Point(-1, 0)) and not zone.contains(Point(5, 3))
    far = sdz.sdz_km(fp, Point(100, 0).buffer(2), w)
    fan_only = far.difference(Point(100, 0).buffer(2 + sdz.TARGET_BUFFER_KM + 0.1))
    assert fp.hausdorff_distance(fan_only) <= w["max_range_km"] + 1e-6


def test_no_sdz_for_weapon_class_none():
    assert sdz.sdz_km(Point(0, 0), Point(10, 0).buffer(1), sdz.weapon_class("none")) is None
    assert sdz.event_sdz("none", "fp-k1", "ta-k-north") is None
    assert sdz.closed_segments(None) == []
    assert sdz.closure_km([]) == (0, 0)


def test_155mm_from_fp_k1_closes_only_us95_between_gates():
    zone = sdz.event_sdz("155mm_howitzer", "fp-k1", "ta-k-north")
    assert zone.intersects(shape(refdata.feature("fp-k1")["geometry"]))
    assert zone.contains(shape(refdata.feature("ta-k-north")["geometry"]))
    segs = sdz.closed_segments(zone)
    assert segs and {f["properties"]["road"] for f in segs} == {US95}
    assert all(f["properties"]["gate_from"] and f["properties"]["gate_to"] for f in segs)
    with_gates, without = sdz.closure_km(segs)
    us95_total = sum(f["properties"]["length_km"] for f in refdata.features("road_segment") if f["properties"]["road"] == US95)
    assert 0 < with_gates < without == round(us95_total, 2)


# --- check endpoint ---------------------------------------------------------------------------

def test_check_155mm_partial_closure_with_sdz_geojson():
    r = c.post("/api/schedule/check", json=shoot(), headers=VIEWER)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sdz"]["type"] in ("Polygon", "MultiPolygon") and body["sdz"]["coordinates"]
    assert body["closures"] and all(cl["road"] == US95 for cl in body["closures"])
    assert {cl["segment_id"] for cl in body["closures"]} == {"seg-us-hwy-95-5"}
    cl = body["closures"][0]
    assert (cl["gate_from"], cl["gate_to"]) == ("gate-us-hwy-95-4", "gate-us-hwy-95-5")
    assert cl["start"] == shoot()["start"] and "155mm" in cl["reason"]
    assert 0 < body["closed_km_with_gates"] < body["closed_km_without_gates"]
    assert body["closed_km_with_gates"] == pytest.approx(sum(x["length_km"] for x in body["closures"]))
    assert body["conflicts"] == []


def test_check_no_sdz_event_closes_nothing():
    ev = dict(range_complex_id="rc-ncties", title="Route clearance", start="2026-12-15T07:00:00",
              end="2026-12-15T12:00:00", weapon_class="none", equipment_ids=["eq-blast-1"])
    body = c.post("/api/schedule/check", json=ev, headers=G3).json()
    assert body["sdz"] is None and body["closures"] == []
    assert body["closed_km_with_gates"] == 0 and body["closed_km_without_gates"] == 0


def test_check_conflicts_when_reusing_seeded_gun_and_crew():
    ev = shoot(equipment_ids=["eq-m777-1"], personnel_ids=["p-ruiz", "p-hale"], **SEEDED_TIME)
    kinds = {x["kind"] for x in c.post("/api/schedule/check", json=ev, headers=G3).json()["conflicts"]}
    assert {"equipment", "personnel", "range_busy", "sdz_overlap"} <= kinds


def test_equipment_and_personnel_conflicts_on_another_range():
    ev = dict(range_complex_id="rc-laguna", title="UAS sortie", weapon_class="none",
              equipment_ids=["eq-dyno-1"], personnel_ids=["p-okafor"], start="2026-12-09T09:00:00",
              end="2026-12-09T10:00:00")
    conflicts = c.post("/api/schedule/check", json=ev, headers=G3).json()["conflicts"]
    assert {x["kind"] for x in conflicts} == {"equipment", "personnel"}
    assert "Chassis Dynamometer" in next(x["detail"] for x in conflicts if x["kind"] == "equipment")
    assert "J. Okafor" in next(x["detail"] for x in conflicts if x["kind"] == "personnel")


def test_range_busy_same_range_complex():
    ev = dict(range_complex_id="rc-dz", title="Cargo drop", weapon_class="none", start="2026-12-09T11:00:00",
              end="2026-12-09T13:00:00")
    conflicts = c.post("/api/schedule/check", json=ev, headers=G3).json()["conflicts"]
    assert [(x["kind"], x["event_id"]) for x in conflicts] == [("range_busy", 3)]


def test_sdz_covering_another_range_complex_is_hard_conflict():
    c.post("/api/schedule/events", json=dict(range_complex_id="rc-castle-dome", title="Solar soak", weapon_class="none",
                                             start="2026-12-15T06:00:00", end="2026-12-15T18:00:00"), headers=SCHED)
    conflicts = c.post("/api/schedule/check", json=shoot(), headers=G3).json()["conflicts"]
    assert [x["kind"] for x in conflicts] == ["sdz_overlap"]
    assert "Castle Dome Annex" in conflicts[0]["detail"]


def test_non_overlapping_times_produce_no_conflicts():
    ev = shoot(equipment_ids=["eq-m777-1", "eq-radar-1"], personnel_ids=["p-ruiz", "p-hale"],
               start="2026-12-08T15:00:00", end="2026-12-08T20:00:00")
    assert c.post("/api/schedule/check", json=ev, headers=G3).json()["conflicts"] == []


def test_road_needed_when_closed_segment_touches_other_range():
    # Mobility courses border US-95 segment 2; force the proposed shoot to close it.
    seg2 = refdata.feature("seg-us-hwy-95-2")
    ev = ProposedEvent(**shoot(range_complex_id="rc-castle-dome", start="2026-12-09T08:00:00", end="2026-12-09T12:00:00"))
    zone = sdz.event_sdz(ev.weapon_class, ev.firing_point_id, ev.target_area_id)
    mobility = ScheduleEvent(id=99, range_complex_id="rc-mobility", title="Durability lap", weapon_class="none",
                             start="2026-12-09T06:00:00", end="2026-12-09T18:00:00")
    conflicts = scheduling.find_conflicts(ev, zone, [seg2], [mobility])
    assert [x.kind for x in conflicts] == ["road_needed"]
    assert "Mobility Test Courses" in conflicts[0].detail and "US Hwy 95" in conflicts[0].detail
    assert "road_needed" not in scheduling.HARD_CONFLICTS


def test_check_validation_errors():
    assert c.post("/api/schedule/check", json=shoot(firing_point_id=None), headers=G3).status_code == 422
    assert c.post("/api/schedule/check", json=shoot(weapon_class="railgun"), headers=G3).status_code == 422
    assert c.post("/api/schedule/check", json=shoot(range_complex_id="rc-nope"), headers=G3).status_code == 422
    assert c.post("/api/schedule/check", json=shoot(end="2026-12-15T06:00:00"), headers=G3).status_code == 422
    assert c.post("/api/schedule/check", json=shoot(equipment_ids=["eq-nope"]), headers=G3).status_code == 422


# --- create / list / closures ---------------------------------------------------------------

def test_create_event_and_list_with_geometry():
    r = c.post("/api/schedule/events", json=shoot(equipment_ids=["eq-m777-1"]), headers=SCHED)
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["id"] > 3 and created["status"] == "scheduled" and created["sdz"]
    assert created["closed_km_with_gates"] < created["closed_km_without_gates"]
    events = c.get("/api/schedule/events?site=YTC", headers=VIEWER).json()
    assert [e["id"] for e in events][-1] == created["id"] and len(events) == 4
    seeded = next(e for e in events if e["id"] == 1)
    assert seeded["sdz"] and seeded["closures"][0]["segment_id"] == "seg-us-hwy-95-5"
    assert next(e for e in events if e["id"] == 2)["sdz"] is None


def test_list_events_time_filter():
    ids = [e["id"] for e in c.get("/api/schedule/events?from=2026-12-09T00:00:00&to=2026-12-09T23:00:00", headers=G3).json()]
    assert ids == [2, 3]


def test_create_event_hard_conflict_returns_409():
    r = c.post("/api/schedule/events", json=shoot(equipment_ids=["eq-m777-1"], **SEEDED_TIME), headers=G3)
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert {x["kind"] for x in detail["conflicts"]} >= {"equipment", "range_busy"}
    assert detail["check"]["closures"]
    assert len(c.get("/api/schedule/events", headers=G3).json()) == 3


def test_python_entry_points_for_planning():
    check = scheduling.check_event(ProposedEvent(**shoot()))
    assert check.closed_km_with_gates < check.closed_km_without_gates
    ev = scheduling.create_event(ProposedEvent(**shoot()), request_id=7, recommendation_id=11)
    assert isinstance(ev, ScheduleEvent) and ev.request_id == 7 and ev.recommendation_id == 11
    with pytest.raises(HTTPException) as e:
        scheduling.create_event(ProposedEvent(**shoot()))
    assert e.value.status_code == 409


def test_closures_active_at_time():
    at = lambda t: c.get(f"/api/schedule/closures?at={t}", headers=VIEWER).json()
    during = at("2026-12-08T10:00:00")
    assert [x["segment_id"] for x in during] == ["seg-us-hwy-95-5"] and during[0]["road"] == US95
    assert at("2026-12-08T16:00:00") == []
    assert at("2026-12-08T15:00:00") == []
    assert len(c.get("/api/schedule/closures", headers=VIEWER).json()) == 1


def test_roles():
    assert c.get("/api/schedule/events", headers=INDUSTRY).status_code == 403
    assert c.post("/api/schedule/check", json=shoot(), headers=INDUSTRY).status_code == 403
    assert c.post("/api/schedule/events", json=shoot(), headers=VIEWER).status_code == 403
    assert c.get("/api/schedule/closures").status_code == 401
