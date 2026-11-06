import type { Company } from "../../lib/types";

export default function CompanyCard({ company }: { company: Company }) {
  return (
    <dl className="ind-company">
      <div><dt>Company</dt><dd>{company.legal_name}</dd></div>
      <div><dt>UEI</dt><dd><code>{company.uei}</code></dd></div>
      <div><dt>CAGE</dt><dd><code>{company.cage}</code></dd></div>
    </dl>
  );
}
