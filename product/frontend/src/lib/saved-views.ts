/** Personal criteria contracts. No result, document body, decision, token or cursor storage. */
import type { ExceptionQuery } from "@/lib/server-exceptions";
import {
  validatedCriteria,
  viewPath,
  type ExceptionView,
} from "@/lib/exception-view-url";
export class SavedViewsError extends Error {
  constructor(
    message: string,
    public status: number,
    public requestId: string | null = null,
    public code: string | null = null,
  ) {
    super(message);
  }
}
export type SavedDefinition = {
  view_type: ExceptionView;
  format_version: 1;
  criteria: ExceptionQuery;
  page_size: number;
};
export type SavedView = SavedDefinition & {
  id: string;
  organization_id: string;
  user_id: string;
  name: string;
  revision: number;
  created_at: string;
  updated_at: string;
};
export type SavedPage = {
  items: SavedView[];
  limit: number;
  has_more: boolean;
  next_after: string | null;
  max_views: number;
};
export interface SavedViewsGateway {
  list(
    org: string,
    owner: string,
    view: ExceptionView,
    search: string,
    after: string | null,
    signal: AbortSignal,
  ): Promise<SavedPage>;
  get(
    org: string,
    owner: string,
    id: string,
    signal: AbortSignal,
  ): Promise<SavedView>;
  create(
    org: string,
    owner: string,
    name: string,
    definition: SavedDefinition,
    signal: AbortSignal,
  ): Promise<SavedView>;
  update(
    org: string,
    owner: string,
    id: string,
    expected_revision: number,
    patch: { name?: string; definition?: SavedDefinition },
    signal: AbortSignal,
  ): Promise<SavedView>;
  remove(
    org: string,
    owner: string,
    id: string,
    expected_revision: number,
    signal: AbortSignal,
  ): Promise<void>;
}
const fields = new Set([
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
]);
const uuid = /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i;
const invalid = (): never => {
  throw Error("Unsupported personal view. No search was started.");
};
const record = (v: unknown): Record<string, unknown> => {
  if (!v || typeof v !== "object" || Array.isArray(v)) return invalid();
  return v as Record<string, unknown>;
};
export function savedName(value: string) {
  if (/[\p{Cc}\p{Cf}\p{Cs}]/u.test(value))
    throw Error("Use a plain-text view name.");
  const name = value.normalize("NFKC").trim().replace(/\s+/gu, " ");
  if (![...name].length || [...name].length > 80)
    throw Error("Use a name between 1 and 80 characters.");
  return name;
}
export function savedDefinition(value: unknown, demo = false): SavedDefinition {
  const v = record(value);
  if (
    Object.keys(v).some(
      (k) =>
        !["view_type", "format_version", "criteria", "page_size"].includes(k),
    ) ||
    !["review", "anomalies"].includes(String(v.view_type)) ||
    v.format_version !== 1 ||
    !(demo ? [2, 20, 50, 100] : [20, 50, 100]).includes(v.page_size as number)
  )
    return invalid();
  const raw = record(v.criteria);
  if (Object.keys(raw).some((k) => !fields.has(k))) return invalid();
  for (const [k, item] of Object.entries(raw)) {
    if (
      ["current", "needs_review", "missing_contract"].includes(k)
        ? typeof item !== "boolean"
        : typeof item !== "string"
    )
      return invalid();
  }
  if (
    Object.values(raw).some(
      (item) => typeof item === "string" && /[\p{Cc}\p{Cf}\p{Cs}]/u.test(item),
    )
  )
    return invalid();
  const view = v.view_type as ExceptionView;
  const criteria = validatedCriteria(raw as ExceptionQuery, view);
  viewPath(
    "00000000-0000-4000-8000-000000000001",
    criteria,
    v.page_size as number,
    view,
    demo,
  );
  return {
    view_type: view,
    format_version: 1,
    criteria,
    page_size: v.page_size as number,
  };
}
export function parseSavedView(
  value: unknown,
  org: string,
  owner: string,
  demo = false,
): SavedView {
  const v = record(value);
  if (
    Object.keys(v).some(
      (k) =>
        ![
          "id",
          "organization_id",
          "user_id",
          "name",
          "revision",
          "created_at",
          "updated_at",
          "view_type",
          "format_version",
          "criteria",
          "page_size",
        ].includes(k),
    ) ||
    typeof v.id !== "string" ||
    !uuid.test(v.id) ||
    v.organization_id !== org ||
    v.user_id !== owner ||
    typeof v.name !== "string" ||
    savedName(v.name) !== v.name ||
    !Number.isSafeInteger(v.revision) ||
    Number(v.revision) < 1 ||
    typeof v.created_at !== "string" ||
    !Number.isFinite(Date.parse(v.created_at)) ||
    typeof v.updated_at !== "string" ||
    !Number.isFinite(Date.parse(v.updated_at))
  )
    return invalid();
  const definition = savedDefinition(
    {
      view_type: v.view_type,
      format_version: v.format_version,
      criteria: v.criteria,
      page_size: v.page_size,
    },
    demo,
  );
  return {
    ...definition,
    id: v.id,
    organization_id: org,
    user_id: owner,
    name: v.name,
    revision: Number(v.revision),
    created_at: v.created_at,
    updated_at: v.updated_at,
  };
}
async function request(
  org: string,
  path: string,
  signal: AbortSignal,
  method = "GET",
  body?: unknown,
) {
  const response = await fetch(
    `/api/organizations/${encodeURIComponent(org)}/financial/saved-views${path}`,
    {
      method,
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
  const data = await response.json().catch(() => null);
  if (!response.ok)
    throw new SavedViewsError(
      data?.error?.message ??
        "Personal views are unavailable. Reload before another write.",
      response.status,
      response.headers.get("x-request-id"),
      data?.error?.code,
    );
  return data;
}
export const liveSavedViewsGateway: SavedViewsGateway = {
  async list(org, owner, view, search, after, signal) {
    const q = new URLSearchParams({ view_type: view, search, limit: "10" });
    if (after) q.set("after", after);
    const value = record(await request(org, `?${q}`, signal));
    if (
      !Array.isArray(value.items) ||
      value.items.length > 10 ||
      value.limit !== 10 ||
      typeof value.has_more !== "boolean" ||
      value.max_views !== 50 ||
      (value.next_after !== null &&
        (typeof value.next_after !== "string" ||
          !uuid.test(value.next_after))) ||
      value.has_more !== Boolean(value.next_after)
    )
      return invalid();
    return {
      items: value.items.map((i) => parseSavedView(i, org, owner)),
      limit: 10,
      has_more: value.has_more,
      next_after: value.next_after as string | null,
      max_views: 50,
    };
  },
  async get(org, owner, id, signal) {
    const row = parseSavedView(
      await request(org, `/${id}`, signal),
      org,
      owner,
    );
    if (row.id !== id) return invalid();
    return row;
  },
  async create(org, owner, name, definition, signal) {
    const d = savedDefinition(definition);
    return parseSavedView(
      await request(org, "", signal, "POST", { name: savedName(name), ...d }),
      org,
      owner,
    );
  },
  async update(org, owner, id, expected_revision, patch, signal) {
    return parseSavedView(
      await request(org, `/${id}`, signal, "PATCH", {
        expected_revision,
        ...(patch.name === undefined ? {} : { name: savedName(patch.name) }),
        ...(patch.definition === undefined
          ? {}
          : { definition: savedDefinition(patch.definition) }),
      }),
      org,
      owner,
    );
  },
  async remove(org, _owner, id, expected_revision, signal) {
    const data = await request(org, `/${id}`, signal, "DELETE", {
      expected_revision,
    });
    if (data?.id !== id || data?.deleted !== true)
      throw Error("Deletion could not be confirmed. Reload personal views.");
  },
};
