"""WS2 - Planning (rules matcher + Devin session) and G3 review.

  POST /api/requests/{id}/plan                 -> Recommendation  (g3; re-run planning)
  GET  /api/g3/queue                           -> list[{request, company, recommendation}] (g3)
  GET  /api/recommendations/{id}               -> Recommendation (ATEC roles)
  GET  /api/recommendations/{id}/refresh       -> Recommendation (g3; poll a pending Devin session)
  POST /api/recommendations/{id}/decision      DecisionIn -> Recommendation (g3). Approve schedules the
                                               event via scheduling.create_event(...); nothing is scheduled
                                               without a G3 approve.
Python entry point used by WS1:
  start_planning(request_id: int) -> int   # returns recommendation id
"""
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from .. import devin_client, matcher
from ..auth import ATEC_ROLES, require
from ..db import row, tx
from ..schemas import DecisionIn, Persona, Recommendation, RecommendationPayload

router = APIRouter(prefix="/api", tags=["planning"])
log = logging.getLogger(__name__)
G3 = Depends(require("g3"))


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _request(con, request_id):
    r = row(con.execute("SELECT * FROM test_requests WHERE id=?", (request_id,)).fetchone())
    if not r:
        raise HTTPException(404, "Test request not found")
    return r


def _rec(con, rec_id):
    r = row(con.execute("SELECT * FROM recommendations WHERE id=?", (rec_id,)).fetchone())
    if not r:
        raise HTTPException(404, "Recommendation not found")
    return r


def _company(con, uei):
    return row(con.execute("SELECT * FROM companies WHERE uei=?", (uei,)).fetchone())


def _set_status(con, request_id, status):
    con.execute("UPDATE test_requests SET status=? WHERE id=?", (status, request_id))


def _insert(con, request_id, source, status, payload, session_id=None, session_url=None):
    cur = con.execute(
        "INSERT INTO recommendations (request_id,source,status,payload,devin_session_id,devin_session_url,created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (request_id, source, status, json.dumps(payload), session_id, session_url, _now()))
    return cur.lastrowid


def _start_devin(con, req) -> int | None:
    schedule = [row(e) for e in con.execute("SELECT * FROM schedule_events WHERE status != 'cancelled'")]
    prompt = devin_client.planning_prompt(req, _company(con, req["company_uei"]), schedule)
    try:
        s = devin_client.create_planning_session(prompt, f"ATEC planning: {req['system_name']} (request {req['id']})")
    except Exception:  # noqa: BLE001 - any API failure falls back to the rules matcher
        log.exception("Devin planning session failed; using rules matcher")
        return None
    return _insert(con, req["id"], "devin", "pending_devin", {}, s.get("session_id"), s.get("url"))


def start_planning(request_id: int) -> int:
    """Create a recommendation for a request (Devin session if enabled, else rules matcher)."""
    with tx() as con:
        req = _request(con, request_id)
        _set_status(con, request_id, "planning")
    with tx() as con:
        rec_id = _start_devin(con, req) if devin_client.enabled() else None
        if rec_id is None:
            try:
                payload = matcher.recommend(req)
            except ValueError as e:
                _set_status(con, request_id, "submitted")
                raise HTTPException(422, str(e)) from e
            rec_id = _insert(con, request_id, "rules", "draft", payload.model_dump())
        _set_status(con, request_id, "in_review")
    return rec_id


@router.post("/requests/{request_id}/plan", response_model=Recommendation, dependencies=[G3])
def plan(request_id: int):
    with tx() as con:
        if _request(con, request_id)["status"] in ("approved", "scheduled"):
            raise HTTPException(409, "Request is already approved")
    rec_id = start_planning(request_id)
    with tx() as con:
        return _rec(con, rec_id)


@router.get("/g3/queue", dependencies=[G3])
def queue():
    with tx() as con:
        out = []
        for r in con.execute("SELECT * FROM test_requests ORDER BY id DESC"):
            req = row(r)
            rec = row(con.execute("SELECT * FROM recommendations WHERE request_id=? ORDER BY id DESC LIMIT 1",
                                  (req["id"],)).fetchone())
            out.append({"request": req, "company": _company(con, req["company_uei"]), "recommendation": rec})
        return out


@router.get("/recommendations/{rec_id}", response_model=Recommendation, dependencies=[Depends(require(*ATEC_ROLES))])
def get_recommendation(rec_id: int):
    with tx() as con:
        return _rec(con, rec_id)


@router.get("/recommendations/{rec_id}/refresh", response_model=Recommendation, dependencies=[G3])
def refresh(rec_id: int):
    """Poll a pending Devin session and turn its structured output into a draft."""
    with tx() as con:
        rec = _rec(con, rec_id)
        req = _request(con, rec["request_id"])
    if rec["source"] != "devin" or rec["status"] != "pending_devin":
        return rec
    try:
        s = devin_client.get_session(rec["devin_session_id"])
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"Could not reach Devin session: {e}") from e
    out = s.get("structured_output")
    if not out:
        return rec
    try:
        payload = matcher.attach_schedule_check(RecommendationPayload.model_validate(out), req)
    except ValidationError as e:
        raise HTTPException(502, f"Devin structured output did not match RecommendationPayload: {e}") from e
    with tx() as con:
        con.execute("UPDATE recommendations SET status='draft', payload=?, devin_session_url=COALESCE(?, devin_session_url)"
                    " WHERE id=?", (json.dumps(payload.model_dump()), s.get("url"), rec_id))
        return _rec(con, rec_id)


def _schedule(payload: RecommendationPayload, req, rec_id) -> bool:
    """True if WS4 created the event; False while scheduling is still a stub. Raises HTTPException on conflict."""
    from . import scheduling
    fn = getattr(scheduling, "create_event", None)
    if fn is None:
        return False
    try:
        fn(matcher.to_event(payload, matcher.event_title(req)), request_id=req["id"], recommendation_id=rec_id)
    except NotImplementedError:
        return False
    return True


@router.post("/recommendations/{rec_id}/decision", response_model=Recommendation)
def decide(rec_id: int, body: DecisionIn, user: Persona = Depends(require("g3"))):
    with tx() as con:
        rec = _rec(con, rec_id)
        req = _request(con, rec["request_id"])
    if rec["status"] != "draft":
        raise HTTPException(409, f"Recommendation is {rec['status']}, not a draft")
    if body.decision == "reject":
        if not body.note.strip():
            raise HTTPException(400, "A note is required to reject")
        payload, status, req_status = rec["payload"], "rejected", "rejected"
    else:
        p = body.edits or RecommendationPayload.model_validate(rec["payload"])
        if body.edits:
            p.schedule_check = None
            p = matcher.attach_schedule_check(p, req)
        req_status = "scheduled" if _schedule(p, req, rec_id) else "approved"
        payload, status = p.model_dump(), "approved"
    with tx() as con:
        con.execute("UPDATE recommendations SET status=?, payload=?, reviewer=?, review_note=?, reviewed_at=? WHERE id=?",
                    (status, json.dumps(payload), user.username, body.note, _now(), rec_id))
        _set_status(con, req["id"], req_status)
        return _rec(con, rec_id)
