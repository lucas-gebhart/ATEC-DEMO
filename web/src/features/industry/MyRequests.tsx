import { Link } from "react-router-dom";
import type { TestRequest } from "../../lib/types";
import { StatusTag, labelFor, useLoad, useTaxonomy } from "./common";

export default function MyRequests() {
  const { data, error } = useLoad<TestRequest[]>("/requests");
  const tax = useTaxonomy();
  return (
    <div className="card">
      <div className="ind-head">
        <h1>My test requests</h1>
        <Link className="button-link" to="/industry/new">New test request</Link>
      </div>
      {error && <p className="error" role="alert">{error}</p>}
      {data && data.length === 0 && <p className="hint">No requests yet. Submit a test need to start ATEC planning.</p>}
      {data && data.length > 0 && (
        <table>
          <thead><tr><th>ID</th><th>System</th><th>Test mission area</th><th>Desired window</th><th>Submitted</th><th>Status</th></tr></thead>
          <tbody>
            {data.map((r) => (
              <tr key={r.id}>
                <td>TR-{r.id}</td>
                <td><Link to={`/industry/requests/${r.id}`}>{r.system_name}</Link></td>
                <td>{labelFor(tax?.test_mission_areas, r.mission_area)}</td>
                <td>{r.desired_start && r.desired_end ? `${r.desired_start} to ${r.desired_end}` : "-"}</td>
                <td>{r.created_at.slice(0, 10)}</td>
                <td><StatusTag status={r.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
