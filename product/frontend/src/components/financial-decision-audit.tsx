"use client";
import { useEffect, useState } from "react";
import type { Assessment } from "@/lib/financial";
import type {
  FinancialAuditPage,
  WorkspaceGateway,
} from "@/lib/product-workspace";

/** The current decision is joined to its actual PostgreSQL-triggered audit target ID. */
export function FinancialDecisionAudit({
  gateway,
  orgId,
  detail,
  demo,
}: {
  gateway: WorkspaceGateway;
  orgId: string;
  detail: Assessment;
  demo: boolean;
}) {
  const key = `${orgId}:${detail.decision_id}`;
  const [state, setState] = useState<{
    key: string;
    page?: FinancialAuditPage;
    error?: string;
  } | null>(null);
  useEffect(() => {
    if (!detail.decision_id || !gateway.audit) return;
    const controller = new AbortController();
    void gateway
      .audit(orgId, controller.signal)
      .then((page) => {
        if (!controller.signal.aborted) setState({ key, page });
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setState({
            key,
            error:
              "Financial audit is unavailable. The decision’s actor and reason have not been verified.",
          });
      });
    return () => controller.abort();
  }, [gateway, orgId, detail.decision_id, key]);
  if (!detail.decision_id || !gateway.audit) return null;
  const current = state?.key === key ? state : null;
  const entry = current?.page?.items.find(
    (row) =>
      row.target_id === detail.decision_id &&
      row.detail.table === "financial_finding_decisions" &&
      row.action === `finding.${detail.status}`,
  );
  return (
    <div className="p-decision-journal">
      <h3>Current financial decision journal</h3>
      <p>
        {demo
          ? "Synthetic journal — browser memory only; no PostgreSQL persistence."
          : "Read from the existing organization financial audit; separate from proof-package review."}
      </p>
      {!current ? (
        <p role="status">Loading financial decision audit…</p>
      ) : current.error ? (
        <p role="alert">{current.error}</p>
      ) : entry ? (
        <article>
          <strong>{entry.action}</strong>
          <p>
            {typeof entry.detail.reason === "string"
              ? entry.detail.reason
              : "Reason not returned by audit"}
          </p>
          <dl>
            <dt>Decision ID</dt>
            <dd>{entry.target_id}</dd>
            <dt>Actor ID</dt>
            <dd>{entry.actor_id}</dd>
            <dt>Recorded at</dt>
            <dd>
              <time dateTime={entry.created_at}>{entry.created_at}</time>
            </dd>
            <dt>Audit ID</dt>
            <dd>{entry.id}</dd>
          </dl>
        </article>
      ) : (
        <p>
          No matching decision audit was found in this loaded window. This is
          not proof of missing database history.
        </p>
      )}
      {current?.page && (
        <small>
          Latest {current.page.items.length} of {current.page.total}{" "}
          organization audit entries loaded. Earlier decisions are not inferred
          from a current decision ID.
        </small>
      )}
    </div>
  );
}
