import {
  liveSavedViewsGateway,
  type SavedViewsGateway,
} from "@/lib/saved-views";
import type { FacetOption } from "@/lib/business-facets";
import {
  facetsPath,
  type FacetKind,
  type FacetPage,
} from "@/lib/business-facets";
import type { Assessment, Source, Summary } from "@/lib/financial";
import type { DocumentPage, FinancialDocument } from "@/lib/documents";
import type { Page, ProofEvent, ProofPackage } from "@/lib/proof";
import {
  exceptionsPath,
  type ExceptionQuery,
  type ExceptionPage,
} from "@/lib/server-exceptions";

export type ProductView =
  "dashboard" | "invoices" | "contracts" | "anomalies" | "review";
export type ResultPage<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};
export type WorkspaceData = {
  summary: Summary & {
    potential_by_rule?: Record<string, Record<string, string>>;
  };
  documents: DocumentPage;
  sources: ResultPage<Source>;
  assessments: ResultPage<Assessment>;
};
export type ProofDetail = {
  proof: ProofPackage | null;
  history: Page<ProofEvent> | null;
  hasMorePackages: boolean;
};
export type Decision = {
  status: "confirmed" | "false_positive" | "needs_review";
  reason: string;
  expected_decision: string | null;
};
export type FinancialAuditEntry = {
  id: string;
  actor_id: string;
  action: string;
  target_id: string;
  created_at: string;
  detail: Record<string, unknown>;
};
export type FinancialAuditPage = ResultPage<FinancialAuditEntry>;
export interface WorkspaceGateway {
  savedViews?: SavedViewsGateway;
  sourceLabel?(
    org: string,
    id: string,
    kind: "invoice" | "contract",
    signal: AbortSignal,
  ): Promise<FacetOption>;
  queryFacets?(
    org: string,
    filters: ExceptionQuery,
    facet: FacetKind,
    search: string,
    limit: number,
    after: string | null,
    signal: AbortSignal,
  ): Promise<FacetPage>;
  queryExceptions?(
    org: string,
    filters: ExceptionQuery,
    limit: number,
    after: string | null,
    signal: AbortSignal,
  ): Promise<ExceptionPage>;
  loadContext?(org: string, signal: AbortSignal): Promise<WorkspaceData>;
  sources?(
    org: string,
    offset: number,
    signal: AbortSignal,
  ): Promise<ResultPage<Source>>;
  audit?(org: string, signal: AbortSignal): Promise<FinancialAuditPage>;
  load(org: string, signal: AbortSignal): Promise<WorkspaceData>;
  documents(
    org: string,
    offset: number,
    signal: AbortSignal,
  ): Promise<DocumentPage>;
  assessments(
    org: string,
    offset: number,
    signal: AbortSignal,
  ): Promise<ResultPage<Assessment>>;
  assessment(org: string, id: string, signal: AbortSignal): Promise<Assessment>;
  proof(org: string, id: string, signal: AbortSignal): Promise<ProofDetail>;
  decide(
    org: string,
    id: string,
    decision: Decision,
    signal: AbortSignal,
  ): Promise<unknown>;
}

export class WorkspaceError extends Error {
  constructor(
    message: string,
    public status: number,
    public requestId: string | null = null,
    public code: string | null = null,
  ) {
    super(message);
  }
}

async function request<T>(
  org: string,
  path: string,
  signal: AbortSignal,
  body?: unknown,
): Promise<T> {
  const response = await fetch(
    `/api/organizations/${encodeURIComponent(org)}/${path}`,
    {
      method: body === undefined ? "GET" : "POST",
      cache: "no-store",
      credentials: "same-origin",
      signal: AbortSignal.any([signal, AbortSignal.timeout(30000)]),
      ...(body === undefined
        ? {}
        : {
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          }),
    },
  );
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    const message =
      response.status === 401
        ? "Your session has expired. Sign in again."
        : response.status === 409
          ? ["EXCEPTIONS_CHANGED", "FACETS_CHANGED"].includes(data?.error?.code)
            ? data.error.message
            : "This record changed. Refresh the assessment before making another decision."
          : (data?.error?.message ??
            "The workspace service is unavailable. Please retry.");
    throw new WorkspaceError(
      message,
      response.status,
      response.headers.get("X-Request-ID"),
      typeof data?.error?.code === "string" ? data.error.code : null,
    );
  }
  return response.json() as Promise<T>;
}

