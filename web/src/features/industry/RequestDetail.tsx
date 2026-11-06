import { Link, useLocation, useParams } from "react-router-dom";
import type { TestRequest } from "../../lib/types";
import { STATUS_LABELS, StatusTag, labelFor, useLoad, useTaxonomy, type TestRequestDetail } from "./common";

const STEPS: TestRequest["status"][] = ["submitted", "planning", "in_review", "approved", "scheduled"];
const NEXT: Record<TestRequest["status"], string> = {
  submitted: "Your request is queued for ATEC planning.",
  planning: "ATEC planning is drafting a test site and schedule recommendation.",
  in_review: "A recommendation is with ATEC G3 for review.",
  approved: "ATEC G3 approved the plan; range scheduling is in progress.",
  rejected: "ATEC G3 did not approve this request. Your ATEC point of contact will follow up.",
  scheduled: "Your test is on the range schedule. Your ATEC point of contact will share details.",
};

export default function RequestDetail() {
  const { id } = useParams();
  const { state } = useLocation() as { state?: { justSubmitted?: boolean } };
  const { data: r, error } = useLoad<TestRequestDetail>(`/requests/${id}`);
  const tax = useTaxonomy();

  if (error) return <div className="card"><p className="error" role="alert">{error}</p><Link to="/industry">Back to my requests</Link></div>;
  if (!r) return <div className="card"><p className="hint">Loading request...</p></div>;

  const reached = r.status === "rejected" ? STEPS.indexOf("in_review") : STEPS.indexOf(r.status);
  const steps = r.status === "rejected" ? [...STEPS.slice(0, 3), "rejected" as const] : STEPS;

  return (
    <div className="card">
      {state?.justSubmitted && <div className="ind-success-box" role="status">Test request TR-{r.id} submitted.</div>}
      <p><Link to="/industry">&larr; My requests</Link></p>
      <div className="ind-head">
        <h1>TR-{r.id}: {r.system_name}</h1>
        <StatusTag status={r.status} />
      </div>
      <ol className="ind-steps" aria-label="Request status">
        {steps.map((s, i) => (
          <li key={s} className={s === r.status ? "current" : i <= reached ? "done" : undefined}>{STATUS_LABELS[s]}</li>
        ))}
      </ol>
      <p>{NEXT[r.status]}</p>
      <dl className="ind-details">
        <dt>Test mission area</dt><dd>{labelFor(tax?.test_mission_areas, r.mission_area)}</dd>
        <dt>Applicable test functions</dt><dd>{r.test_functions.map((f) => labelFor(tax?.test_functions, f)).join(", ")}</dd>
        <dt>Description</dt><dd>{r.description || "-"}</dd>
        <dt>Quantity</dt><dd>{r.quantity}</dd>
        <dt>Desired window</dt><dd>{r.desired_start && r.desired_end ? `${r.desired_start} to ${r.desired_end}` : "-"}</dd>
        <dt>Classification</dt><dd>{r.classification}</dd>
        <dt>Company UEI</dt><dd><code>{r.company_uei}</code></dd>
        <dt>Submitted</dt><dd>{r.created_at}</dd>
      </dl>
    </div>
  );
}
