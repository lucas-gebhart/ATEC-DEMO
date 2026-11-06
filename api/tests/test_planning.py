import json
import os

os.environ.setdefault("ATEC_DB", "/tmp/atec_test.db")

import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import devin_client, matcher  # noqa: E402
from app.db import init_db, row, tx  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import planning, scheduling  # noqa: E402
from app.schemas import ScheduleCheck, RoadClosure  # noqa: E402

init_db(reset=True)
c = TestClient(app)
G3 = {"Authorization": "Bearer g3.planner"}

ARTILLERY = dict(system_name="XM1113 155mm extended-range projectile", mission_area="artillery",
                 test_functions=["live_fire_indirect", "fuze_performance", "munitions_lethality"],
                 description="Fuze function and terminal lethality, 155mm", desired_start="2026-12-07",
                 desired_end="2026-12-18")


def make_request(**kw):
    r = {**ARTILLERY, **kw}
    with tx() as con:
        cur = con.execute(
            "INSERT INTO test_requests (company_uei,system_name,mission_area,test_functions,description,"
            "desired_start,desired_end) VALUES (?,?,?,?,?,?,?)",
            ("ACME12345XYZ", r["system_name"], r["mission_area"], json.dumps(r["test_functions"]),
             r["description"], r.get("desired_start"), r.get("desired_end")))
        return cur.lastrowid


def request_row(rid):
    with tx() as con:
        return row(con.execute("SELECT * FROM test_requests WHERE id=?", (rid,)).fetchone())


def test_matcher_artillery_kofa():
    p = matcher.recommend({**ARTILLERY, "id": 0})
    assert (p.site_code, p.range_complex_id, p.weapon_class) == ("YTC", "rc-kofa", "155mm_howitzer")
    assert set(p.equipment_ids) == {"eq-m777-1", "eq-radar-1"}
    assert set(p.personnel_ids) == {"p-ruiz", "p-hale"}
    assert p.firing_point_id.startswith("fp-k") and p.target_area_id.startswith("ta-k")
    assert "2026-12-07" <= p.proposed_start[:10] <= "2026-12-18"
    assert p.proposed_start.endswith("07:00:00") and p.proposed_end.endswith("15:00:00")
    assert p.score == 1.0 and p.reasoning
    assert any("Range Safety Officer" in r for r in p.risks)
    assert len(p.alternatives) <= 2


def test_matcher_avoids_busy_day():
    # Seeded 155mm event occupies rc-kofa, Ruiz and Hale on 2026-12-08.
    p = matcher.recommend({**ARTILLERY, "desired_start": "2026-12-08", "desired_end": "2026-12-10"})
    assert p.proposed_start[:10] == "2026-12-09"


def test_matcher_other_mission_areas():
    uas = matcher.recommend({"system_name": "Quadcopter", "mission_area": "uas", "description": "",
                             "test_functions": ["uas_flight", "target_acquisition"]})
    assert uas.range_complex_id == "rc-cibola" and "p-chen" in uas.personnel_ids and uas.weapon_class == "none"
    assert uas.firing_point_id is None
    cold = matcher.recommend({"system_name": "Boot", "mission_area": "soldier_systems", "description": "",
                              "test_functions": ["environmental_cold"]})
    assert cold.site_code == "CRTC" and not cold.equipment_ids


def test_matcher_attaches_schedule_check(monkeypatch):
    closure = RoadClosure(segment_id="seg-us-hwy-95-5", road="US Hwy 95", length_km=5.43,
                          start="2026-12-07T07:00:00", end="2026-12-07T15:00:00", reason="SDZ")
    monkeypatch.setattr(scheduling, "check_event", lambda ev: ScheduleCheck(closures=[closure], closed_km_with_gates=5.43,
                                                                            closed_km_without_gates=44.7), raising=False)
    p = matcher.recommend(ARTILLERY)
    assert p.schedule_check.closures[0].segment_id == "seg-us-hwy-95-5"


def test_plan_queue_and_get(monkeypatch):
    monkeypatch.setattr(devin_client, "enabled", lambda: False)
    rid = make_request()
    rec_id = planning.start_planning(rid)
    assert request_row(rid)["status"] == "in_review"
    rec = c.get(f"/api/recommendations/{rec_id}", headers=G3).json()
    assert rec["source"] == "rules" and rec["status"] == "draft" and rec["payload"]["range_complex_id"] == "rc-kofa"
    item = next(i for i in c.get("/api/g3/queue", headers=G3).json() if i["request"]["id"] == rid)
    assert item["company"]["cage"] == "7ACM1" and item["recommendation"]["id"] == rec_id
    replanned = c.post(f"/api/requests/{rid}/plan", headers=G3).json()
    assert replanned["id"] > rec_id


def test_roles():
    ind = {"Authorization": "Bearer acme.industry"}
    assert c.get("/api/g3/queue", headers=ind).status_code == 403
    assert c.get("/api/g3/queue", headers={"Authorization": "Bearer ytc.scheduler"}).status_code == 403
    assert c.post("/api/recommendations/1/decision", headers=ind, json={"decision": "reject", "note": "x"}).status_code == 403


