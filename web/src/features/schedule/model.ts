import type { RoadClosure, ScheduleCheck, ScheduleEvent } from "../../lib/types";

export interface ScheduleEventDetail extends ScheduleEvent {
  sdz?: GeoJSON.Geometry | null;
  closures: RoadClosure[];
  closed_km_with_gates: number;
  closed_km_without_gates: number;
}
export interface Equipment { id: string; name: string; category: string; range_complex_id?: string | null }
export interface Person { id: string; name: string; role: string }
export type Layer = GeoJSON.Feature<GeoJSON.Geometry, { kind: string; name: string; [k: string]: unknown }>;
export interface MapFocus { label: string; sdz?: GeoJSON.Geometry | null; closures: RoadClosure[]; firing_point_id?: string; target_area_id?: string }

export const HARD = new Set(["equipment", "personnel", "range_busy", "sdz_overlap"]);
export const CONFLICT_LABEL: Record<string, string> = {
  sdz_overlap: "SDZ overlap", road_needed: "Road needed", equipment: "Equipment", personnel: "Personnel", range_busy: "Range busy",
};
export const km = (n: number) => `${n.toFixed(2)} km`;
export const hhmm = (iso: string) => iso.slice(11, 16);
export const focusOf = (label: string, ev: { firing_point_id?: string; target_area_id?: string }, c: Pick<ScheduleCheck, "closures"> & { sdz?: GeoJSON.Geometry | null }): MapFocus =>
  ({ label, sdz: c.sdz, closures: c.closures, firing_point_id: ev.firing_point_id, target_area_id: ev.target_area_id });
