/** Criteria-only links. Encoding is public text, never encryption or authorization. */
import type { ExceptionQuery } from "@/lib/server-exceptions";
export type ExceptionView = "anomalies" | "review";
export type RestoredView = {
  org: string;
  filters: ExceptionQuery;
  limit: number;
  assessment: string;
  versioned: boolean;
};
export const MAX_VIEW_URL = 4096;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const fields = [
  "q",
  "supplier",
  "invoice_source_id",
  "invoice_document_id",
  "contract_source_id",
  "currency",
  "outcome",
  "decision_status",
  "created_from",
  "created_to",
  "current",
  "needs_review",
  "missing_contract",
  "sort",
] as const;
const flags = new Set(["current", "needs_review", "missing_contract"]);
const ids = new Set([
  "invoice_source_id",
  "invoice_document_id",
  "contract_source_id",
]);
const sorts = ["newest", "oldest", "amount_high", "amount_low", "outcome"];
const outcomes = [
  "POTENTIAL_LEAKAGE",
  "NEEDS_REVIEW",
  "NO_OVERCHARGE",
  "UNDERCHARGE",
];
const decisions = ["confirmed", "false_positive", "needs_review", "unrecorded"];
const invalid = (): never => {
  throw new Error("Invalid or unsupported view link. No search was started.");
};
export function viewDefaults(view: ExceptionView): ExceptionQuery {
  return { sort: "newest", needs_review: view === "review" };
}
function canonicalId(value: string) {
  if (!uuid.test(value)) return invalid();
  return value.toLowerCase();
}
function dateValue(value: string) {
  if (
    !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?(?:Z|[+-]\d{2}:\d{2})$/.test(
      value,
    )
  )
    return invalid();
  if (
    value.startsWith("0000") ||
    Number(value.slice(11, 13)) > 23 ||
    Number(value.slice(14, 16)) > 59 ||
    Number(value.slice(17, 19)) > 59
  )
    return invalid();
  const parsed = new Date(value);
  // Reject dates which JS normalizes, e.g. February 30, and invalid offsets/times.
  const day = value.slice(0, 10),
    calendar = new Date(day + "T00:00:00Z");
  if (
    !Number.isFinite(parsed.valueOf()) ||
    !Number.isFinite(calendar.valueOf()) ||
    calendar.toISOString().slice(0, 10) !== day
  )
    return invalid();
  return parsed.toISOString();
}
export function validatedCriteria(
  filters: ExceptionQuery,
  view: ExceptionView,
): ExceptionQuery {
  const result: ExceptionQuery = viewDefaults(view);
  for (const name of fields) {
    const value = filters[name];
    if (value === undefined || value === "") continue;
    if (flags.has(name)) {
      if (typeof value !== "boolean") return invalid();
      Object.assign(result, { [name]: value });
      continue;
    }
    if (typeof value !== "string" || /[\u0000-\u001f\u007f]/.test(value))
      return invalid();
    try {
      encodeURIComponent(value);
    } catch {
      return invalid();
    }
    let text = value;
    if (ids.has(name)) text = canonicalId(value);
    if (name === "q") {
      if (value.length > 160) return invalid();
      text = value.trim();
    }
    if (name === "supplier" && (value.length < 1 || value.length > 120))
      return invalid();
    if (name === "currency" && !/^[A-Z]{3}$/.test(value)) return invalid();
    if (name === "outcome" && !outcomes.includes(value)) return invalid();
    if (name === "decision_status" && !decisions.includes(value))
      return invalid();
    if (name === "sort" && !sorts.includes(value)) return invalid();
    if (name === "created_from" || name === "created_to")
      text = dateValue(value);
    Object.assign(result, { [name]: text });
  }
  if (result.missing_contract && result.contract_source_id) return invalid();
  if (
    result.created_from &&
    result.created_to &&
    result.created_from >= result.created_to
  )
    return invalid();
  return result;
}
function pageSize(value: number, demo: boolean) {
  if (!(demo ? [2, 20, 50, 100] : [20, 50, 100]).includes(value))
    return invalid();
  return value;
}
export function readViewSearch(
  search: string,
  view: ExceptionView,
  demo: boolean,
): RestoredView {
  if (search.length > MAX_VIEW_URL) return invalid();
  const params = new URLSearchParams();
  if (search.endsWith("&") || search.includes("&&")) return invalid();
  for (const pair of search.replace(/^\?/, "").split("&").filter(Boolean)) {
    const index = pair.indexOf("=");
    if (index < 0) return invalid();
    let key: string, value: string;
    try {
      key = decodeURIComponent(pair.slice(0, index).replace(/\+/g, " "));
      value = decodeURIComponent(pair.slice(index + 1).replace(/\+/g, " "));
    } catch {
      return invalid();
    }
    if (params.has(key) || /[\u0000-\u001f\u007f]/.test(value))
      return invalid();
    if (
      ![
        "org",
        "invoice",
        "assessment",
        "ev",
        "ev_limit",
        ...fields.map((f) => `ev_${f}`),
      ].includes(key)
    )
      return invalid();
    params.set(key, value);
  }
  const versioned = params.has("ev");
  if (versioned && !params.has("org")) return invalid();
  if (
    (versioned && params.get("ev") !== "1") ||
    (!versioned && [...params.keys()].some((k) => k.startsWith("ev_")))
  )
    return invalid();
  if (versioned && params.has("invoice")) return invalid();
  const filters: ExceptionQuery = {};
  for (const name of fields) {
    if (!params.has(`ev_${name}`)) continue;
    const value = params.get(`ev_${name}`)!;
    if (!value) return invalid();
    if (flags.has(name)) {
      if (value !== "true" && value !== "false") return invalid();
      Object.assign(filters, { [name]: value === "true" });
    } else Object.assign(filters, { [name]: value });
  }
  if (!versioned && params.has("invoice"))
    filters.invoice_source_id = canonicalId(params.get("invoice")!);
  const limitText = params.get("ev_limit");
  if (limitText !== null && !/^(2|20|50|100)$/.test(limitText))
    return invalid();
  return {
    org: params.has("org") ? canonicalId(params.get("org")!) : "",
    filters: validatedCriteria(filters, view),
    limit: pageSize(
      limitText === null ? (demo ? 2 : 20) : Number(limitText),
      demo,
    ),
    assessment: params.has("assessment")
      ? canonicalId(params.get("assessment")!)
      : "",
    versioned,
  };
}
export function viewPath(
  org: string,
  filters: ExceptionQuery,
  limit: number,
  view: ExceptionView,
  demo: boolean,
) {
  const value = validatedCriteria(filters, view),
    defaults = viewDefaults(view);
  const params = new URLSearchParams({ ev: "1", org: canonicalId(org) });
  for (const name of fields) {
    const field = value[name];
    if (
      field === undefined ||
      field === "" ||
      field === defaults[name] ||
      (field === false && name !== "needs_review")
    )
      continue;
    params.set(`ev_${name}`, String(field));
  }
  if (limit !== (demo ? 2 : 20))
    params.set("ev_limit", String(pageSize(limit, demo)));
  else pageSize(limit, demo);
  const path = `${demo ? "/demo" : ""}/${view}?${params}`;
  if (path.length > MAX_VIEW_URL) return invalid();
  return path;
}
export function absoluteViewLink(origin: string, path: string) {
  if (!path.startsWith("/") || path.startsWith("//")) return invalid();
  const url = new URL(origin);
  if (
    !["https:", "http:"].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.origin !== origin
  )
    return invalid();
  const target = new URL(path, origin);
  if (
    target.origin !== origin ||
    target.hash ||
    !/^\/(?:demo\/)?(?:anomalies|review)$/.test(target.pathname)
  )
    return invalid();
  readViewSearch(
    target.search,
    target.pathname.endsWith("/review") ? "review" : "anomalies",
    target.pathname.startsWith("/demo/"),
  );
  const result = origin + path;
  if (result.length > MAX_VIEW_URL) return invalid();
  return result;
}
export function searchFromRecord(
  query: Record<string, string | string[] | undefined>,
) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query))
    for (const item of Array.isArray(value)
      ? value
      : value === undefined
        ? []
        : [value])
      params.append(key, item);
  return params.size ? `?${params}` : "";
}
