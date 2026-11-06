"""Builds data/geo/ytc_layers.geojson: YTC range complexes, firing points, impact areas,
gates and gated US-95 / range-road segments, laid out on the real TIGER boundary and roads.

Placement sources (public): Census TIGER/Line 2024 boundary and roads; OpenStreetMap (ODbL) for the
Laguna Army Airfield footprint (relation 14707120), the General Motors Desert Proving Ground tenant
area (relation 14707124, kept out of Army range complexes), the Kofa firing-front facilities east of
US-95 and the former North Army Airfield on Cibola Range; Esri World Imagery for visual checks.
Every feature is kept inside the TIGER installation boundary."""
import json
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon, mapping, shape
from shapely.ops import linemerge, split, unary_union

ROOT = Path(__file__).resolve().parents[1]
GEO = ROOT / "data" / "geo"

inst = json.loads((GEO / "installations.geojson").read_text())
ypg = shape(next(f for f in inst["features"] if f["properties"]["code"] == "YTC")["geometry"])
roads = json.loads((GEO / "ytc_roads.geojson").read_text())


def road(name):
    g = unary_union([shape(f["geometry"]) for f in roads["features"] if f["properties"]["name"] == name])
    g = linemerge(g) if g.geom_type == "MultiLineString" else g
    return max(getattr(g, "geoms", [g]), key=lambda x: x.length)


def poly(*pts):
    return Polygon([(lon, lat) for lat, lon in pts]).intersection(ypg)


def inside(geom):
    assert geom.difference(ypg).area <= 1e-9 and (geom.area or ypg.contains(geom)), geom
    return geom


LAGUNA_AAF = poly((32.8544, -114.3849), (32.8468, -114.3899), (32.8444, -114.3846), (32.8397, -114.3833),
                  (32.835, -114.3865), (32.8353, -114.3904), (32.8331, -114.3918), (32.8362, -114.3982),
                  (32.8375, -114.3974), (32.8382, -114.399), (32.8396, -114.3997), (32.8484, -114.3937),
                  (32.8511, -114.3932), (32.8586, -114.4004), (32.8591, -114.4032), (32.8643, -114.3995),
                  (32.866, -114.4016), (32.8667, -114.4012), (32.8664, -114.4042), (32.8729, -114.3973),
                  (32.8782, -114.3958), (32.8796, -114.3948), (32.8753, -114.3814), (32.8688, -114.374),
                  (32.862, -114.3797))
GM_DESERT_PG = Polygon([(lon, lat) for lat, lon in (
    (32.9207, -114.3296), (32.9215, -114.3268), (32.9187, -114.3244), (32.9165, -114.3242), (32.9072, -114.3303),
    (32.8837, -114.3456), (32.8761, -114.3504), (32.879, -114.3586), (32.8823, -114.3629), (32.8841, -114.3633),
    (32.886, -114.3584), (32.8915, -114.3538), (32.8939, -114.356), (32.8871, -114.3683), (32.8968, -114.3737),
    (32.9029, -114.3795), (32.9175, -114.3699), (32.9259, -114.3384), (32.926, -114.33))]).buffer(0.002)


features = []


def add(kind, fid, name, geom, **props):
    features.append({"type": "Feature", "id": fid,
                     "properties": {"id": fid, "kind": kind, "name": name, **props},
                     "geometry": mapping(geom)})


complexes = [
    ("rc-kofa", "Kofa Firing Range", "artillery",
     poly((32.96, -114.36), (33.06, -114.36), (33.06, -114.12), (32.96, -114.12)),
     ["live_fire_indirect", "live_fire_direct", "munitions_lethality", "fuze_performance"]),
    ("rc-kofa-impact", "Kofa Impact Area", "impact_area",
     poly((32.97, -114.12), (33.20, -114.12), (33.20, -113.80), (32.97, -113.80)),
     ["live_fire_indirect", "munitions_lethality"]),
    ("rc-cibola", "Cibola Range", "aviation",
     poly((33.22, -114.47), (33.55, -114.47), (33.55, -114.25), (33.22, -114.25)),
     ["aircraft_armament", "uas_flight", "target_acquisition", "airdrop"]),
    ("rc-laguna", "Laguna Army Airfield", "airfield", LAGUNA_AAF,
     ["uas_flight", "airdrop", "aircraft_armament"]),
    ("rc-mobility", "Mobility Test Courses", "mobility",
     poly((32.79, -114.372), (32.875, -114.372), (32.875, -114.30), (32.79, -114.30))
     .difference(GM_DESERT_PG).difference(LAGUNA_AAF.buffer(0.002)),
     ["mobility_durability", "environmental_desert", "vehicle_performance"]),
    ("rc-ncties", "Counter-IED Test Complex", "c_ied",
     poly((32.90, -114.27), (32.955, -114.27), (32.955, -114.17), (32.90, -114.17)),
     ["c_ied", "mine_countermine", "survivability"]),
    ("rc-castle-dome", "Castle Dome Annex", "environmental",
     poly((32.88, -114.12), (32.96, -114.12), (32.96, -114.00), (32.88, -114.00)),
     ["environmental_desert", "materiel_storage", "soldier_systems"]),
    ("rc-dz", "Drop Zone Complex", "airdrop",
     poly((33.32, -114.315), (33.41, -114.315), (33.41, -114.262), (33.32, -114.262)),
     ["airdrop", "guided_airdrop"]),
]
for fid, name, rtype, geom, funcs in complexes:
    add("range_complex", fid, name, inside(geom), range_type=rtype, test_functions=funcs)

firing_points = [("fp-k1", "Kofa FP-1 (west of US-95)", 33.040, -114.330),
                 ("fp-k2", "Kofa FP-2", 33.016, -114.246),
                 ("fp-k3", "Kofa FP-3", 33.000, -114.200)]
for fid, name, lat, lon in firing_points:
    add("firing_point", fid, name, inside(Point(lon, lat)), range_complex_id="rc-kofa")

targets = [("ta-k-north", "Kofa Impact North", 33.065, -113.99, 0.035),
           ("ta-k-east", "Kofa Impact East", 33.05, -113.92, 0.03)]
for fid, name, lat, lon, r in targets:
    add("target_area", fid, name, inside(Point(lon, lat).buffer(r)), range_complex_id="rc-kofa-impact")

gated_roads = {"US Hwy 95": [0.10, 0.35, 0.48, 0.60, 0.72, 0.90],
               "Castle Dome Mine Rd": [0.3, 0.6],
               "Cibola Rd": [0.4]}
for rname, fracs in gated_roads.items():
    line = road(rname)
    pts = [line.interpolate(f, normalized=True) for f in fracs]
    slug = rname.lower().replace(" ", "-")
    gate_ids = []
    for i, p in enumerate(pts, 1):
        gid = f"gate-{slug}-{i}"
        gate_ids.append(gid)
        add("gate", gid, f"{rname} Gate {i}", p, road=rname)
    cuts = [0.0] + [line.project(p) for p in pts] + [line.length]
    bounds = [None] + gate_ids + [None]
    for i in range(len(cuts) - 1):
        a, b = cuts[i], cuts[i + 1]
        n = 20
        seg = LineString([line.interpolate(a + (b - a) * k / n) for k in range(n + 1)])
        add("road_segment", f"seg-{slug}-{i + 1}", f"{rname} segment {i + 1}", seg,
            road=rname, gate_from=bounds[i], gate_to=bounds[i + 1],
            length_km=round(seg.length * 100, 2))

out = {"type": "FeatureCollection", "features": features}
(GEO / "ytc_layers.geojson").write_text(json.dumps(out))
print(f"wrote {len(features)} features")
