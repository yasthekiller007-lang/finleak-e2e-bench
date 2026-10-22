import Link from "next/link";
import type { Assessment } from "@/lib/financial";
import type { WorkspaceData } from "@/lib/product-workspace";
import { contractName } from "@/lib/exception-workbench";

export function ExceptionInvestigation({
  detail,
  data,
  demo,
}: {
  detail: Assessment;
  data: WorkspaceData;
  demo: boolean;
}) {
  const context = detail.queue_context,
    inputs = detail.snapshot?.inputs ?? [];
  const ids = new Set(
    inputs.flatMap((row) => row.provenance.map((e) => e.document_id)),
  );
  const contract = context?.contract_source_id;
  return (
    <section
      className="p-card p-investigation"
      aria-label="Investigation context"
    >
      <div className="p-section-heading">
        <div>
          <p className="p-eyebrow">INVESTIGATION BRIEF</p>
          <h3>Trace the exception to its basis</h3>
        </div>
        <span className="p-subtle-tag">Recorded context</span>
      </div>
      <div className="p-comparison">
        <div>
          <h4>Contract basis</h4>
          <dl>
            <dt>Supplier party</dt>
            <dd>
              {context?.supplier_party ?? "Not recorded in assessment context"}
            </dd>
            <dt>Associated contract</dt>
            <dd>
              {contract
                ? `Document: ${contractName(data, contract)}`
                : "No unique approved association returned"}
            </dd>
            <dt>Contract references</dt>
            <dd>
              {context?.contract_references.length
                ? context.contract_references.join(" · ")
                : "Not returned"}
            </dd>
          </dl>
        </div>
        <div>
          <h4>Assessment basis</h4>
          <dl>
            <dt>Reason code</dt>
            <dd>{detail.reason_code}</dd>
            <dt>Billing scope</dt>
            <dd>{detail.scope_key}</dd>
            <dt>Source documents cited</dt>
            <dd>{ids.size}</dd>
            <dt>Current decision</dt>
            <dd>{detail.decision_id ?? "No decision recorded"}</dd>
          </dl>
        </div>
      </div>
      <div className="p-investigation-notes">
        <strong>
          {detail.stale
            ? "Reassessment required"
            : detail.potential === null
              ? "Resolve evidence gaps before deciding"
              : "Human judgment required"}
        </strong>
        <p>
          {detail.snapshot?.coverage ??
            "Coverage has not been returned. Do not infer a complete contract or invoice audit."}
        </p>
        <p>
          References describe the frozen assessment. Currentness and recorded
          decisions are shown separately. Proof-package review remains a
          separate operation.
        </p>
      </div>
      {inputs.length > 0 && (
        <details className="p-uncertainty">
          <summary>
            Reviewed explanations & uncertainty resolutions ({inputs.length})
          </summary>
          {inputs.map((row) => (
            <article key={row.id}>
              <strong>
                {row.kind.replaceAll("_", " ")} · {row.state}
              </strong>
              <p>{row.payload.reason || "No review reason returned"}</p>
              <p>
                {row.payload.uncertainty_resolution ||
                  "No uncertainty resolution returned"}
              </p>
            </article>
          ))}
        </details>
      )}
      {!demo && (
        <p className="p-investigation-link">
          <Link className="p-text-link" href="/leakage-cases">
            Open existing fact & proof review workspace →
          </Link>
          <small>Select the matching organization in that workspace.</small>
        </p>
      )}
    </section>
  );
}
