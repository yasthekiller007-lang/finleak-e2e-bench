"use client";
import { useRef, useState } from "react";
import {
  criterionAction,
  type RemovableCriterion,
  type CriteriaTransition,
} from "@/lib/criteria-removal";
import type { ExceptionQuery } from "@/lib/server-exceptions";
import {
  criteriaLines,
  noOptionalCriteria,
  summaryText,
  type CriteriaLabels,
} from "@/lib/applied-criteria-summary";
import type { ExceptionView } from "@/lib/exception-view-url";
export type AppliedCriteria = {
  org: string;
  filters: ExceptionQuery;
  limit: number;
  labels?: Partial<Pick<CriteriaLabels, "invoice" | "contract" | "document">>;
};
export function AppliedCriteriaSummary({
  applied,
  org,
  organization,
  view,
  demo,
  coherent,
  failed,
  makeViewLink,
  onRemove,
  canRemove = false,
  transition,
  onRestore,
}: {
  applied: AppliedCriteria | null;
  org: string;
  organization: string;
  view: ExceptionView;
  demo: boolean;
  coherent: boolean;
  failed: boolean;
  makeViewLink: (f: ExceptionQuery, limit: number) => string;
  onRemove?: (field: RemovableCriterion) => boolean;
  canRemove?: boolean;
  transition?: CriteriaTransition | null;
  onRestore?: () => void;
}) {
  const heading = useRef<HTMLHeadingElement>(null);
  const snapshot = applied?.org === org ? applied : null;
  const [copy, setCopy] = useState<{
    key: string;
    state: "pending" | "copied" | "error";
  } | null>(null);
  const labels: CriteriaLabels = { organization, ...snapshot?.labels };
  let lines: ReturnType<typeof criteriaLines> = [],
    text: string | null = null,
    invalid = false,
    optional = false;
  if (snapshot) {
    try {
      lines = criteriaLines(
        snapshot.filters,
        snapshot.limit,
        view,
        labels,
        demo,
      );
      optional = noOptionalCriteria(snapshot.filters, view);
      text = summaryText(
        org,
        snapshot.filters,
        snapshot.limit,
        view,
        labels,
        demo,
        makeViewLink(snapshot.filters, snapshot.limit),
      );
    } catch {
      invalid = true;
    }
  }
  const copyKey = JSON.stringify([
    org,
    snapshot?.filters,
    snapshot?.limit,
    labels,
  ]);
  return (
    <section
      className="p-criteria-summary"
      aria-label="Applied criteria summary"
    >
      <div className="p-criteria-heading">
        <h3 ref={heading} tabIndex={-1}>
          Applied criteria
        </h3>
        <button
          disabled={
            !coherent || !snapshot || invalid || copy?.state === "pending"
          }
          onClick={async () => {
            if (!text) return;
            setCopy({ key: copyKey, state: "pending" });
            try {
              if (!navigator.clipboard?.writeText) throw Error();
              await navigator.clipboard.writeText(text);
              setCopy({ key: copyKey, state: "copied" });
            } catch {
              setCopy({ key: copyKey, state: "error" });
            }
          }}
        >
          Copy summary &amp; link
        </button>
      </div>
      <p>
        {!snapshot
          ? failed
            ? "Query failed. No criteria have been applied successfully."
            : "Waiting for the first successful query."
          : failed
            ? "Query failed. Showing the last successful criteria; copy is disabled."
            : !coherent
              ? "Criteria changed or a read is pending. Showing the last successful criteria; copy is disabled."
              : "Criteria from the successful query. These filters do not certify financial results."}
      </p>
      {invalid ? (
        <p role="alert">
          Summary or link unavailable: criteria cannot be represented safely.
          Nothing was copied.
        </p>
      ) : (
        snapshot && (
          <>
            <div className="p-criteria-lines">
              <dl aria-busy={!coherent}>
                {lines.map((l) => {
                  const action =
                    l.criterion && snapshot
                      ? criterionAction(snapshot.filters, l.criterion, view)
                      : null;
                  return (
                    <div key={l.name}>
                      <dt>{l.name}</dt>
                      <dd>{l.value}</dd>
                      {onRemove && action && (
                        <button
                          className="p-criterion-remove"
                          aria-label={action.label}
                          title={action.label}
                          disabled={
                            !coherent ||
                            invalid ||
                            !canRemove ||
                            copy?.state === "pending"
                          }
                          onClick={() => {
                            if (onRemove(action.field))
                              heading.current?.focus();
                          }}
                        >
                          ×
                        </button>
                      )}
                    </div>
                  );
                })}
              </dl>
            </div>
            {optional && <p>No optional filters selected.</p>}
          </>
        )
      )}
      {transition?.org === org && (
        <p
          className="p-criteria-transition"
          role={transition.status === "failed" ? "alert" : "status"}
        >
          {transition.status === "pending"
            ? `Requested change: ${transition.label}. Waiting for server confirmation; last applied criteria are unchanged.`
            : transition.status === "failed"
              ? `Requested change failed: ${transition.label}. Fields show the requested criteria. Last applied criteria and URL are unchanged; retry the query or restore them.`
              : `${transition.result} Server results refreshed.`}
          {transition.status === "failed" && onRestore && (
            <button
              disabled={!canRemove}
              onClick={() => {
                onRestore();
                heading.current?.focus();
              }}
            >
              Restore last applied criteria
            </button>
          )}
        </p>
      )}
      {snapshot && lines.some((l) => l.value.endsWith("label unavailable")) && (
        <p>
          Some labels are unavailable. Selections are kept without replacement;
          use the document selectors to retry available label reads.
        </p>
      )}
      {coherent && copy?.key === copyKey && copy.state === "copied" && (
        <p role="status">
          Summary and view link copied. Permissions are unchanged.
        </p>
      )}
      {coherent && copy?.key === copyKey && copy.state === "error" && (
        <p role="alert">
          Summary was not copied. Clipboard access was refused or unavailable;
          retry Copy summary &amp; link.
        </p>
      )}
      {demo && (
        <small>Synthetic criteria only; no live financial results.</small>
      )}
      <small>
        Recorded supplier names are not verified legal identities. Document
        names are not verified invoice numbers. A contract filter does not
        approve an association; a decision filter is not an individual decision.
      </small>
    </section>
  );
}
