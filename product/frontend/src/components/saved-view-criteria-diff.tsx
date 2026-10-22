"use client";
import { useEffect, useId, useRef } from "react";
import {
  criteriaLines,
  type CriteriaLabels,
} from "@/lib/applied-criteria-summary";
import type { SavedDefinition } from "@/lib/saved-views";
import type {
  CriteriaComparison,
  CriterionDifference,
  DiffField,
  SourceLabels,
} from "@/lib/saved-view-diff";
const names: Record<DiffField, string> = {
  q: "Search text",
  supplier: "Recorded supplier name",
  contract_source_id: "Approved-association contract filter",
  invoice_source_id: "Invoice source document",
  invoice_document_id: "Invoice document constraint",
  currency: "Currency filter",
  outcome: "Outcome filter",
  decision_status: "Recorded decision filter",
  created_from: "Created from (inclusive, UTC)",
  created_to: "Created before (exclusive, UTC)",
  current: "Current assessments filter",
  needs_review: "Needs human review filter",
  missing_contract: "Missing contract filter",
  sort: "Sort",
  page_size: "Page size",
};
const documents = new Set([
  "contract_source_id",
  "invoice_source_id",
  "invoice_document_id",
]);
function formatted(
  d: SavedDefinition,
  labels: SourceLabels | undefined,
  demo: boolean,
) {
  const known = (
    field: "contract_source_id" | "invoice_source_id" | "invoice_document_id",
  ) => {
    const id = d.criteria[field];
    return id ? labels?.values[`${field}:${id}`] : undefined;
  };
  const display: CriteriaLabels = {
    organization: "Current authorized organization",
    contract: known("contract_source_id"),
    invoice: known("invoice_source_id"),
    document: known("invoice_document_id"),
  };
  const lines = criteriaLines(
    d.criteria,
    d.page_size,
    d.view_type,
    display,
    demo,
  );
  return Object.fromEntries(
    lines
      .filter((l) => l.name !== "Organization")
      .map((l) => [
        l.criterion ?? (l.name === "Sort" ? "sort" : "page_size"),
        l.value,
      ]),
  );
}
export function SavedViewCriteriaDiff({
  name,
  revision,
  comparison,
  valid,
  busy,
  reason,
  versionChanged,
  labels,
  demo,
  onConfirm,
  onCancel,
  onReview,
  reviewAvailable = true,
}: {
  name: string;
  revision: number;
  comparison: CriteriaComparison;
  valid: boolean;
  busy: boolean;
  reason?: string;
  versionChanged?: number;
  labels?: SourceLabels;
  demo: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  onReview: () => void;
  reviewAvailable?: boolean;
}) {
  const id = useId(),
    heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus();
  }, [comparison]);
  const before = formatted(comparison.saved, labels, demo),
    after = formatted(comparison.current, labels, demo);
  const table = (rows: CriterionDifference[], label: string) => (
    <div className="p-diff-table">
      <table aria-label={label}>
        <thead>
          <tr>
            <th>Criterion</th>
            <th>Saved criteria</th>
            <th>Current applied criteria</th>
            <th>Change</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.field}>
              <th scope="row">
                {names[r.field]}
                {documents.has(r.field) && r.status === "CHANGED" && (
                  <small>
                    Different source identity; document labels may be identical.
                  </small>
                )}
              </th>
              <td>{before[r.field] ?? "Not selected"}</td>
              <td>{after[r.field] ?? "Not selected"}</td>
              <td>
                <span className={`p-diff-status ${r.status.toLowerCase()}`}>
                  {r.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
  return (
    <section className="p-criteria-diff" aria-labelledby={id}>
      <h4 id={id} ref={heading} tabIndex={-1}>
        Review saved view changes
      </h4>
      <p>
        <strong>{name}</strong> · Re-read version {revision}
      </p>
      <p>Criteria only. No financial results are compared or stored.</p>
      {versionChanged !== undefined && (
        <p role="status">
          The saved view changed from version {versionChanged} to {revision}.
          Review this new comparison before confirming.
        </p>
      )}
      <p className="p-diff-counts">
        {comparison.counts.ADDED} added · {comparison.counts.REMOVED} removed ·{" "}
        {comparison.counts.CHANGED} changed
      </p>
      {!comparison.hasChanges ? (
        <p role="status">
          <strong>No changes to save</strong>
        </p>
      ) : (
        table(
          comparison.rows.filter((r) => r.status !== "UNCHANGED"),
          "Changed criteria comparison",
        )
      )}
      <details>
        <summary>Unchanged criteria ({comparison.counts.UNCHANGED})</summary>
        {table(
          comparison.rows.filter((r) => r.status === "UNCHANGED"),
          "Unchanged criteria comparison",
        )}
      </details>
      {!valid && (
        <p role="alert">
          {reason ??
            "Criteria or context changed during review. Review the latest criteria again before replacement."}
        </p>
      )}
      <div className="p-diff-actions">
        <button
          disabled={!valid || !comparison.hasChanges || busy}
          onClick={onConfirm}
        >
          Confirm replacement
        </button>
        <button disabled={busy} onClick={onCancel}>
          Cancel
        </button>
        {!valid && (
          <button disabled={busy || !reviewAvailable} onClick={onReview}>
            Review changes again
          </button>
        )}
      </div>
    </section>
  );
}
