import json
import os

os.environ.setdefault("ATEC_DB", "/tmp/atec_test.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import init_db, tx  # noqa: E402
from app.main import app  # noqa: E402
from app.routers import planning  # noqa: E402

c = TestClient(app)
IND = {"Authorization": "Bearer acme.industry"}
G3 = {"Authorization": "Bearer g3.planner"}
XM1299 = {
    "system_name": "XM1299 155mm self-propelled howitzer", "mission_area": "artillery",
    "test_functions": ["live_fire_indirect", "fuze_performance"], "description": "ERCA live fire",
    "quantity": 2, "desired_start": "2027-03-01", "desired_end": "2027-03-14", "classification": "UNCLASSIFIED",
}


@pytest.fixture(autouse=True)
def fresh_db():
    init_db(reset=True)


def company(**kw):
    return {**c.get("/api/companies/me", headers=IND).json(), **kw}


def test_get_company_seeded():
    r = c.get("/api/companies/me", headers=IND)
    assert r.status_code == 200
    assert r.json()["uei"] == "ACME12345XYZ" and r.json()["legal_name"].startswith("Acme Defense Systems")


def test_company_requires_industry():
    assert c.get("/api/companies/me", headers=G3).status_code == 403
    assert c.get("/api/companies/me").status_code == 401


def test_put_company_updates():
    body = company(cage="9ZZZ1", naics=["336992", "541330"], poc_name="Sam Ortiz")
    assert c.put("/api/companies/me", headers=IND, json=body).status_code == 200
    got = c.get("/api/companies/me", headers=IND).json()
    assert got["cage"] == "9ZZZ1" and got["naics"] == ["336992", "541330"] and got["poc_name"] == "Sam Ortiz"


@pytest.mark.parametrize("bad", [
    {"uei": "SHORT"}, {"uei": "acme12345xyz"}, {"cage": "12"}, {"cage": "7ACM1X"},
    {"uei": "OTHER1234567"}, {"naics": ["33699"]}, {"naics": ["abcdef"]}, {"poc_email": "nope"},
])
def test_put_company_validation(bad):
    assert c.put("/api/companies/me", headers=IND, json=company(**bad)).status_code == 422


def test_submit_request_planning_stub(monkeypatch):
    calls = []

    def stub(rid):
        calls.append(rid)
        raise NotImplementedError

    monkeypatch.setattr(planning, "start_planning", stub)
    r = c.post("/api/requests", headers=IND, json=XM1299)
    assert r.status_code == 201, r.text
    req = r.json()
    assert req["status"] == "submitted" and req["company_uei"] == "ACME12345XYZ"
    assert req["test_functions"] == XM1299["test_functions"] and calls == [req["id"]]


def test_submit_request_with_planning(monkeypatch):
    def fake_plan(rid):
        with tx() as con:
            con.execute("UPDATE test_requests SET status='in_review' WHERE id=?", (rid,))
            cur = con.execute("INSERT INTO recommendations (request_id,source,status,payload) VALUES (?,?,?,?)",
                              (rid, "rules", "draft", json.dumps({})))
            return cur.lastrowid

    monkeypatch.setattr(planning, "start_planning", fake_plan)
    rid = c.post("/api/requests", headers=IND, json=XM1299).json()["id"]
    d = c.get(f"/api/requests/{rid}", headers=IND).json()
    assert d["status"] == "in_review" and d["recommendation_status"] == "draft" and d["recommendation_id"]


def test_submit_survives_planning_error(monkeypatch):
    monkeypatch.setattr(planning, "start_planning", lambda rid: 1 / 0)
    assert c.post("/api/requests", headers=IND, json=XM1299).json()["status"] == "submitted"


@pytest.mark.parametrize("bad", [
    {"test_functions": []}, {"mission_area": "naval"}, {"test_functions": ["uas_flight"]},
    {"classification": "SECRET"}, {"quantity": 0}, {"desired_start": "2027-03-14", "desired_end": "2027-03-01"},
    {"system_name": "  "},
])
def test_submit_request_validation(bad):
    assert c.post("/api/requests", headers=IND, json={**XM1299, **bad}).status_code == 422


def test_submit_requires_industry():
    assert c.post("/api/requests", headers=G3, json=XM1299).status_code == 403


def test_list_and_detail_scoping():
    mine = c.post("/api/requests", headers=IND, json=XM1299).json()["id"]
    with tx() as con:
        other = con.execute(
            "INSERT INTO test_requests (company_uei,system_name,mission_area,test_functions) VALUES (?,?,?,?)",
            ("OTHERCO12345", "Other system", "uas", json.dumps(["uas_flight"]))).lastrowid
    assert [r["id"] for r in c.get("/api/requests", headers=IND).json()] == [mine]
    assert {r["id"] for r in c.get("/api/requests", headers=G3).json()} == {mine, other}
    assert c.get(f"/api/requests/{other}", headers=IND).status_code == 404
    assert c.get(f"/api/requests/{other}", headers=G3).status_code == 200
    d = c.get(f"/api/requests/{mine}", headers=IND).json()
    assert d["system_name"] == XM1299["system_name"] and d["recommendation_status"] in (None, "draft")
    assert c.get("/api/requests/9999", headers=IND).status_code == 404


def test_industry_blocked_from_atec_endpoints():
    for path in ("/api/sites", "/api/geo/installations", "/api/geo/sites/YTC/layers", "/api/sites/YTC/equipment"):
        assert c.get(path, headers=IND).status_code == 403, path
