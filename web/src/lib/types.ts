// Mirrors api/app/schemas.py. Change both together.
export type Role = "industry" | "g3" | "range_scheduler" | "atec_viewer";
export interface Persona { username: string; display: string; role: Role; company_uei?: string; site_code?: string }
export interface Option { code: string; label: string }
export interface TestFunctionOption extends Option { mission_areas: string[] }
export interface WeaponClass extends Option { max_range_km: number; sdz_half_angle_deg: number }
export interface Taxonomy { test_mission_areas: Option[]; test_functions: TestFunctionOption[]; weapon_classes: WeaponClass[] }
export interface Site { code: string; name: string; parent: string; state: string; lat: number; lon: number; has_detail: boolean; summary: string; test_functions: string[] }
export interface Company { uei: string; cage: string; legal_name: string; naics: string[]; poc_name: string; poc_email: string; address: string }
export interface TestRequestIn { system_name: string; mission_area: string; test_functions: string[]; description: string; quantity: number; desired_start?: string; desired_end?: string; classification: string }
export interface TestRequest extends TestRequestIn { id: number; company_uei: string; status: "submitted" | "planning" | "in_review" | "approved" | "rejected" | "scheduled"; created_at: string }
export interface RoadClosure { segment_id: string; road: string; gate_from?: string; gate_to?: string; length_km: number; start: string; end: string; reason: string }
export interface ProposedEvent { site_code: string; range_complex_id: string; title: string; start: string; end: string; weapon_class: string; firing_point_id?: string; target_area_id?: string; equipment_ids: string[]; personnel_ids: string[] }
export interface ScheduleEvent extends ProposedEvent { id: number; request_id?: number; recommendation_id?: number; status: string }
export interface Conflict { kind: "sdz_overlap" | "road_needed" | "equipment" | "personnel" | "range_busy"; event_id?: number; detail: string }
export interface ScheduleCheck { sdz?: GeoJSON.Polygon; closures: RoadClosure[]; closed_km_with_gates: number; closed_km_without_gates: number; conflicts: Conflict[] }
export interface RecommendationPayload { site_code: string; range_complex_id: string; proposed_start: string; proposed_end: string; equipment_ids: string[]; personnel_ids: string[]; weapon_class: string; firing_point_id?: string; target_area_id?: string; score: number; reasoning: string[]; risks: string[]; alternatives: Record<string, unknown>[]; schedule_check?: ScheduleCheck }
export interface Recommendation { id: number; request_id: number; source: "rules" | "devin"; status: "draft" | "approved" | "rejected" | "pending_devin"; payload: RecommendationPayload; devin_session_id?: string; devin_session_url?: string; reviewer?: string; review_note?: string; created_at: string; reviewed_at?: string }
