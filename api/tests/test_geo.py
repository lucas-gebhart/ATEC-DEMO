import os

os.environ["ATEC_DB"] = "/tmp/atec_test.db"

from fastapi.testclient import TestClient  # noqa: E402

from app import refdata  # noqa: E402
from app.main import app  # noqa: E402

c = TestClient(app)
H = {"Authorization": "Bearer atec.hq"}


def test_installations_cover_sites_and_filter():
    fc = c.get("/api/geo/installations", headers=H).json()
    codes = {f["properties"]["code"] for f in fc["features"]}
    assert {"YTC", "ATC", "WSMR", "DPG", "RTC", "EPG", "CRTC", "OTC"} <= codes
    one = c.get("/api/geo/installations?code=YTC", headers=H).json()
    assert [f["properties"]["code"] for f in one["features"]] == ["YTC"]
    assert c.get("/api/geo/installations?code=NOPE", headers=H).json()["features"] == []


def test_geo_requires_atec_role():
    for path in ("/api/geo/installations", "/api/geo/sites/YTC/layers", "/api/geo/sites/YTC/roads",
                 "/api/geo/sites/YTC/roads/summary"):
        assert c.get(path, headers={"Authorization": "Bearer acme.industry"}).status_code == 403
        assert c.get(path).status_code == 401


def test_road_summary_sums_gated_segments():
    rows = {r["road"]: r for r in c.get("/api/geo/sites/YTC/roads/summary", headers=H).json()}
    us95 = rows["US Hwy 95"]
    segs = [f for f in refdata.features("road_segment") if f["properties"]["road"] == "US Hwy 95"]
    assert us95["length_km"] == round(sum(f["properties"]["length_km"] for f in segs), 2)
    assert len(us95["gates"]) == len(us95["segments"]) - 1
    assert c.get("/api/geo/sites/ATC/roads/summary", headers=H).json() == []


def test_layers_inside_boundary_and_linked():
    from shapely.geometry import shape

    ytc = shape(next(f for f in refdata.installations()["features"] if f["properties"]["code"] == "YTC")["geometry"])
    fc = c.get("/api/geo/sites/YTC/layers", headers=H).json()
    ids = {f["id"] for f in fc["features"]}
    for f in fc["features"]:
        p, g = f["properties"], shape(f["geometry"])
        if p["kind"] in ("range_complex", "target_area"):
            assert g.difference(ytc).area < 1e-9, f["id"]
        if p["kind"] in ("firing_point", "gate"):
            assert ytc.contains(g), f["id"]
        if p["kind"] in ("firing_point", "target_area"):
            assert p["range_complex_id"] in ids
        if p["kind"] == "road_segment":
            assert {p["gate_from"], p["gate_to"]} - {None} <= ids


def test_equipment_and_personnel_reference_ytc_ranges():
    rc = {f["id"] for f in refdata.features("range_complex")}
    eq = c.get("/api/sites/YTC/equipment", headers=H).json()
    assert eq and all(e["range_complex_id"] in rc for e in eq if e.get("range_complex_id"))
    assert c.get("/api/sites/YTC/personnel", headers=H).json()
