import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { post } from "../../lib/api";
import type { TestRequest, TestRequestIn } from "../../lib/types";
import CompanyCard from "./CompanyCard";
import { errorText, useCompany, useTaxonomy } from "./common";

const CLASSIFICATIONS = ["UNCLASSIFIED", "CUI"];
type Errors = Partial<Record<"system_name" | "mission_area" | "test_functions" | "quantity" | "window", string>>;

const empty: TestRequestIn = {
  system_name: "", mission_area: "", test_functions: [], description: "", quantity: 1,
  desired_start: "", desired_end: "", classification: "UNCLASSIFIED",
};

function validate(f: TestRequestIn): Errors {
  const e: Errors = {};
  if (!f.system_name.trim()) e.system_name = "System name is required.";
  if (!f.mission_area) e.mission_area = "Choose a test mission area.";
  if (!f.test_functions.length) e.test_functions = "Select at least one applicable test function.";
  if (!Number.isInteger(f.quantity) || f.quantity < 1) e.quantity = "Quantity must be a whole number of at least 1.";
  if (!f.desired_start || !f.desired_end) e.window = "Enter a desired start and end date.";
  else if (f.desired_end < f.desired_start) e.window = "End date must be on or after the start date.";
  return e;
}

export default function NewRequest() {
  const nav = useNavigate();
  const company = useCompany();
  const tax = useTaxonomy();
  const [f, setF] = useState<TestRequestIn>(empty);
  const [tried, setTried] = useState(false);
  const [submitErr, setSubmitErr] = useState("");
  const [busy, setBusy] = useState(false);

  const errs = tried ? validate(f) : {};
  const functions = tax?.test_functions.filter((t) => t.mission_areas.includes(f.mission_area)) ?? [];
  const set = <K extends keyof TestRequestIn>(k: K, v: TestRequestIn[K]) => setF((p) => ({ ...p, [k]: v }));
  const toggle = (code: string) =>
    set("test_functions", f.test_functions.includes(code) ? f.test_functions.filter((c) => c !== code) : [...f.test_functions, code]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitErr("");
    setTried(true);
    if (Object.keys(validate(f)).length) return;
    setBusy(true);
    try {
      const r = await post<TestRequest>("/requests", { ...f, system_name: f.system_name.trim(), description: f.description.trim() });
      nav(`/industry/requests/${r.id}`, { state: { justSubmitted: true } });
    } catch (x) {
      setSubmitErr(errorText(x));
      setBusy(false);
    }
  };

  const err = (k: keyof Errors) => errs[k] && <span className="error">{errs[k]}</span>;

  return (
    <form className="card ind-form" onSubmit={submit} noValidate>
      <h1>New test request</h1>
      {company.data && <CompanyCard company={company.data} />}
      {company.error && <p className="error" role="alert">{company.error}</p>}
      {Object.keys(errs).length > 0 && (
        <div className="ind-alert" role="alert">Please fix the {Object.keys(errs).length} highlighted field(s) below.</div>
      )}

      <label className={errs.system_name ? "ind-invalid" : undefined}>System name
        <input value={f.system_name} onChange={(e) => set("system_name", e.target.value)} placeholder="e.g. XM1299 155mm self-propelled howitzer" aria-invalid={!!errs.system_name} />
        {err("system_name")}
      </label>
      <label>Description
        <textarea rows={3} value={f.description} onChange={(e) => set("description", e.target.value)} placeholder="Test objectives, configuration, special requirements" />
      </label>
      <div className="ind-grid">
        <label className={errs.quantity ? "ind-invalid" : undefined}>Quantity (test articles)
          <input type="number" min={1} value={Number.isNaN(f.quantity) ? "" : f.quantity} onChange={(e) => set("quantity", e.target.valueAsNumber)} aria-invalid={!!errs.quantity} />
          {err("quantity")}
        </label>
        <label>Classification
          <select value={f.classification} onChange={(e) => set("classification", e.target.value)}>
            {CLASSIFICATIONS.map((c) => <option key={c}>{c}</option>)}
          </select>
          <span className="hint ind-fieldhint">Classified test needs are handled outside this system.</span>
        </label>
      </div>
      <fieldset className={`ind-fieldset${errs.window ? " ind-invalid" : ""}`}>
        <legend>Desired test window</legend>
        <div className="ind-grid">
          <label>Start date<input type="date" value={f.desired_start} onChange={(e) => set("desired_start", e.target.value)} aria-invalid={!!errs.window} /></label>
          <label>End date<input type="date" value={f.desired_end} min={f.desired_start || undefined} onChange={(e) => set("desired_end", e.target.value)} aria-invalid={!!errs.window} /></label>
        </div>
        {err("window")}
      </fieldset>
      <label className={errs.mission_area ? "ind-invalid" : undefined}>Test Mission Area
        <select value={f.mission_area} onChange={(e) => setF((p) => ({ ...p, mission_area: e.target.value, test_functions: [] }))} aria-invalid={!!errs.mission_area}>
          <option value="">- Select -</option>
          {tax?.test_mission_areas.map((m) => <option key={m.code} value={m.code}>{m.label}</option>)}
        </select>
        {err("mission_area")}
      </label>
      <fieldset className={`ind-fieldset${errs.test_functions ? " ind-invalid" : ""}`}>
        <legend>Applicable Test Functions</legend>
        {!f.mission_area && <p className="hint">Choose a Test Mission Area to see applicable test functions.</p>}
        <div className="ind-checks">
          {functions.map((t) => (
            <label key={t.code} className="ind-check">
              <input type="checkbox" checked={f.test_functions.includes(t.code)} onChange={() => toggle(t.code)} />
              {t.label}
            </label>
          ))}
        </div>
        {err("test_functions")}
      </fieldset>
      {submitErr && <p className="error" role="alert">{submitErr}</p>}
      <button className="primary" type="submit" disabled={busy}>{busy ? "Submitting..." : "Submit test request"}</button>
    </form>
  );
}
