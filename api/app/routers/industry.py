"""WS1 - Industry intake. Owner: industry child session.

Contract (implement these; keep paths/models):
  GET  /api/companies/me            -> Company       (industry)
  PUT  /api/companies/me            Company -> Company (industry; validates UEI/CAGE)
  POST /api/requests                TestRequestIn -> TestRequest (industry; status=submitted, then calls
                                    planning.start_planning(request_id))
  GET  /api/requests                -> list[TestRequest] (industry: own; ATEC roles: all)
  GET  /api/requests/{id}           -> TestRequest + latest recommendation status
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["industry"])
