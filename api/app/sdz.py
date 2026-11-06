"""Surface danger zone (SDZ) geometry and gate-aware road-closure rules. Pure functions.

Geometry is computed in a local metric plane (km) using an equirectangular projection centred
on YTC, which is accurate to well under 1% over the ~100 km extent of the installation.
"""
import math
from functools import lru_cache

from shapely.geometry import Point, mapping, shape
from shapely.ops import transform, unary_union

from . import refdata

LAT0, LON0 = 33.0, -114.2
_KM_PER_DEG = 6371.0088 * math.pi / 180
_COS0 = math.cos(math.radians(LAT0))
TARGET_BUFFER_KM = 1.0
FAN_STEPS = 32


def to_km(geom):
    return transform(lambda x, y, z=None: ((x - LON0) * _KM_PER_DEG * _COS0, (y - LAT0) * _KM_PER_DEG), geom)


def to_lonlat(geom):
    return transform(lambda x, y, z=None: (x / (_KM_PER_DEG * _COS0) + LON0, y / _KM_PER_DEG + LAT0), geom)


def weapon_class(code):
    return next((w for w in refdata.taxonomy()["weapon_classes"] if w["code"] == code), None)


def sdz_km(firing_point, target_area, weapon):
    """SDZ in local km: fan from the firing point toward the target centroid, unioned with the buffered target.

    firing_point / target_area are shapely geometries in local km; weapon is a taxonomy weapon_class dict.
    """
    if not weapon or weapon["code"] == "none" or weapon["max_range_km"] <= 0:
        return None
    c = target_area.centroid
    bearing = math.atan2(c.y - firing_point.y, c.x - firing_point.x)
    far_edge = max(firing_point.distance(Point(p)) for p in target_area.exterior.coords)
    reach = min(weapon["max_range_km"], far_edge + TARGET_BUFFER_KM)
    half = math.radians(weapon["sdz_half_angle_deg"])
    arc = [(firing_point.x + reach * math.cos(bearing - half + 2 * half * i / FAN_STEPS),
            firing_point.y + reach * math.sin(bearing - half + 2 * half * i / FAN_STEPS)) for i in range(FAN_STEPS + 1)]
    fan = shape({"type": "Polygon", "coordinates": [[(firing_point.x, firing_point.y), *arc, (firing_point.x, firing_point.y)]]})
    return unary_union([fan, target_area.buffer(TARGET_BUFFER_KM)])


@lru_cache(maxsize=256)
def event_sdz(weapon_code, firing_point_id, target_area_id):
    """SDZ for an event as a lon/lat shapely geometry, or None when the weapon class has no SDZ."""
    weapon = weapon_class(weapon_code)
    if not weapon or weapon["code"] == "none":
        return None
    fp, ta = refdata.feature(firing_point_id), refdata.feature(target_area_id)
    if not fp or not ta:
        return None
    zone = sdz_km(to_km(shape(fp["geometry"])), to_km(shape(ta["geometry"])), weapon)
    return to_lonlat(zone) if zone is not None else None


def closed_segments(zone):
    """Road segments (lon/lat features) intersecting the SDZ. Segments are already split at gates."""
    if zone is None:
        return []
    return [f for f in refdata.features("road_segment") if shape(f["geometry"]).intersects(zone)]


def closure_km(segments):
    """(closed_km_with_gates, closed_km_without_gates): without gates every touched road closes end to end."""
    with_gates = sum(f["properties"]["length_km"] for f in segments)
    roads = {f["properties"]["road"] for f in segments}
    without = sum(f["properties"]["length_km"] for f in refdata.features("road_segment") if f["properties"]["road"] in roads)
    return round(with_gates, 2), round(without, 2)


def geojson(geom):
    return mapping(geom) if geom is not None else None
