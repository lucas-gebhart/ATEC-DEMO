import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import type { Company, Recommendation, Site, Taxonomy, TestRequest } from "../../lib/types";

export interface QueueItem { request: TestRequest; company: Company | null; recommendation: Recommendation | null }
export interface Equipment { id: string; name: string; category: string; supports_functions: string[]; range_complex_id: string | null }
export interface Person { id: string; name: string; role: string; qualifications: string[] }
export interface Feature { id: string; properties: { kind: string; name: string; range_complex_id?: string; range_type?: string; test_functions?: string[] } }

export interface RefData {
  taxonomy: Taxonomy; sites: Site[]; equipment: Equipment[]; personnel: Person[]; features: Feature[];
  label: (code: string) => string; name: (id?: string | null) => string;
}

export function useRefData(): RefData | null {
  const [d, setD] = useState<RefData | null>(null);
  useEffect(() => {
    Promise.all([
      api<Taxonomy>("/taxonomy"), api<Site[]>("/sites"), api<Equipment[]>("/sites/YTC/equipment"),
      api<Person[]>("/sites/YTC/personnel"), api<{ features: Feature[] }>("/geo/sites/YTC/layers"),
    ]).then(([taxonomy, sites, equipment, personnel, layers]) => {
      const labels = new Map<string, string>([...taxonomy.test_mission_areas, ...taxonomy.test_functions, ...taxonomy.weapon_classes].map((o) => [o.code, o.label]));
      const names = new Map<string, string>([
        ...layers.features.map((f) => [f.id, f.properties.name] as [string, string]),
        ...equipment.map((e) => [e.id, e.name] as [string, string]),
        ...personnel.map((p) => [p.id, `${p.name} (${p.role})`] as [string, string]),
        ...sites.map((s) => [s.code, s.name] as [string, string]),
      ]);
      setD({ taxonomy, sites, equipment, personnel, features: layers.features,
        label: (c) => labels.get(c) ?? c, name: (id) => (id ? names.get(id) ?? id : "-") });
    });
  }, []);
  return d;
}

export const fmt = (iso?: string | null) => (iso ? iso.replace("T", " ").slice(0, 16) : "-");

export function SourceBadge({ rec }: { rec: Recommendation | null }) {
  if (!rec) return <span className="tag">Not planned</span>;
  return rec.source === "devin" ? <span className="tag g3-devin">Devin session</span> : <span className="tag g3-rules">Rules matcher</span>;
}

export function StatusTag({ status }: { status: string }) {
  return <span className={`tag g3-status-${status}`}>{status.replace("_", " ")}</span>;
}
