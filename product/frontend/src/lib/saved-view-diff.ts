/** Structured criteria equality only. No financial results, labels or server cursors accepted. */
import { savedDefinition, type SavedDefinition } from "@/lib/saved-views";
export const diffFields = [
  "q",
  "supplier",
  "contract_source_id",
  "invoice_source_id",
  "invoice_document_id",
  "currency",
  "outcome",
  "decision_status",
  "created_from",
  "created_to",
  "current",
  "needs_review",
  "missing_contract",
  "sort",
  "page_size",
] as const;
export type DiffField = (typeof diffFields)[number];
export type DiffStatus = "ADDED" | "REMOVED" | "CHANGED" | "UNCHANGED";
export type CriterionValue = string | number | boolean | null;
export type CriterionDifference = {
  field: DiffField;
  before: CriterionValue;
  after: CriterionValue;
  status: DiffStatus;
};
function canonical(value: unknown, demo: boolean) {
  const d = savedDefinition(value, demo);
  // Missing/false current and missing-contract both mean unrestricted. Review defaults differ by route.
  const criteria = {
    ...d.criteria,
    current: d.criteria.current ?? false,
    missing_contract: d.criteria.missing_contract ?? false,
  };
  Object.freeze(criteria);
  return Object.freeze({ ...d, criteria });
}
function values(d: SavedDefinition): Record<DiffField, CriterionValue> {
  return Object.fromEntries(
    diffFields.map((field) => [
      field,
      field === "page_size" ? d.page_size : (d.criteria[field] ?? null),
    ]),
  ) as Record<DiffField, CriterionValue>;
}
export function definitionKey(value: unknown, demo = false) {
  const d = canonical(value, demo),
    v = values(d);
  return JSON.stringify([
    d.view_type,
    d.format_version,
    ...diffFields.map((f) => v[f]),
  ]);
}
export function compareSavedCriteria(
  before: unknown,
  after: unknown,
  demo = false,
) {
  const saved = canonical(before, demo),
    current = canonical(after, demo);
  if (
    saved.view_type !== current.view_type ||
    saved.format_version !== current.format_version
  )
    throw Error(
      "Incompatible saved view type or format. No replacement is allowed.",
    );
  const a = values(saved),
    b = values(current);
  const rows = diffFields.map((field): CriterionDifference => ({
    field,
    before: a[field],
    after: b[field],
    status:
      a[field] === b[field]
        ? "UNCHANGED"
        : a[field] === null
          ? "ADDED"
          : b[field] === null
            ? "REMOVED"
            : "CHANGED",
  }));
  const counts = { ADDED: 0, REMOVED: 0, CHANGED: 0, UNCHANGED: 0 };
  for (const row of rows) counts[row.status]++;
  return {
    saved,
    current,
    rows,
    counts,
    hasChanges: rows.some((r) => r.status !== "UNCHANGED"),
  };
}
export type CriteriaComparison = ReturnType<typeof compareSavedCriteria>;
export type SourceLabels = {
  organization_id: string;
  user_id: string;
  values: Record<string, string>;
};
