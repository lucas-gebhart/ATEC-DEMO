import { useState } from "react";
import { post } from "../../lib/api";
import type { Conflict, ProposedEvent, ScheduleCheck, WeaponClass } from "../../lib/types";
import type { Equipment, Layer, Person, ScheduleEventDetail } from "./model";
import { CONFLICT_LABEL, HARD, km } from "./model";

interface Props {
  form: ProposedEvent; setForm: (f: ProposedEvent) => void; layers: Layer[]; weapons: WeaponClass[];
  equipment: Equipment[]; personnel: Person[]; canSchedule: boolean;
  onChecked: (c: ScheduleCheck | null) => void; onScheduled: (e: ScheduleEventDetail) => void;
}

const toApi = (f: ProposedEvent): ProposedEvent => ({
  ...f, start: f.start.length === 16 ? `${f.start}:00` : f.start, end: f.end.length === 16 ? `${f.end}:00` : f.end,
  firing_point_id: f.weapon_class === "none" ? undefined : f.firing_point_id,
  target_area_id: f.weapon_class === "none" ? undefined : f.target_area_id,
});

function errorDetail(e: unknown): { message: string; check?: ScheduleCheck } {
  const m = String((e as Error).message ?? e);
  try {
    const d = JSON.parse(m.slice(4)).detail;
    return typeof d === "string" ? { message: d } : { message: d.message, check: d.check };
  } catch { return { message: m }; }
}

export default function ProposeForm({ form, setForm, layers, weapons, equipment, personnel, canSchedule, onChecked, onScheduled }: Props) {
  const [check, setCheck] = useState<ScheduleCheck | null>(null);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (patch: Partial<ProposedEvent>) => { setForm({ ...form, ...patch }); setCheck(null); onChecked(null); setMsg(null); };
  const of = (kind: string) => layers.filter((f) => f.properties.kind === kind);
  const name = (id?: string | null) => (id ? layers.find((f) => f.id === id)?.properties.name ?? id : "road end");
  const firingPoints = of("firing_point").filter((f) => f.properties.range_complex_id === form.range_complex_id);
  const hasSdz = form.weapon_class !== "none";
  const toggle = (key: "equipment_ids" | "personnel_ids", id: string) =>
    set({ [key]: form[key].includes(id) ? form[key].filter((x) => x !== id) : [...form[key], id] });

  const run = async (action: "check" | "schedule") => {
    setBusy(true); setMsg(null);
    try {
      if (action === "check") {
        const c = await post<ScheduleCheck>("/schedule/check", toApi(form));
        setCheck(c); onChecked(c);
      } else {
        const ev = await post<ScheduleEventDetail>("/schedule/events", toApi(form));
        setMsg({ ok: true, text: `Scheduled event #${ev.id}: ${ev.title}` }); onScheduled(ev);
      }
    } catch (e) {
      const d = errorDetail(e);
      setMsg({ ok: false, text: d.message });
      if (d.check) { setCheck(d.check); onChecked(d.check); }
    } finally { setBusy(false); }
  };

  const hard = check?.conflicts.filter((c) => HARD.has(c.kind)) ?? [];
  return (
    <div className="card">
      <h2>Propose event</h2>
      <form onSubmit={(e) => { e.preventDefault(); run("check"); }}>
        <label>Title<input required value={form.title} onChange={(e) => set({ title: e.target.value })} /></label>
        <div className="sched-row">
          <label>Range complex<select value={form.range_complex_id} onChange={(e) => {
            const fp = of("firing_point").find((f) => f.properties.range_complex_id === e.target.value);
            set({ range_complex_id: e.target.value, firing_point_id: fp ? String(fp.id) : undefined });
          }}>
            {of("range_complex").map((r) => <option key={String(r.id)} value={String(r.id)}>{r.properties.name}</option>)}
          </select></label>
          <label>Weapon class<select value={form.weapon_class} onChange={(e) => set({ weapon_class: e.target.value })}>
            {weapons.map((w) => <option key={w.code} value={w.code}>{w.label}{w.max_range_km ? ` (${w.max_range_km} km, ±${w.sdz_half_angle_deg}°)` : ""}</option>)}
          </select></label>
        </div>
        <div className="sched-row">
          <label>Start<input type="datetime-local" required value={form.start.slice(0, 16)} onChange={(e) => set({ start: e.target.value })} /></label>
          <label>End<input type="datetime-local" required value={form.end.slice(0, 16)} onChange={(e) => set({ end: e.target.value })} /></label>
        </div>
        {hasSdz && (
          <div className="sched-row">
            <label>Firing point<select value={form.firing_point_id ?? ""} onChange={(e) => set({ firing_point_id: e.target.value || undefined })}>
              <option value="">Select...</option>
              {firingPoints.map((f) => <option key={String(f.id)} value={String(f.id)}>{f.properties.name}</option>)}
            </select></label>
            <label>Target area<select value={form.target_area_id ?? ""} onChange={(e) => set({ target_area_id: e.target.value || undefined })}>
              <option value="">Select...</option>
              {of("target_area").map((f) => <option key={String(f.id)} value={String(f.id)}>{f.properties.name}</option>)}
            </select></label>
          </div>
        )}
        <div className="sched-row">
          <fieldset className="sched-checks"><legend>Equipment</legend>
            {equipment.map((e) => (
              <label key={e.id}><input type="checkbox" checked={form.equipment_ids.includes(e.id)} onChange={() => toggle("equipment_ids", e.id)} />{e.name}</label>
            ))}
          </fieldset>
          <fieldset className="sched-checks"><legend>Crew</legend>
            {personnel.map((p) => (
              <label key={p.id}><input type="checkbox" checked={form.personnel_ids.includes(p.id)} onChange={() => toggle("personnel_ids", p.id)} />{p.name} <span className="hint">{p.role}</span></label>
            ))}
          </fieldset>
        </div>
        <div className="sched-actions">
          <button className="secondary" type="submit" disabled={busy}>Check</button>
          {canSchedule && <button className="primary" type="button" disabled={busy || !check || hard.length > 0} onClick={() => run("schedule")}
            title={!check ? "Run Check first" : hard.length ? "Resolve hard conflicts first" : ""}>Schedule</button>}
          {!canSchedule && <span className="hint">Scheduling requires the G3 or range scheduler role.</span>}
        </div>
      </form>
      {msg && <p className={msg.ok ? "sched-ok" : "error"}>{msg.text}</p>}
      {check && <CheckResult check={check} gateName={name} />}
    </div>
  );
}

