"""Read-only reference data loaded from data/seed and data/geo."""
import json
from functools import lru_cache

from .config import DATA


def _load(rel):
    return json.loads((DATA / rel).read_text())


@lru_cache
def taxonomy():
    return _load("seed/taxonomy.json")


@lru_cache
def sites():
    return _load("seed/sites.json")


@lru_cache
def equipment():
    return _load("seed/equipment.json")


@lru_cache
def personnel():
    return _load("seed/personnel.json")


@lru_cache
def personas():
    return _load("seed/personas.json")


@lru_cache
def installations():
    return _load("geo/installations.geojson")


@lru_cache
def ytc_layers():
    return _load("geo/ytc_layers.geojson")


@lru_cache
def ytc_roads():
    return _load("geo/ytc_roads.geojson")


def features(kind):
    return [f for f in ytc_layers()["features"] if f["properties"]["kind"] == kind]


def feature(fid):
    return next((f for f in ytc_layers()["features"] if f["id"] == fid), None)
