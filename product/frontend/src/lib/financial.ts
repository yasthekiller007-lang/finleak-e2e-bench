export type Source = {
  id: string;
  document_id: string;
  kind: "contract" | "invoice";
};
export type ReviewRecord = {
  id: string;
  kind: string;
  key: string;
  state: "prepared" | "approved" | "revoked";
  actor_id: string;
  created_at: string;
  payload: {
    value: Record<string, unknown>;
    evidence: Evidence[];
    reason: string;
    uncertainty_resolution: string;
  };
  provenance: Evidence[];
};
export type Evidence = {
  document_id: string;
  location: string;
  quote: string;
  field_id: string | null;
  manual: boolean;
  supports: string[];
  sha256?: string;
  raw_value?: string;
  normalized_candidate?: string | null;
  run_id?: string | null;
};
export type SourceDetail = Source & {
  reviews: ReviewRecord[];
  approved_inputs: ReviewRecord[];
  revision_ids: string[];
};
export type Assessment = {
  queue_context?: {
    supplier_party: string | null;
    contract_source_id: string | null;
    contract_references: string[];
  };
  fingerprint?: string;
  scope_summary?: {
    label: string | null;
    quantity: string | null;
    unit: string | null;
    contracted_rate: string | null;
    billed_rate: string | null;
  };
  id: string;
  invoice_source_id: string;
  scope_key: string;
  outcome: string;
  reason_code: string;
  explanation: string;
  currency: string | null;
  expected: string | null;
  actual: string | null;
  discrepancy: string | null;
  potential: string | null;
  stale: boolean;
  status: string | null;
  decision_id: string | null;
  created_at: string;
  snapshot?: {
    inputs: ReviewRecord[];
    billing_scope: Record<string, unknown> | null;
    calculation: {
      formula: string;
      expected_raw: string;
      actual_bridge_raw: string;
      alternatives: Record<string, string>[];
      rules: string[];
    } | null;
    compiler: string;
    rules: string;
    coverage: string;
  };
};
export type Summary = {
  potential_by_currency: Record<string, string>;
  counts: Record<string, number>;
  limited: boolean;
  coverage: string;
};
export function money(amount: string | null, currency: string | null) {
  if (amount === null) return "Not assessed";
  const [integer, fraction = ""] = amount.split(".");
  return `${integer.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}${fraction ? "." + fraction.replace(/0+$/, "").padEnd(2, "0") : ".00"} ${currency ?? ""}`.trim();
}
export function evidencePaths(value: unknown, prefix = ""): string[] {
  if (value !== null && typeof value === "object")
    return Object.entries(value).flatMap(([k, v]) =>
      evidencePaths(v, `${prefix}/${k}`),
    );
  return [prefix];
}
export async function financialRequest<T>(
  organizationId: string,
  path: string,
  body?: unknown,
  key?: string,
): Promise<T> {
  const response = await fetch(
    `/api/organizations/${organizationId}/financial/${path}`,
    {
      method: body === undefined ? "GET" : "POST",
      cache: "no-store",
      headers:
        body === undefined
          ? undefined
          : {
              "Content-Type": "application/json",
              ...(key ? { "Idempotency-Key": key } : {}),
            },
      body: body === undefined ? undefined : JSON.stringify(body),
    },
  );
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      data.error?.message ?? "Unable to complete financial review.",
    );
  return data as T;
}