function CheckResult({ check, gateName }: { check: ScheduleCheck; gateName: (id?: string | null) => string }) {
  const kept = check.closed_km_without_gates - check.closed_km_with_gates;
  return (
    <div className="sched-result">
      <h3>Road closures</h3>
      {check.closures.length === 0 ? <p className="hint">{check.sdz ? "SDZ crosses no public road." : "No surface danger zone - no roads close."}</p> : (
        <>
          <table>
            <thead><tr><th>Road</th><th>Closed between</th><th>Length</th></tr></thead>
            <tbody>{check.closures.map((c) => (
              <tr key={c.segment_id}><td>{c.road}</td><td>{gateName(c.gate_from)} &rarr; {gateName(c.gate_to)}</td><td>{km(c.length_km)}</td></tr>
            ))}</tbody>
          </table>
          <div className="sched-kms">
            <div><span>Closed with gates</span><strong className="red">{km(check.closed_km_with_gates)}</strong></div>
            <div><span>Closed without gates</span><strong>{km(check.closed_km_without_gates)}</strong></div>
            <div><span>Kept open by gates</span><strong className="green">{km(kept)}</strong></div>
          </div>
        </>
      )}
      <h3>Conflicts</h3>
      {check.conflicts.length === 0 ? <p className="sched-ok">No conflicts with scheduled events.</p> : (
        <ul className="sched-conflicts">{check.conflicts.map((c: Conflict, i) => (
          <li key={i} className={HARD.has(c.kind) ? "hard" : "soft"}>
            <span className="tag">{HARD.has(c.kind) ? "HARD" : "ADVISORY"}</span> <b>{CONFLICT_LABEL[c.kind]}</b>: {c.detail}
          </li>
        ))}</ul>
      )}
    </div>
  );
}
