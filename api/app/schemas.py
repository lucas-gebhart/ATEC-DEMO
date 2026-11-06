"""Shared API contract. Every workstream codes against these models; change them only in the foundation."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

Role = Literal["industry", "g3", "range_scheduler", "atec_viewer"]


class Persona(BaseModel):
    username: str
    display: str
    role: Role
    company_uei: Optional[str] = None
    site_code: Optional[str] = None


class LoginIn(BaseModel):
    username: str
    password: str


class LoginOut(BaseModel):
    token: str
    user: Persona


class Company(BaseModel):
    uei: str = Field(pattern=r"^[A-Z0-9]{12}$", description="SAM.gov Unique Entity ID (12 chars)")
    cage: str = Field(pattern=r"^[A-Z0-9]{5}$", description="CAGE code (5 chars)")
    legal_name: str
    naics: list[str] = []
    poc_name: str
    poc_email: str
    address: str = ""


class TestRequestIn(BaseModel):
    system_name: str
    mission_area: str
    test_functions: list[str] = Field(min_length=1)
    description: str = ""
    quantity: int = 1
    desired_start: Optional[str] = None
    desired_end: Optional[str] = None
    classification: str = "UNCLASSIFIED"


class TestRequest(TestRequestIn):
    id: int
    company_uei: str
    status: Literal["submitted", "planning", "in_review", "approved", "rejected", "scheduled"]
    created_at: str


class RoadClosure(BaseModel):
    segment_id: str
    road: str
    gate_from: Optional[str] = None
    gate_to: Optional[str] = None
    length_km: float
    start: str
    end: str
    reason: str


class ProposedEvent(BaseModel):
    site_code: str = "YTC"
    range_complex_id: str
    title: str
    start: str
    end: str
    weapon_class: str = "none"
    firing_point_id: Optional[str] = None
    target_area_id: Optional[str] = None
    equipment_ids: list[str] = []
    personnel_ids: list[str] = []


class ScheduleEvent(ProposedEvent):
    id: int
    request_id: Optional[int] = None
    recommendation_id: Optional[int] = None
    status: str = "scheduled"


class Conflict(BaseModel):
    kind: Literal["sdz_overlap", "road_needed", "equipment", "personnel", "range_busy"]
    event_id: Optional[int] = None
    detail: str


class ScheduleCheck(BaseModel):
    sdz: Optional[dict] = None  # GeoJSON Polygon of the surface danger zone
    closures: list[RoadClosure] = []
    closed_km_with_gates: float = 0
    closed_km_without_gates: float = 0
    conflicts: list[Conflict] = []


class RecommendationPayload(BaseModel):
    """Same shape whether it came from the rules matcher or a Devin session (structured_output_schema)."""
    site_code: str
    range_complex_id: str
    proposed_start: str
    proposed_end: str
    equipment_ids: list[str]
    personnel_ids: list[str]
    weapon_class: str = "none"
    firing_point_id: Optional[str] = None
    target_area_id: Optional[str] = None
    score: float
    reasoning: list[str]
    risks: list[str]
    alternatives: list[dict] = []
    schedule_check: Optional[ScheduleCheck] = None


class Recommendation(BaseModel):
    id: int
    request_id: int
    source: Literal["rules", "devin"]
    status: Literal["draft", "approved", "rejected", "pending_devin"]
    payload: RecommendationPayload | dict
    devin_session_id: Optional[str] = None
    devin_session_url: Optional[str] = None
    reviewer: Optional[str] = None
    review_note: Optional[str] = None
    created_at: str
    reviewed_at: Optional[str] = None


class DecisionIn(BaseModel):
    decision: Literal["approve", "reject"]
    note: str = ""
    edits: Optional[RecommendationPayload] = None
