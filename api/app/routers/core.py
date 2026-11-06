"""Foundation endpoints: auth, taxonomy, ATEC sites and map layers, YTC resources."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from .. import refdata
from ..auth import ATEC_ROLES, current_user, require
from ..config import DEVIN_PLANNING_ENABLED
from ..schemas import LoginIn, LoginOut, Persona

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return {"ok": True, "devin_planning_enabled": DEVIN_PLANNING_ENABLED}


@router.get("/auth/personas")
def list_personas():
    return refdata.personas()


@router.post("/auth/login", response_model=LoginOut)
def login(body: LoginIn):
    p = next((p for p in refdata.personas() if p["username"] == body.username), None)
    if not p or body.password != "demo":
        raise HTTPException(401, "Invalid credentials")
    return LoginOut(token=p["username"], user=Persona(**p))


@router.get("/auth/me", response_model=Persona)
def me(user: Persona = Depends(current_user)):
    return user


@router.get("/taxonomy")
def taxonomy():
    return refdata.taxonomy()


@router.get("/sites", dependencies=[Depends(require(*ATEC_ROLES))])
def sites():
    return refdata.sites()


@router.get("/sites/{code}", dependencies=[Depends(require(*ATEC_ROLES))])
def site(code: str):
    s = next((s for s in refdata.sites() if s["code"] == code), None)
    if not s:
        raise HTTPException(404)
    return s


@router.get("/geo/installations", dependencies=[Depends(require(*ATEC_ROLES))])
def installations(code: Optional[str] = None):
    """Census TIGER 2024 installation boundaries; `code` filters to one ATEC site."""
    fc = refdata.installations()
    if code is None:
        return fc
    return {**fc, "features": [f for f in fc["features"] if f["properties"].get("code") == code]}


@router.get("/geo/sites/{code}/layers", dependencies=[Depends(require(*ATEC_ROLES))])
def site_layers(code: str):
    """Range complexes, firing points, target areas, gates and gated road segments."""
    if code != "YTC":
        return {"type": "FeatureCollection", "features": []}
    return refdata.ytc_layers()


@router.get("/geo/sites/{code}/roads/summary", dependencies=[Depends(require(*ATEC_ROLES))])
def site_road_summary(code: str):
    """Per gated road: length inside the installation (what closes without gates) and its gates/segments."""
    if code != "YTC":
        return []
    roads: dict[str, dict] = {}
    for f in refdata.features("road_segment"):
        p = f["properties"]
        r = roads.setdefault(p["road"], {"road": p["road"], "length_km": 0.0, "segments": [], "gates": []})
        r["length_km"] = round(r["length_km"] + p["length_km"], 2)
        r["segments"].append(p["id"])
    for f in refdata.features("gate"):
        if f["properties"]["road"] in roads:
            roads[f["properties"]["road"]]["gates"].append(f["properties"]["id"])
    return list(roads.values())


@router.get("/geo/sites/{code}/roads", dependencies=[Depends(require(*ATEC_ROLES))])
def site_roads(code: str):
    """Public road network (Census TIGER 2024) inside the installation."""
    if code != "YTC":
        return {"type": "FeatureCollection", "features": []}
    return refdata.ytc_roads()


@router.get("/sites/{code}/equipment", dependencies=[Depends(require(*ATEC_ROLES))])
def site_equipment(code: str):
    return [e for e in refdata.equipment() if e["site_code"] == code]


@router.get("/sites/{code}/personnel", dependencies=[Depends(require(*ATEC_ROLES))])
def site_personnel(code: str):
    return [p for p in refdata.personnel() if p["site_code"] == code]