/** Existing same-origin BFF only. No token, tenant override or demo fallback. */
export const liveWorkspaceGateway: WorkspaceGateway = {
  savedViews: liveSavedViewsGateway,
  async sourceLabel(org, id, kind, signal) {
    const source = await request<Source>(
      org,
      `financial/sources/${encodeURIComponent(id)}`,
      signal,
    );
    if (source.id !== id || source.kind !== kind)
      throw new WorkspaceError("Selected source unavailable.", 404);
    const doc = await request<FinancialDocument>(
      org,
      `documents/${encodeURIComponent(source.document_id)}`,
      signal,
    );
    if (doc.organization_id !== org || doc.id !== source.document_id)
      throw new WorkspaceError("Selected source unavailable.", 404);
    return {
      value: id,
      label: doc.original_filename,
      document_id: doc.id,
      description:
        "Authorized current document label; not a certified reference.",
    };
  },
  queryFacets: (org, filters, facet, search, limit, after, signal) =>
    request(org, facetsPath(filters, facet, search, limit, after), signal),
  queryExceptions: (org, filters, limit, after, signal) =>
    request(org, exceptionsPath(filters, limit, after), signal),
  async loadContext(org, signal) {
    const [documents, sources] = await Promise.all([
      request<DocumentPage>(org, "documents?limit=100&offset=0", signal),
      request<ResultPage<Source>>(
        org,
        "financial/sources?limit=100&offset=0",
        signal,
      ),
    ]);
    return {
      summary: {
        potential_by_currency: {},
        counts: {},
        limited: false,
        coverage:
          "Summary not requested in exceptions view. Open the dashboard for authoritative financial aggregates.",
      },
      documents,
      sources,
      assessments: { items: [], total: 0, limit: 100, offset: 0 },
    };
  },
  sources: (org, offset, signal) =>
    request(org, `financial/sources?limit=100&offset=${offset}`, signal),
  audit: (org, signal) =>
    request(org, "financial/audit?limit=100&offset=0", signal),
  async load(org, signal) {
    const [summary, documents, sources, assessments] = await Promise.all([
      request<WorkspaceData["summary"]>(org, "financial/summary", signal),
      request<DocumentPage>(org, "documents?limit=100&offset=0", signal),
      request<ResultPage<Source>>(
        org,
        "financial/sources?limit=100&offset=0",
        signal,
      ),
      request<ResultPage<Assessment>>(
        org,
        "financial/evaluations?limit=100&offset=0",
        signal,
      ),
    ]);
    return { summary, documents, sources, assessments };
  },
  documents: (org, offset, signal) =>
    request(org, `documents?limit=100&offset=${offset}`, signal),
  assessments: (org, offset, signal) =>
    request(org, `financial/evaluations?limit=100&offset=${offset}`, signal),
  assessment: (org, id, signal) =>
    request(org, `financial/evaluations/${encodeURIComponent(id)}`, signal),
  async proof(org, id, signal) {
    const packages = await request<Page<ProofPackage>>(
      org,
      `proof/evaluations/${encodeURIComponent(id)}/packages?limit=100&offset=0`,
      signal,
    );
    if (!packages.items.length)
      return { proof: null, history: null, hasMorePackages: packages.has_more };
    const packageId = encodeURIComponent(packages.items[0].id);
    const [proof, history] = await Promise.all([
      request<ProofPackage>(org, `proof/packages/${packageId}`, signal),
      request<Page<ProofEvent>>(
        org,
        `proof/packages/${packageId}/history?limit=100&offset=0`,
        signal,
      ),
    ]);
    return { proof, history, hasMorePackages: packages.has_more };
  },
  decide: (org, id, body, signal) =>
    request(
      org,
      `financial/evaluations/${encodeURIComponent(id)}/decision`,
      signal,
      body,
    ),
};

