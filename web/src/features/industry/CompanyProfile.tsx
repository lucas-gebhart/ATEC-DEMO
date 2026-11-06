import { useEffect, useState } from "react";
import { put } from "../../lib/api";
import type { Company } from "../../lib/types";
import { errorText, useCompany } from "./common";

interface Form { uei: string; cage: string; legal_name: string; naics: string; poc_name: string; poc_email: string; address: string }
const toForm = (c: Company): Form => ({ ...c, naics: c.naics.join(", ") });

function validate(f: Form): Partial<Record<keyof Form, string>> {
  const e: Partial<Record<keyof Form, string>> = {};
  if (!/^[A-Z0-9]{12}$/.test(f.uei)) e.uei = "UEI must be 12 letters or digits.";
  if (!/^[A-Z0-9]{5}$/.test(f.cage)) e.cage = "CAGE code must be 5 letters or digits.";
  if (!f.legal_name.trim()) e.legal_name = "Legal name is required.";
  const bad = splitNaics(f.naics).filter((n) => !/^\d{6}$/.test(n));
  if (bad.length) e.naics = `NAICS codes must be 6 digits: ${bad.join(", ")}`;
  if (!f.poc_name.trim()) e.poc_name = "POC name is required.";
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(f.poc_email.trim())) e.poc_email = "Enter a valid email address.";
  return e;
}
const splitNaics = (s: string) => s.split(",").map((n) => n.trim()).filter(Boolean);

export default function CompanyProfile() {
  const { data, error } = useCompany();
  const [f, setF] = useState<Form | null>(null);
  const [tried, setTried] = useState(false);
  const [status, setStatus] = useState<{ ok: boolean; msg: string } | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (data) setF(toForm(data)); }, [data]);

  if (error) return <div className="card"><p className="error" role="alert">{error}</p></div>;
  if (!f) return <div className="card"><p className="hint">Loading company profile...</p></div>;

  const errs = tried ? validate(f) : {};
  const set = (k: keyof Form, upper = false) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setF({ ...f, [k]: upper ? e.target.value.toUpperCase() : e.target.value });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus(null);
    setTried(true);
    if (Object.keys(validate(f)).length) return;
    setBusy(true);
    try {
      const saved = await put<Company>("/companies/me", {
        ...f, legal_name: f.legal_name.trim(), poc_name: f.poc_name.trim(), poc_email: f.poc_email.trim(),
        address: f.address.trim(), naics: splitNaics(f.naics),
      });
      setF(toForm(saved));
      setStatus({ ok: true, msg: "Company profile saved." });
    } catch (x) {
      setStatus({ ok: false, msg: errorText(x) });
    } finally { setBusy(false); }
  };

  const field = (k: keyof Form, label: string, opts: { hint?: string; upper?: boolean; readOnly?: boolean; type?: string } = {}) => (
    <label className={errs[k] ? "ind-invalid" : undefined}>{label}
      {opts.hint && <span className="hint ind-fieldhint">{opts.hint}</span>}
      <input type={opts.type ?? "text"} value={f[k]} onChange={set(k, opts.upper)} readOnly={opts.readOnly}
        aria-invalid={!!errs[k]} />
      {errs[k] && <span className="error">{errs[k]}</span>}
    </label>
  );

  return (
    <form className="card ind-form" onSubmit={submit} noValidate>
      <h1>Company profile</h1>
      <p className="hint">Identifiers must match your SAM.gov entity registration.</p>
      <div className="ind-grid">
        {field("uei", "Unique Entity ID (UEI)", { hint: "12 characters; tied to your account", readOnly: true })}
        {field("cage", "CAGE code", { hint: "5 characters", upper: true })}
      </div>
      {field("legal_name", "Legal business name")}
      {field("naics", "NAICS codes", { hint: "6-digit codes, comma separated" })}
      <div className="ind-grid">
        {field("poc_name", "Point of contact name")}
        {field("poc_email", "Point of contact email", { type: "email" })}
      </div>
      {field("address", "Address")}
      {status && <p className={status.ok ? "ind-success" : "error"} role="status">{status.msg}</p>}
      <button className="primary" type="submit" disabled={busy}>{busy ? "Saving..." : "Save profile"}</button>
    </form>
  );
}
