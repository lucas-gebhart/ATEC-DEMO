import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import type { Company, Taxonomy, TestRequest } from "../../lib/types";

export interface TestRequestDetail extends TestRequest { recommendation_id?: number; recommendation_status?: string }

export const STATUS_LABELS: Record<TestRequest["status"], string> = {
  submitted: "Submitted", planning: "Planning", in_review: "In G3 review",
  approved: "Approved", rejected: "Not approved", scheduled: "Scheduled",
};

export function StatusTag({ status }: { status: TestRequest["status"] }) {
  return <span className={`tag status-${status}`}>{STATUS_LABELS[status] ?? status}</span>;
}

/** Turns `api()` errors ("422 {detail: ...}") into a readable message. */
export function errorText(e: unknown): string {
  const msg = e instanceof Error ? e.message : String(e);
  const m = msg.match(/^(\d{3}) ([\s\S]*)$/);
  if (!m) return msg;
  try {
    const { detail } = JSON.parse(m[2]);
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((d) => `${d.loc?.slice(1).join(".") || "field"}: ${d.msg}`).join("; ");
  } catch { /* not JSON */ }
  return m[2] || `Request failed (${m[1]})`;
}

export function useLoad<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    api<T>(path).then((d) => live && setData(d)).catch((e) => live && setError(errorText(e)));
    return () => { live = false; };
  }, [path]);
  return { data, error, setData };
}

export const useCompany = () => useLoad<Company>("/companies/me");
export const useTaxonomy = () => useLoad<Taxonomy>("/taxonomy").data;

export const labelFor = (opts: { code: string; label: string }[] | undefined, code: string) =>
  opts?.find((o) => o.code === code)?.label ?? code;
