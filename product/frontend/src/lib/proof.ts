export type Page<T> = {
  items: T[];
  has_more: boolean;
  limit: number;
  offset: number;
};
export type ProofBinding = {
  binding_id: string;
  revision_id: string;
  input_pointer: string;
  role: string;
  typed_input: {
    type: string;
    value: string | boolean | null;
    currency?: string | null;
    unit?: string | null;
    denominator?: string | null;
  };
  source: {
    document_id: string;
    sha256: string;
    quote: string;
    location: string;
    raw_value: string;
    normalized_candidate: string | null;
    manual: boolean;
    run_id: string | null;
    field_id: string | null;
    source_location: unknown;
  };
  location_precision: string;
};
export type ProofPackage = {
  id: string;
  number: number;
  family_id: string;
  fingerprint: string;
  created_at: string;
  previous_id: string | null;
  revision_reason: string | null;
  issued_completeness: "COMPLETE" | "INCOMPLETE";
  identity: {
    evaluation_id: string;
    evaluation_fingerprint: string;
    finding_id: string | null;
    kind: string;
    scope_key: string;
  };
  financial: {
    outcome: string;
    explanation: string;
    currency: string | null;
    expected: string | null;
    actual: string | null;
    discrepancy: string | null;
    potential: string | null;
  };
  overlays: {
    as_of?: string;
    financial_currentness: string;
    finding_decision: string | null;
    human_review: string;
    review_id: string | null;
    successor_id: string | null;
    predecessor_id: string | null;
    evidence_availability: {
      document_id: string;
      status: string;
      observed_at?: string;
    }[];
  };
  core?: {
    authority: unknown[];
    governing: unknown;
    billing: { scope: Record<string, unknown> | null };
    matching: unknown;
    behavior: unknown;
    calculation: { recorded_trace: unknown; bindings: ProofBinding[] };
    completeness: {
      requirements: Record<string, { passed: boolean; gaps: unknown[] }>;
      gaps: { code: string; binding: string; message: string }[];
    };
    limitations: string[];
    sources: {
      document_id: string;
      sha256: string;
      verified_at_issuance: boolean;
    }[];
    evaluation_snapshot_digest: string;
  };
  envelope?: Record<string, unknown>;
};
export type ProofEvent = {
  id: string;
  number: number;
  kind: string;
  actor_id: string;
  created_at: string;
  previous_id: string | null;
  audit_id: string;
  detail: { text?: string; status?: string; paths?: string[] };
};
export type ProofArtifact = {
  id: string;
  content_hash: string;
  disclosure_id: string | null;
  actor_id: string;
  created_at: string;
  size_bytes: number;
};
export function proofUrl(org: string, path: string) {
  return `/api/organizations/${org}/proof/${path}`;
}
export async function proofRequest<T>(
  org: string,
  path: string,
  signal: AbortSignal,
  body?: unknown,
  key?: string,
): Promise<T> {
  const response = await fetch(proofUrl(org, path), {
    method: body === undefined ? "GET" : "POST",
    cache: "no-store",
    signal,
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
      `${data.error?.code ?? "proof_error"}: ${data.error?.message ?? "Proof request failed"}`,
    );
  return data as T;
}
