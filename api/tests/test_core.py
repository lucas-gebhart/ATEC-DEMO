import os

os.environ["ATEC_DB"] = "/tmp/atec_test.db"

from fastapi.testclient import TestClient  # noqa: E402

from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402

init_db(reset=True)
c = TestClient(app)
H = {"Authorization": "Bearer g3.planner"}


def test_login_and_me():
    r = c.post("/api/auth/login", json={"username": "acme.industry", "password": "demo"})
    assert r.status_code == 200
    assert c.get("/api/auth/me", headers={"Authorization": f"Bearer {r.json()['token']}"}).json()["role"] == "industry"


def test_industry_cannot_see_sites():
    assert c.get("/api/sites", headers={"Authorization": "Bearer acme.industry"}).status_code == 403


def test_ytc_layers():
    fc = c.get("/api/geo/sites/YTC/layers", headers=H).json()
    kinds = {f["properties"]["kind"] for f in fc["features"]}
    assert {"range_complex", "firing_point", "target_area", "gate", "road_segment"} <= kinds


def test_sites_and_taxonomy():
    assert any(s["code"] == "YTC" for s in c.get("/api/sites", headers=H).json())
    assert len(c.get("/api/taxonomy").json()["test_mission_areas"]) >= 8
