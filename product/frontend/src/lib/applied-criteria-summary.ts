/** Criteria-only presentation. Never accepts a result page, decision or evidence. */
import type { RemovableCriterion } from "@/lib/criteria-removal";
import type { ExceptionQuery } from "@/lib/server-exceptions";
import {
  absoluteViewLink,
  readViewSearch,
  validatedCriteria,
  viewDefaults,
  viewPath,
  type ExceptionView,
} from "@/lib/exception-view-url";
export const MAX_SUMMARY_TEXT = 12000;
export type CriteriaLabels = {
  organization: string;
  invoice?: string;
  contract?: string;
  document?: string;
};
export type CriteriaLine = {
  name: string;
  value: string;
  criterion?: RemovableCriterion;
};
const safeLabel = (value: string | undefined, fallback: string) =>
  value &&
  value.length <= 512 &&
  !/[\u0000-\u001f\u007f\u2028\u2029\u202a-\u202e\u2066-\u2069]/.test(value) &&
  !/^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(value)
    ? value
    : fallback;
export function criteriaLines(
  filters: ExceptionQuery,
  limit: number,
  view: ExceptionView,
  labels: CriteriaLabels,
  demo: boolean,
): CriteriaLine[] {
  const f = validatedCriteria(filters, view);
  if (
    Object.values(f).some(
      (value) =>
        typeof value === "string" &&
        /[\u2028\u2029\u202a-\u202e\u2066-\u2069]/.test(value),
    )
  )
    throw Error("Criteria cannot be represented as safe structured text.");
  // Reuse the existing size and criteria validation, not another financial filter model.
  viewPath("00000000-0000-4000-8000-000000000001", f, limit, view, demo);
  const lines: CriteriaLine[] = [
    {
      name: "Organization",
      value: safeLabel(
        labels.organization,
        "Authorized organization label unavailable",
      ),
    },
  ];
  if (f.q) lines.push({ name: "Search text", criterion: "q", value: f.q });
  if (f.supplier)
    lines.push({
      name: "Recorded supplier name",
      criterion: "supplier",
      value: safeLabel(f.supplier, "Recorded supplier name unavailable"),
    });
  if (f.contract_source_id)
    lines.push({
      name: "Approved-association contract filter",
      criterion: "contract_source_id",
      value: safeLabel(labels.contract, "Selected contract label unavailable"),
    });
  if (f.invoice_source_id)
    lines.push({
      name: "Invoice source document",
      criterion: "invoice_source_id",
      value: safeLabel(labels.invoice, "Selected invoice label unavailable"),
    });
  if (f.invoice_document_id)
    lines.push({
      name: "Invoice document constraint",
      criterion: "invoice_document_id",
      value: safeLabel(labels.document, "Selected document label unavailable"),
    });
  if (f.currency)
    lines.push({
      name: "Currency filter",
      criterion: "currency",
      value: f.currency,
    });
  const outcomes: Record<string, string> = {
    POTENTIAL_LEAKAGE: "Potential leakage",
    NEEDS_REVIEW: "Needs review",
    NO_OVERCHARGE: "No overcharge",
    UNDERCHARGE: "Undercharge",
  };
  const decisions: Record<string, string> = {
    confirmed: "Confirmed",
    false_positive: "Dismissed (false positive)",
    needs_review: "Further review requested",
    unrecorded: "No recorded decision",
  };
  if (f.outcome)
    lines.push({
      name: "Outcome filter",
      criterion: "outcome",
      value: outcomes[f.outcome],
    });
  if (f.decision_status)
    lines.push({
      name: "Recorded decision filter",
      criterion: "decision_status",
      value: decisions[f.decision_status],
    });
  if (f.created_from)
    lines.push({
      name: "Created from (inclusive, UTC)",
      criterion: "created_from",
      value: f.created_from,
    });
  if (f.created_to)
    lines.push({
      name: "Created before (exclusive, UTC)",
      criterion: "created_to",
      value: f.created_to,
    });
  lines.push(
    {
      name: "Current assessments filter",
      criterion: "current",
      value: f.current ? "Current only" : "Not restricted",
    },
    {
      name: "Needs human review filter",
      criterion: "needs_review",
      value: f.needs_review ? "Yes" : "Not restricted",
    },
    {
      name: "Missing contract filter",
      criterion: "missing_contract",
      value: f.missing_contract
        ? "No unique association returned"
        : "Not restricted",
    },
  );
  const sorts: Record<string, string> = {
    newest: "Newest first",
    oldest: "Oldest first",
    amount_high: "Potential high–low within currency",
    amount_low: "Potential low–high within currency",
    outcome: "Outcome A–Z",
  };
  lines.push(
    { name: "Sort", value: sorts[f.sort!] },
    { name: "Page size", value: String(limit) },
  );
  return lines;
}
export function noOptionalCriteria(
  filters: ExceptionQuery,
  view: ExceptionView,
) {
  const f = validatedCriteria(filters, view),
    defaults = viewDefaults(view);
  return Object.entries(f).every(
    ([k, v]) =>
      v === undefined ||
      v === "" ||
      v === defaults[k as keyof ExceptionQuery] ||
      (v === false && k !== "needs_review"),
  );
}
export function summaryText(
  org: string,
  filters: ExceptionQuery,
  limit: number,
  view: ExceptionView,
  labels: CriteriaLabels,
  demo: boolean,
  link: string,
) {
  const url = new URL(link),
    restored = readViewSearch(url.search, view, demo);
  const canonical = absoluteViewLink(
    url.origin,
    viewPath(org, filters, limit, view, demo),
  );
  if (link !== canonical || restored.org !== org)
    throw Error("Summary and view link do not match.");
  const lines = criteriaLines(filters, limit, view, labels, demo);
  if (
    lines.some((line) =>
      /[\u2028\u2029\u202a-\u202e\u2066-\u2069]/.test(line.value),
    )
  )
    throw Error("Criteria cannot be represented as safe structured text.");
  const text = [
    demo ? "FINLEAK — Synthetic exception view" : "FINLEAK — Exception view",
    "",
    ...lines.map((l) => `${l.name}: ${l.value}`),
    "",
    `View link: ${link}`,
    "",
    "This link restores search criteria against current authorized data. It does not grant access or certify financial results.",
    "Supplier names are recorded strings, not verified legal identities. Document labels are not invoice numbers. Filters are not individual decisions or certifications of currentness.",
    "Criteria and document labels can be sensitive; share only with the intended authorized audience.",
  ].join("\n");
  if (text.length > MAX_SUMMARY_TEXT)
    throw Error("Summary exceeds the permitted length.");
  // No silent truncation or unpaired Unicode in clipboard output.
  encodeURIComponent(text);
  return text;
}
