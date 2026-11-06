"""WS1 - Industry intake. Owner: industry child session.

Contract (implement these; keep paths/models):
  GET  /api/companies/me            -> Company       (industry)
  PUT  /api/companies/me            Company -> Company (industry; validates UEI/CAGE)
  POST /api/requests                TestRequestIn -> TestRequest (industry; status=submitted, then calls
                                    planning.start_planning(request_id))
  GET  /api/requests                -> list[TestRequest] (industry: own; ATEC roles: all)
  GET  /api/requests/{id}           -> TestRequest + latest recommendation status
"""
import json
import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from .. import refdata
from ..auth import ATEC_ROLES, current_user, require
from ..db import row, tx
from ..schemas import Company, Persona, TestRequest, TestRequestIn
from . import planning

router = APIRouter(prefix="/api", tags=["industry"])
log = logging.getLogger(__name__)

CLASSIFICATIONS = ("UNCLASSIFIED", "CUI")
NAICS_RE = re.compile(r"^\d{6}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class TestRequestDetail(TestRequest):
    recommendation_id: Optional[int] = None
    recommendation_status: Optional[str] = None


def _company_uei(user: Persona) -> str:
    if not user.company_uei:
        raise HTTPException(403, "Account is not linked to a company")
    return user.company_uei


def _invalid(msg: str):
    raise HTTPException(422, msg)


@router.get("/companies/me", response_model=Company)
def get_my_company(user: Persona = Depends(require("industry"))):
    with tx() as con:
        c = row(con.execute("SELECT * FROM companies WHERE uei=?", (_company_uei(user),)).fetchone())
    if not c:
        raise HTTPException(404, "Company profile not found")
    return c


@router.put("/companies/me", response_model=Company)
def put_my_company(body: Company, user: Persona = Depends(require("industry"))):
    uei = _company_uei(user)
    if body.uei != uei:
        _invalid("UEI is bound to your SAM.gov registration and cannot be changed here")
    bad = [n for n in body.naics if not NAICS_RE.match(n)]
    if bad:
        _invalid(f"NAICS codes must be 6 digits: {', '.join(bad)}")
    if not body.legal_name.strip() or not body.poc_name.strip():
        _invalid("Legal name and POC name are required")
    if not EMAIL_RE.match(body.poc_email):
        _invalid("POC email is not a valid address")
    with tx() as con:
        con.execute(
            "INSERT INTO companies (uei,cage,legal_name,naics,poc_name,poc_email,address) VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(uei) DO UPDATE SET cage=excluded.cage, legal_name=excluded.legal_name, naics=excluded.naics,"
            " poc_name=excluded.poc_name, poc_email=excluded.poc_email, address=excluded.address",
            (uei, body.cage, body.legal_name.strip(), json.dumps(body.naics), body.poc_name.strip(),
             body.poc_email.strip(), body.address.strip()))
    return body


def _validate_request(body: TestRequestIn):
    tax = refdata.taxonomy()
    if not body.system_name.strip():
        _invalid("System name is required")
    if body.mission_area not in {m["code"] for m in tax["test_mission_areas"]}:
        _invalid(f"Unknown test mission area: {body.mission_area}")
    allowed = {f["code"] for f in tax["test_functions"] if body.mission_area in f["mission_areas"]}
    bad = [f for f in body.test_functions if f not in allowed]
    if bad:
        _invalid(f"Test functions not applicable to {body.mission_area}: {', '.join(bad)}")
    if body.quantity < 1:
        _invalid("Quantity must be at least 1")
    if body.classification not in CLASSIFICATIONS:
        _invalid("Classification must be UNCLASSIFIED or CUI")
    if body.desired_start and body.desired_end and body.desired_end < body.desired_start:
        _invalid("Desired end date must be on or after the start date")


def _req(r):
    d = row(r)
    if d is not None:
        d["description"] = d.get("description") or ""
    return d


def _get_request(con, request_id: int):
    return _req(con.execute("SELECT * FROM test_requests WHERE id=?", (request_id,)).fetchone())


@router.post("/requests", response_model=TestRequest, status_code=201)
def create_request(body: TestRequestIn, user: Persona = Depends(require("industry"))):
    uei = _company_uei(user)
    _validate_request(body)
    with tx() as con:
        cur = con.execute(
            "INSERT INTO test_requests (company_uei,system_name,mission_area,test_functions,description,quantity,"
            "desired_start,desired_end,classification,status) VALUES (?,?,?,?,?,?,?,?,?,'submitted')",
            (uei, body.system_name.strip(), body.mission_area, json.dumps(body.test_functions),
             body.description.strip(), body.quantity, body.desired_start, body.desired_end, body.classification))
        request_id = cur.lastrowid
    try:
        planning.start_planning(request_id)
    except NotImplementedError:
        pass
    except Exception:  # planning failures must not lose the submission
        log.exception("start_planning failed for request %s", request_id)
    with tx() as con:
        return _get_request(con, request_id)


@router.get("/requests", response_model=list[TestRequest])
def list_requests(user: Persona = Depends(current_user)):
    with tx() as con:
        if user.role == "industry":
            rows = con.execute("SELECT * FROM test_requests WHERE company_uei=? ORDER BY id DESC",
                               (_company_uei(user),)).fetchall()
        elif user.role in ATEC_ROLES:
            rows = con.execute("SELECT * FROM test_requests ORDER BY id DESC").fetchall()
        else:
            raise HTTPException(403)
    return [_req(r) for r in rows]


@router.get("/requests/{request_id}", response_model=TestRequestDetail)
def get_request(request_id: int, user: Persona = Depends(current_user)):
    with tx() as con:
        r = _get_request(con, request_id)
        if not r or (user.role == "industry" and r["company_uei"] != user.company_uei) \
                or user.role not in ("industry", *ATEC_ROLES):
            raise HTTPException(404, "Request not found")
        rec = con.execute("SELECT id, status FROM recommendations WHERE request_id=? ORDER BY id DESC LIMIT 1",
                          (request_id,)).fetchone()
    if rec:
        r["recommendation_id"], r["recommendation_status"] = rec["id"], rec["status"]
    return r
