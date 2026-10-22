/** Query-edit actions only. No financial rule, association or decision is changed. */
import type { ExceptionQuery } from "@/lib/server-exceptions";
import {
  validatedCriteria,
  viewDefaults,
  type ExceptionView,
} from "@/lib/exception-view-url";
const controls = {
  q: "search",
  supplier: "supplier",
  contract_source_id: "contract",
  invoice_source_id: "invoice",
  invoice_document_id: "invoice document",
  currency: "currency",
  outcome: "outcome",
  decision_status: "decision status",
  created_from: "created from",
  created_to: "created before",
  current: "current assessments",
  needs_review: "needs review",
  missing_contract: "missing contract",
} as const;
export type RemovableCriterion = keyof typeof controls;
export type CriteriaTransition = {
  org: string;
  criteria: string;
  status: "pending" | "failed" | "succeeded";
  label: string;
  result: string;
};
export function criterionAction(
  filters: ExceptionQuery,
  field: RemovableCriterion,
  view: ExceptionView,
) {
  if (!Object.hasOwn(controls, field))
    throw Error("Criterion cannot be removed.");
  const f = validatedCriteria(filters, view),
    value = f[field],
    defaults = viewDefaults(view);
  if (
    value === undefined ||
    value === "" ||
    value === defaults[field] ||
    (value === false && field !== "needs_review")
  )
    return null;
  const restore = field === "needs_review" && view === "review";
  return {
    field,
    label: restore
      ? "Restore default needs review filter"
      : `Remove ${controls[field]} filter`,
    result: restore
      ? "Needs review default restored."
      : `${controls[field][0].toUpperCase() + controls[field].slice(1)} filter removed.`,
  };
}
export function withoutCriterion(
  filters: ExceptionQuery,
  field: RemovableCriterion,
  view: ExceptionView,
): ExceptionQuery {
  if (!criterionAction(filters, field, view))
    throw Error("Criterion is not an explicit removable filter.");
  const next = { ...filters };
  delete next[field];
  // Removing the review override reinstates its existing route default, never a wider implicit query.
  if (field === "needs_review")
    next.needs_review = viewDefaults(view).needs_review;
  return validatedCriteria(next, view);
}
