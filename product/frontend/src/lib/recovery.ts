export type LedgerRecord = {
  id: string;
  kind: string;
  case_id?: string;
  number?: number;
  actor_id?: string;
  created_at: string;
  known_at?: string | null;
  recorded_at?: string;
  amount?: string | null;
  reason?: string;
  value: Record<string, unknown>;
  authority?: { head: string | null };
  pins?: Record<string, unknown>;
};
export type RecoveryCase = {
  id: string;
  evaluation_id: string;
  head_id: string | null;
  currency: string;
  supplier: string;
  customer: string;
  lifecycle: string;
  readiness: string;
  finding_decision: string;
  currentness: string;
  evidence: string;
  realization_state: string;
  category: string;
  coverage: string;
  potential: string;
  validated: string | null;
  pursuit: string | null;
  claimed: string | null;
  acknowledged: string | null;
  disputed: string | null;
  realized: string;
  methods: Record<string, string>;
  net_cash: string | null;
  pending_credit: string | null;
  unrealized: string | null;
  ratio: string | null;
  costs: Record<string, { incurred: string; paid: string }>;
  readiness_record: LedgerRecord | null;
  workflow: Record<string, unknown> | null;
};
export type Instrument = {
  id: string;
  kind: string;
  namespace: string;
  issuer: string;
  reference: string;
  currency: string;
};
export type Page<T> = {
  items: T[];
  has_more: boolean;
  offset: number;
  limit: number;
};
export async function recoveryRequest<T>(
  org: string,
  path: string,
  body?: unknown,
  key?: string,
): Promise<T> {
  const response = await fetch(`/api/organizations/${org}/recovery/${path}`, {
    method: body === undefined ? "GET" : "POST",
    cache: "no-store",
    headers:
      body === undefined
        ? undefined
        : {
            "Content-Type": "application/json",
            "Idempotency-Key": key ?? crypto.randomUUID(),
          },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      data.error?.message ??
        "Recovery request could not safely complete. Reload before retrying.",
    );
  return data as T;
}
export function sourceFields(
  value: Record<string, unknown>,
  prefix = "/value",
): Record<string, string> {
  const result: Record<string, string> = {};
  for (const [key, child] of Object.entries(value)) {
    const pointer = `${prefix}/${key.replaceAll("~", "~0").replaceAll("/", "~1")}`;
    if (child === null || child === undefined) continue;
    if (Array.isArray(child))
      Object.assign(
        result,
        sourceFields(Object.fromEntries(child.map((c, i) => [i, c])), pointer),
      );
    else if (typeof child === "object")
      Object.assign(
        result,
        sourceFields(child as Record<string, unknown>, pointer),
      );
    else
      result[pointer] =
        typeof child === "boolean" ? (child ? "True" : "False") : String(child);
  }
  return result;
}
