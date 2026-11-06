import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, post } from "../../lib/api";
import type { Recommendation, RecommendationPayload } from "../../lib/types";
import { fmt, SourceBadge, StatusTag, type QueueItem, type RefData } from "./refdata";

const isPlan = (p: Recommendation["payload"] | undefined): p is RecommendationPayload => !!p && "range_complex_id" in p;
const toLocal = (iso: string) => iso.slice(0, 16);
const fromLocal = (v: string) => (v.length === 16 ? `${v}:00` : v);

export default function Detail({ refs }: { refs: RefData }) {
  const { id } = useParams();
  const [item, setItem] = useState<QueueItem | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [edit, setEdit] = useState<RecommendationPayload | null>(null);
  const [rejecting, setRejecting] = useState(false);
  const [note, setNote] = useState("");

  const load = useCallback(() => api<QueueItem[]>("/g3/queue")
    .then((q) => setItem(q.find((i) => String(i.request.id) === id) ?? null)).catch((e) => setErr(String(e))), [id]);
  useEffect(() => { load(); }, [load]);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true); setErr("");
    try { await fn(); setEdit(null); setRejecting(false); await load(); } catch (e) { setErr(String(e)); } finally { setBusy(false); }
  };

  if (!item) return <div className="card"><Link to="/g3">&larr; Queue</Link><p>{err || "Loading..."}</p></div>;
  const { request: r, company: co, recommendation: rec } = item;
  const p = isPlan(rec?.payload) ? rec!.payload as RecommendationPayload : null;
  const draft = rec?.status === "draft";
  const decide = (decision: "approve" | "reject") => act(() => post(`/recommendations/${rec!.id}/decision`, { decision, note, edits: decision === "approve" ? edit : null }));

  return (
    <>
      <div className="card">
        <Link to="/g3">&larr; G3 review queue</Link>
        <div className="g3-head">
          <h1>{r.system_name}</h1>
          <SourceBadge rec={rec} /> <StatusTag status={r.status} />
          {p && <span className="g3-score" title="Matcher score">{Math.round(p.score * 100)}%</span>}
        </div>
        {rec?.devin_session_url && <p><a href={rec.devin_session_url} target="_blank" rel="noreferrer">Open Devin planning session</a></p>}
        {rec?.status === "pending_devin" && <p className="hint">Devin is planning this request.{" "}
          <button className="secondary" disabled={busy} onClick={() => act(() => api(`/recommendations/${rec.id}/refresh`))}>Check Devin session</button></p>}
        {rec?.review_note && <p><b>G3 note ({rec.reviewer}, {fmt(rec.reviewed_at)}):</b> {rec.review_note}</p>}
        {err && <p className="error">{err}</p>}
      </div>

      <div className="g3-grid">
        <div className="card">
          <h2>Company</h2>
          {co ? <dl className="g3-kv">
            <dt>Legal name</dt><dd>{co.legal_name}</dd>
            <dt>UEI</dt><dd>{co.uei}</dd>
            <dt>CAGE</dt><dd>{co.cage}</dd>
            <dt>NAICS</dt><dd>{co.naics.join(", ")}</dd>
            <dt>POC</dt><dd>{co.poc_name} &lt;{co.poc_email}&gt;</dd>
            <dt>Address</dt><dd>{co.address}</dd>
          </dl> : <p>{r.company_uei}</p>}
        </div>
        <div className="card">
          <h2>Test request #{r.id}</h2>
          <dl className="g3-kv">
            <dt>Mission area</dt><dd>{refs.label(r.mission_area)}</dd>
            <dt>Test functions</dt><dd>{r.test_functions.map((f) => <span key={f} className="g3-chip">{refs.label(f)}</span>)}</dd>
            <dt>Quantity</dt><dd>{r.quantity}</dd>
            <dt>Desired window</dt><dd>{r.desired_start ?? "any"} to {r.desired_end ?? "any"}</dd>
            <dt>Classification</dt><dd>{r.classification}</dd>
            <dt>Description</dt><dd>{r.description || "-"}</dd>
            <dt>Submitted</dt><dd>{fmt(r.created_at)}</dd>
          </dl>
        </div>

        {p && <div className="card">
          <h2>Recommended plan</h2>
          <dl className="g3-kv">
            <dt>Site</dt><dd>{refs.name(p.site_code)}</dd>
            <dt>Range complex</dt><dd>{refs.name(p.range_complex_id)}</dd>
            <dt>Window</dt><dd>{fmt(p.proposed_start)} to {fmt(p.proposed_end)}</dd>
            <dt>Weapon class</dt><dd>{refs.label(p.weapon_class)}</dd>
            {p.firing_point_id && <><dt>Firing point</dt><dd>{refs.name(p.firing_point_id)}</dd></>}
            {p.target_area_id && <><dt>Target area</dt><dd>{refs.name(p.target_area_id)}</dd></>}
            <dt>Equipment</dt><dd>{p.equipment_ids.length ? p.equipment_ids.map((e) => <div key={e}>{refs.name(e)}</div>) : "-"}</dd>
            <dt>Crew</dt><dd>{p.personnel_ids.length ? p.personnel_ids.map((e) => <div key={e}>{refs.name(e)}</div>) : "-"}</dd>
          </dl>
        </div>}
        {p && <div className="card">
          <h2>Why this plan</h2>
          <ul>{p.reasoning.map((x, i) => <li key={i}>{x}</li>)}</ul>
          <h3>Risks</h3>
          {p.risks.length ? <ul className="g3-risks">{p.risks.map((x, i) => <li key={i}>{x}</li>)}</ul> : <p className="hint">None identified.</p>}
        </div>}

        {p && <div className="card">
          <h2>Alternatives</h2>
          {p.alternatives.length ? <table><thead><tr><th>Site</th><th>Range</th><th>Coverage</th><th>Note</th></tr></thead><tbody>
            {p.alternatives.map((a, i) => <tr key={i}><td>{String(a.site_name ?? a.site_code ?? "")}</td><td>{String(a.range_name ?? a.range_complex_id ?? "")}</td>
              <td>{typeof a.coverage === "number" ? `${Math.round(a.coverage * 100)}%` : "-"}</td><td>{String(a.note ?? "")}</td></tr>)}
          </tbody></table> : <p className="hint">No other site or range covers these test functions.</p>}
        </div>}
        {p && <ScheduleCheckCard p={p} refs={refs} />}

        {draft && p && <div className="card g3-wide">
          <h2>G3 decision</h2>
          {edit && <EditForm value={edit} onChange={setEdit} refs={refs} />}
          <label>Note {rejecting && <span className="error">(required to reject)</span>}<textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} /></label>
          <div className="g3-actions" style={{ marginTop: 12 }}>
            <button className="primary" disabled={busy} onClick={() => decide("approve")}>{edit ? "Approve with edits" : "Approve"} &amp; schedule</button>
            {edit ? <button className="secondary" disabled={busy} onClick={() => setEdit(null)}>Discard edits</button>
              : <button className="secondary" disabled={busy} onClick={() => setEdit(structuredClone(p))}>Edit</button>}
            {rejecting ? <button className="danger" disabled={busy || !note.trim()} onClick={() => decide("reject")}>Confirm reject</button>
              : <button className="danger" disabled={busy} onClick={() => setRejecting(true)}>Reject</button>}
            <button className="link g3-replan" disabled={busy} onClick={() => act(() => post(`/requests/${r.id}/plan`, {}))}>Re-run planning</button>
          </div>
        </div>}
        {!rec && <div className="card g3-wide"><button className="primary" disabled={busy} onClick={() => act(() => post(`/requests/${r.id}/plan`, {}))}>Run planning</button></div>}
      </div>
    </>
  );
}

