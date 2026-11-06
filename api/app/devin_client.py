"""Starts and polls Devin planning sessions via the Devin API (v3). Disabled unless
DEVIN_PLANNING_ENABLED=true and DEVIN_API_KEY / DEVIN_ORG_ID are set."""
import json

import httpx

from . import refdata
from .config import DEVIN_API_BASE, DEVIN_API_KEY, DEVIN_ORG_ID, DEVIN_PLANNING_ENABLED
from .schemas import RecommendationPayload


def enabled() -> bool:
    return DEVIN_PLANNING_ENABLED and bool(DEVIN_ORG_ID)


def _headers():
    return {"Authorization": f"Bearer {DEVIN_API_KEY}"}


def create_planning_session(prompt: str, title: str) -> dict:
    if not enabled():
        raise RuntimeError("Devin planning is disabled")
    r = httpx.post(
        f"{DEVIN_API_BASE}/v3/organizations/{DEVIN_ORG_ID}/sessions",
        headers=_headers(),
        json={"prompt": prompt, "title": title, "tags": ["atec-demo", "g3-planning"],
              "structured_output_schema": RecommendationPayload.model_json_schema(),
              "structured_output_required": True},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def get_session(session_id: str) -> dict:
    """SessionResponse: status, status_detail, url, structured_output (validated against the schema)."""
    if not enabled():
        raise RuntimeError("Devin planning is disabled")
    r = httpx.get(f"{DEVIN_API_BASE}/v3/organizations/{DEVIN_ORG_ID}/sessions/{session_id}",
                  headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json()


def planning_prompt(req: dict, company: dict | None, schedule: list[dict]) -> str:
    layers = [{"id": f["id"], **{k: v for k, v in f["properties"].items() if k not in ("id",)}}
              for f in refdata.ytc_layers()["features"] if f["properties"]["kind"] != "road_segment"]
    segments = [f["properties"] for f in refdata.features("road_segment")]
    data = {
        "test_request": {k: req.get(k) for k in ("id", "system_name", "mission_area", "test_functions", "description",
                                                  "quantity", "desired_start", "desired_end", "classification")},
        "company": company,
        "taxonomy": refdata.taxonomy(),
        "atec_sites": refdata.sites(),
        "ytc_layers": layers,
        "ytc_gated_road_segments": segments,
        "ytc_equipment": refdata.equipment(),
        "ytc_personnel": refdata.personnel(),
        "current_schedule": schedule,
    }
    return (
        "You are an ATEC test planner. Recommend where and when to run this industry test request.\n"
        "Rules: prefer Yuma Test Center (YTC) when it covers the requested test functions; pick one YTC range "
        "complex (id from ytc_layers, kind=range_complex, never an impact_area), equipment and personnel ids that "
        "cover the functions, a Range Safety Officer for hazardous/live-fire tests, and a weekday 07:00-15:00 "
        "window (ISO local time, e.g. 2026-12-07T07:00:00) inside desired_start/desired_end that does not clash "
        "with current_schedule. For indirect fire set weapon_class (taxonomy.weapon_classes), firing_point_id and "
        "target_area_id within max_range_km, and minimize gated road segments under the danger zone. "
        "score is 0-1. reasoning: short bullets on why this site/range/people/equipment/window. risks: coverage "
        "gaps, RSO needs, road closures, conflicts. alternatives: up to 2 objects with site_code, site_name, "
        "range_complex_id, range_name, coverage, note. Leave schedule_check null. Do not write code or open PRs; "
        "return only the structured output.\n\nDATA:\n" + json.dumps(data, indent=1)
    )