def test_approve_without_scheduler_leaves_approved(monkeypatch):
    def stub(ev, request_id=None, recommendation_id=None):
        raise NotImplementedError
    monkeypatch.setattr(scheduling, "create_event", stub, raising=False)
    rid = make_request()
    rec_id = planning.start_planning(rid)
    r = c.post(f"/api/recommendations/{rec_id}/decision", headers=G3, json={"decision": "approve", "note": "ok"})
    assert r.status_code == 200 and r.json()["status"] == "approved" and r.json()["reviewer"] == "g3.planner"
    assert request_row(rid)["status"] == "approved"
    assert c.post(f"/api/recommendations/{rec_id}/decision", headers=G3, json={"decision": "reject", "note": "x"}).status_code == 409
    assert c.post(f"/api/requests/{rid}/plan", headers=G3).status_code == 409


def test_approve_with_edits_schedules(monkeypatch):
    calls = []
    monkeypatch.setattr(scheduling, "create_event", lambda ev, request_id=None, recommendation_id=None:
                        calls.append((ev, request_id, recommendation_id)), raising=False)
    rid = make_request()
    rec_id = planning.start_planning(rid)
    payload = c.get(f"/api/recommendations/{rec_id}", headers=G3).json()["payload"]
    payload.update(firing_point_id="fp-k2", proposed_start="2026-12-11T07:00:00", proposed_end="2026-12-11T15:00:00")
    r = c.post(f"/api/recommendations/{rec_id}/decision", headers=G3,
               json={"decision": "approve", "note": "moved to FP-2", "edits": payload})
    assert r.json()["payload"]["firing_point_id"] == "fp-k2"
    ev, req_id, rec = calls[0]
    assert (ev.firing_point_id, ev.start, ev.range_complex_id, req_id, rec) == ("fp-k2", "2026-12-11T07:00:00", "rc-kofa", rid, rec_id)
    assert request_row(rid)["status"] == "scheduled"


def test_approve_conflict_is_not_recorded(monkeypatch):
    def conflict(ev, request_id=None, recommendation_id=None):
        raise HTTPException(409, "Range busy")
    monkeypatch.setattr(scheduling, "create_event", conflict, raising=False)
    rid = make_request()
    rec_id = planning.start_planning(rid)
    assert c.post(f"/api/recommendations/{rec_id}/decision", headers=G3, json={"decision": "approve"}).status_code == 409
    assert request_row(rid)["status"] == "in_review"


def test_reject_requires_note():
    rid = make_request()
    rec_id = planning.start_planning(rid)
    assert c.post(f"/api/recommendations/{rec_id}/decision", headers=G3, json={"decision": "reject"}).status_code == 400
    r = c.post(f"/api/recommendations/{rec_id}/decision", headers=G3, json={"decision": "reject", "note": "Need SDZ waiver"})
    assert r.json()["status"] == "rejected" and r.json()["review_note"] == "Need SDZ waiver"
    assert request_row(rid)["status"] == "rejected"


class FakeResp:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


@pytest.fixture
def devin_on(monkeypatch):
    monkeypatch.setattr(devin_client, "enabled", lambda: True)
    sent = {}

    def fake_post(url, headers, json, timeout):
        sent.update(url=url, body=json)
        return FakeResp({"session_id": "devin-abc", "url": "https://app.devin.ai/sessions/abc", "status": "new"})
    monkeypatch.setattr(devin_client.httpx, "post", fake_post)
    return sent


def test_devin_planning_and_refresh(devin_on, monkeypatch):
    rid = make_request()
    rec_id = planning.start_planning(rid)
    assert "structured_output_schema" in devin_on["body"] and "XM1113" in devin_on["body"]["prompt"]
    assert "eq-m777-1" in devin_on["body"]["prompt"]
    rec = c.get(f"/api/recommendations/{rec_id}", headers=G3).json()
    assert (rec["source"], rec["status"], rec["devin_session_id"]) == ("devin", "pending_devin", "devin-abc")
    assert request_row(rid)["status"] == "in_review"
    assert c.post(f"/api/recommendations/{rec_id}/decision", headers=G3, json={"decision": "approve"}).status_code == 409

    monkeypatch.setattr(devin_client.httpx, "get", lambda url, headers, timeout: FakeResp({"status": "running"}))
    assert c.get(f"/api/recommendations/{rec_id}/refresh", headers=G3).json()["status"] == "pending_devin"

    out = matcher.recommend(ARTILLERY).model_dump()
    monkeypatch.setattr(devin_client.httpx, "get", lambda url, headers, timeout: FakeResp(
        {"status": "exit", "url": "https://app.devin.ai/sessions/abc", "structured_output": out}))
    rec = c.get(f"/api/recommendations/{rec_id}/refresh", headers=G3).json()
    assert rec["status"] == "draft" and rec["payload"]["range_complex_id"] == "rc-kofa"


def test_devin_failure_falls_back_to_rules(monkeypatch):
    monkeypatch.setattr(devin_client, "enabled", lambda: True)

    def boom(*a, **k):
        raise RuntimeError("network")
    monkeypatch.setattr(devin_client.httpx, "post", boom)
    rec_id = planning.start_planning(make_request())
    assert c.get(f"/api/recommendations/{rec_id}", headers=G3).json()["source"] == "rules"
