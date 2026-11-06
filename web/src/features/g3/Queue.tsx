import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../lib/api";
import { fmt, SourceBadge, StatusTag, type QueueItem, type RefData } from "./refdata";

export default function Queue({ refs }: { refs: RefData }) {
  const [items, setItems] = useState<QueueItem[] | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { api<QueueItem[]>("/g3/queue").then(setItems).catch((e) => setErr(String(e))); }, []);
  const pending = items?.filter((i) => i.request.status === "in_review").length ?? 0;
  return (
    <div className="card">
      <h1>G3 review queue</h1>
      <p className="hint">{pending} recommendation(s) awaiting G3 decision. Nothing is scheduled on a range until G3 approves.</p>
      {err && <p className="error">{err}</p>}
      {items && items.length === 0 && <p>No test requests yet.</p>}
      {items && items.length > 0 && (
        <table className="g3-table">
          <thead><tr><th>#</th><th>Company</th><th>System</th><th>Mission area</th><th>Test functions</th><th>Planning</th><th>Recommended</th><th>Score</th><th>Status</th><th /></tr></thead>
          <tbody>
            {items.map(({ request: r, company, recommendation: rec }) => (
              <tr key={r.id}>
                <td>{r.id}</td>
                <td>{company?.legal_name ?? r.company_uei}</td>
                <td><Link to={`requests/${r.id}`}>{r.system_name}</Link></td>
                <td>{refs.label(r.mission_area)}</td>
                <td className="g3-funcs">{r.test_functions.map((f) => <span key={f} className="g3-chip">{refs.label(f)}</span>)}</td>
                <td><SourceBadge rec={rec} /></td>
                <td>{rec && "range_complex_id" in rec.payload ? <>{refs.name(rec.payload.range_complex_id)}<div className="hint">{fmt(rec.payload.proposed_start)}</div></> : "-"}</td>
                <td>{rec && "score" in rec.payload ? `${Math.round(rec.payload.score * 100)}%` : "-"}</td>
                <td><StatusTag status={r.status} /></td>
                <td><Link to={`requests/${r.id}`}>Review</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