export const viewLabels: Record<
  ProductView,
  { title: string; description: string }
> = {
  dashboard: {
    title: "Financial overview",
    description:
      "A clearer view of your spend. A stronger case for every finding.",
  },
  invoices: {
    title: "Invoices",
    description:
      "Follow each invoice from source document to reviewed financial evidence.",
  },
  contracts: {
    title: "Contracts",
    description: "The source of truth behind your financial assessments.",
  },
  anomalies: {
    title: "Anomalies",
    description:
      "Understand the discrepancy. Inspect the evidence. Make an informed decision.",
  },
  review: {
    title: "Human review",
    description:
      "Your judgment, backed by evidence. Every decision stays attributable.",
  },
};
export const isReviewNeeded = (a: Assessment) =>
  !a.stale &&
  (a.outcome === "NEEDS_REVIEW" ||
    (a.potential !== null &&
      a.status !== "confirmed" &&
      a.status !== "false_positive"));
export function assessmentLabel(a: Assessment) {
  return a.stale
    ? "Reassessment needed"
    : a.status === "confirmed"
      ? "Confirmed"
      : a.status === "false_positive"
        ? "Dismissed"
        : a.outcome === "NEEDS_REVIEW"
          ? "Evidence needed"
          : a.potential !== null
            ? "Needs review"
            : "No overcharge";
}
export function ruleLabel(rule: string) {
  const labels: Record<string, string> = {
    unit_price: "Unit price variance",
    fixed_fee: "Recurring / fixed fee",
    percentage_discount: "Unapplied discount",
  };
  return (
    rule
      .split("+")
      .map((part) => labels[part] ?? part.replaceAll("_", " "))
      .join(" + ") || "Recorded financial rules"
  );
}
export function documentFor(
  data: WorkspaceData,
  assessment: Assessment,
): FinancialDocument | undefined {
  const source = data.sources.items.find(
    (s) => s.id === assessment.invoice_source_id,
  );
  return data.documents.items.find((d) => d.id === source?.document_id);
}
export function linkedAssessments(data: WorkspaceData, documentId: string) {
  const ids = new Set(
    data.sources.items
      .filter((s) => s.document_id === documentId)
      .map((s) => s.id),
  );
  return data.assessments.items.filter((a) => ids.has(a.invoice_source_id));
}
/** Counts are a dated sample, never an alternative calculation of financial totals. */
export function activitySeries(assessments: Assessment[]) {
  const days = new Map<string, number>();
  for (const a of assessments)
    if (
      /^\d{4}-\d{2}-\d{2}T/.test(a.created_at) &&
      Number.isFinite(Date.parse(a.created_at))
    ) {
      const day = a.created_at.slice(0, 10);
      days.set(day, (days.get(day) ?? 0) + 1);
    }
  return [...days].sort(([a], [b]) => a.localeCompare(b)).slice(-10);
}

/** A chart percentage only; monetary values always come from the backend. */
export function exposureShare(part: string, total: string): number {
  const valid = /^\d{1,60}(?:\.\d{1,30})?$/;
  if (!valid.test(part) || !valid.test(total)) return 0;
  const scale = Math.max(
    part.split(".")[1]?.length ?? 0,
    total.split(".")[1]?.length ?? 0,
  );
  const units = (v: string) => {
    const [i, f = ""] = v.split(".");
    return BigInt(i + f.padEnd(scale, "0"));
  };
  const denominator = units(total);
  return denominator === 0n
    ? 0
    : Math.min(100, Number((units(part) * 10000n) / denominator) / 100);
}