function ScheduleCheckCard({ p, refs }: { p: RecommendationPayload; refs: RefData }) {
  const sc = p.schedule_check;
  return (
    <div className="card">
      <h2>Schedule check</h2>
      {!sc ? <p className="hint">Range schedule check not available yet (scheduling service pending). Closures and conflicts will appear here.</p> : <>
        {sc.closures.length > 0 && <p>Road closed: <span className="g3-closed">{sc.closed_km_with_gates.toFixed(1)} km</span> with gates
          (vs {sc.closed_km_without_gates.toFixed(1)} km without gates)</p>}
        {sc.closures.length ? <table><thead><tr><th>Road</th><th>Between gates</th><th>km</th><th>Reason</th></tr></thead><tbody>
          {sc.closures.map((c) => <tr key={c.segment_id}><td>{c.road}</td><td>{refs.name(c.gate_from ?? null)} to {refs.name(c.gate_to ?? null)}</td><td>{c.length_km.toFixed(1)}</td><td>{c.reason}</td></tr>)}
        </tbody></table> : <p>No road closures required.</p>}
        <h3>Conflicts</h3>
        {sc.conflicts.length ? <ul className="g3-risks">{sc.conflicts.map((c, i) => <li key={i}><b>{c.kind.replace("_", " ")}</b>: {c.detail}</li>)}</ul> : <p className="hint">None.</p>}
      </>}
    </div>
  );
}

