"""Builds data/geo/ytc_layers.geojson: YTC range complexes, firing points, impact areas,
gates and gated US-95 / range-road segments, laid out on the real TIGER boundary and roads."""
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


features = []


def add(kind, fid, name, geom, **props):
    features.append({"type": "Feature", "id": fid,
                     "properties": {"id": fid, "kind": kind, "name": name, **props},
                     "geometry": mapping(geom)})


complexes = [
    ("rc-kofa", "Kofa Firing Range", "artillery",
     poly((32.98, -114.36), (33.12, -114.36), (33.12, -114.05), (32.98, -114.05)),
     ["live_fire_indirect", "live_fire_direct", "munitions_lethality", "fuze_performance"]),
    ("rc-kofa-impact", "Kofa Impact Area", "impact_area",
     poly((33.0, -114.15), (33.18, -114.15), (33.18, -113.85), (33.0, -113.85)),
     ["live_fire_indirect", "munitions_lethality"]),
    ("rc-cibola", "Cibola Range", "aviation",
     poly((33.25, -114.45), (33.50, -114.45), (33.50, -114.15), (33.25, -114.15)),
     ["aircraft_armament", "uas_flight", "target_acquisition", "airdrop"]),
    ("rc-laguna", "Laguna Army Airfield", "airfield",
     poly((32.85, -114.41), (32.88, -114.41), (32.88, -114.38), (32.85, -114.38)),
     ["uas_flight", "airdrop", "aircraft_armament"]),
    ("rc-mobility", "Mobility Test Courses", "mobility",
     poly((32.80, -114.37), (32.92, -114.37), (32.92, -114.30), (32.80, -114.30)),
     ["mobility_durability", "environmental_desert", "vehicle_performance"]),
    ("rc-ncties", "Counter-IED Test Complex", "c_ied",
     poly((32.92, -114.25), (32.98, -114.25), (32.98, -114.15), (32.92, -114.15)),
     ["c_ied", "mine_countermine", "survivability"]),
    ("rc-castle-dome", "Castle Dome Annex", "environmental",
     poly((33.05, -114.05), (33.15, -114.05), (33.15, -113.95), (33.05, -113.95)),
     ["environmental_desert", "materiel_storage", "soldier_systems"]),
    ("rc-dz", "Drop Zone Complex", "airdrop",
     poly((33.20, -114.30), (33.28, -114.30), (33.28, -114.18), (33.20, -114.18)),
     ["airdrop", "guided_airdrop"]),
]
for fid, name, rtype, geom, funcs in complexes:
    add("range_complex", fid, name, geom, range_type=rtype, test_functions=funcs)

firing_points = [("fp-k1", "Kofa FP-1 (west of US-95)", 33.040, -114.330),
                 ("fp-k2", "Kofa FP-2", 33.090, -114.250),
                 ("fp-k3", "Kofa FP-3", 33.000, -114.200)]
for fid, name, lat, lon in firing_points:
    add("firing_point", fid, name, Point(lon, lat), range_complex_id="rc-kofa")

targets = [("ta-k-north", "Kofa Impact North", 33.13, -114.00, 0.035),
           ("ta-k-east", "Kofa Impact East", 33.05, -113.92, 0.03)]
for fid, name, lat, lon, r in targets:
    add("target_area", fid, name, Point(lon, lat).buffer(r), range_complex_id="rc-kofa-impact")

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
