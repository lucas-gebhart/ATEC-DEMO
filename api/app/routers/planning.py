"""WS2 - Planning (rules matcher + Devin session) and G3 review. Owner: planning child session.

Contract:
  POST /api/requests/{id}/plan            -> Recommendation  (g3; re-run planning)
  GET  /api/g3/queue                      -> list[{request, company, recommendation}] (g3)
  GET  /api/recommendations/{id}          -> Recommendation (ATEC roles)
  POST /api/recommendations/{id}/decision DecisionIn -> Recommendation (g3). On approve, create a
                                          schedule_events row via scheduling.create_event(...).
Python entry point used by WS1:
  start_planning(request_id: int) -> int   # returns recommendation id
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["planning"])


def start_planning(request_id: int) -> int:
    raise NotImplementedError("WS2 implements this")
