"""Starts a Devin planning session via the Devin API (v3). Disabled unless DEVIN_PLANNING_ENABLED=true
and DEVIN_API_KEY / DEVIN_ORG_ID are set. WS2 owns wiring this into start_planning()."""
import httpx

from .config import DEVIN_API_BASE, DEVIN_API_KEY, DEVIN_ORG_ID, DEVIN_PLANNING_ENABLED
from .schemas import RecommendationPayload


def enabled() -> bool:
    return DEVIN_PLANNING_ENABLED and bool(DEVIN_ORG_ID)


def create_planning_session(prompt: str, title: str) -> dict:
    if not enabled():
        raise RuntimeError("Devin planning is disabled")
    r = httpx.post(
        f"{DEVIN_API_BASE}/v3/organizations/{DEVIN_ORG_ID}/sessions",
        headers={"Authorization": f"Bearer {DEVIN_API_KEY}"},
        json={"prompt": prompt, "title": title, "tags": ["atec-demo", "g3-planning"],
              "structured_output_schema": RecommendationPayload.model_json_schema(),
              "structured_output_required": True},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()
