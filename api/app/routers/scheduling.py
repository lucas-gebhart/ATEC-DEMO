"""WS4 - Range scheduling and road-closure rules. Owner: scheduling child session.

Contract:
  GET  /api/schedule/events?site=YTC&from=&to=   -> list[ScheduleEvent] (ATEC roles)
  POST /api/schedule/check   ProposedEvent       -> ScheduleCheck (ATEC roles; no write)
  POST /api/schedule/events  ProposedEvent       -> ScheduleEvent (g3, range_scheduler; 409 on hard conflict)
  GET  /api/schedule/closures?at=ISO             -> list[RoadClosure] active at that time
Python entry points used by WS2:
  check_event(ev: ProposedEvent) -> ScheduleCheck
  create_event(ev: ProposedEvent, request_id=None, recommendation_id=None) -> ScheduleEvent
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["scheduling"])