function EditForm({ value: v, onChange, refs }: { value: RecommendationPayload; onChange: (p: RecommendationPayload) => void; refs: RefData }) {
  const set = (patch: Partial<RecommendationPayload>) => onChange({ ...v, ...patch });
  const toggle = (list: string[], id: string) => (list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);
  const ranges = refs.features.filter((f) => f.properties.kind === "range_complex" && f.properties.range_type !== "impact_area");
  const fps = refs.features.filter((f) => f.properties.kind === "firing_point" && f.properties.range_complex_id === v.range_complex_id);
  const tas = refs.features.filter((f) => f.properties.kind === "target_area");
  return (
    <div className="g3-grid">
      <div>
        <label>Range complex<select value={v.range_complex_id} onChange={(e) => set({ range_complex_id: e.target.value, site_code: "YTC", firing_point_id: undefined })}>
          {!ranges.some((f) => f.id === v.range_complex_id) && <option value={v.range_complex_id}>{refs.name(v.range_complex_id)}</option>}
          {ranges.map((f) => <option key={f.id} value={f.id}>{f.properties.name}</option>)}
        </select></label>
        <label>Start<input type="datetime-local" value={toLocal(v.proposed_start)} onChange={(e) => set({ proposed_start: fromLocal(e.target.value) })} /></label>
        <label>End<input type="datetime-local" value={toLocal(v.proposed_end)} onChange={(e) => set({ proposed_end: fromLocal(e.target.value) })} /></label>
        <label>Weapon class<select value={v.weapon_class} onChange={(e) => set({ weapon_class: e.target.value })}>
          {refs.taxonomy.weapon_classes.map((w) => <option key={w.code} value={w.code}>{w.label}</option>)}
        </select></label>
        {v.weapon_class !== "none" && <>
          <label>Firing point<select value={v.firing_point_id ?? ""} onChange={(e) => set({ firing_point_id: e.target.value || undefined })}>
            <option value="">-</option>{fps.map((f) => <option key={f.id} value={f.id}>{f.properties.name}</option>)}
          </select></label>
          <label>Target area<select value={v.target_area_id ?? ""} onChange={(e) => set({ target_area_id: e.target.value || undefined })}>
            <option value="">-</option>{tas.map((f) => <option key={f.id} value={f.id}>{f.properties.name}</option>)}
          </select></label>
        </>}
      </div>
      <div className="g3-checks">
        <label style={{ fontWeight: 600 }}>Equipment</label>
        {refs.equipment.map((e) => <label key={e.id}><input type="checkbox" checked={v.equipment_ids.includes(e.id)}
          onChange={() => set({ equipment_ids: toggle(v.equipment_ids, e.id) })} />{e.name}</label>)}
        <label style={{ fontWeight: 600 }}>Crew</label>
        {refs.personnel.map((x) => <label key={x.id}><input type="checkbox" checked={v.personnel_ids.includes(x.id)}
          onChange={() => set({ personnel_ids: toggle(v.personnel_ids, x.id) })} />{x.name} ({x.role})</label>)}
      </div>
    </div>
  );
}
