/** Synthetic, browser-local example data. Never imported by live routes or API proxies. */
import type {
  Assessment,
  Evidence,
  ReviewRecord,
  Source,
} from "@/lib/financial";
import type { CurrentUser, FinancialDocument } from "@/lib/documents";
import type { ProofPackage } from "@/lib/proof";
import type {
  Decision,
  WorkspaceData,
  WorkspaceGateway,
} from "@/lib/product-workspace";
import { WorkspaceError } from "@/lib/product-workspace";

const id = (n: number) =>
  `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
export const demoUser: CurrentUser = {
  id: id(1),
  display_name: "Alex Morgan",
  email: null,
  max_upload_bytes: 20971520,
  organizations: [{ id: id(2), name: "Northstar Industries", role: "owner" }],
};

function document(
  n: number,
  name: string,
  kind: "invoice" | "contract",
  status: FinancialDocument["processing_status"] = "processed",
): FinancialDocument {
  return {
    id: id(n),
    organization_id: id(2),
    original_filename: name,
    document_type: kind,
    processing_status: status,
    mime_type: "application/pdf",
    file_size: 48216 + n,
    sha256: "d".repeat(64),
    uploaded_at: `2026-10-${14 + (n % 5)}T09:30:00Z`,
    uploaded_by: id(1),
  };
}
const docs = [
  document(101, "AcmeCloud_INV-2026-1042.pdf", "invoice"),
  document(102, "Veridian_INV-2026-0891.pdf", "invoice"),
  document(103, "Atlas_INV-2026-0318.pdf", "invoice"),
  document(104, "AcmeCloud_INV-2026-1089.pdf", "invoice", "needs_review"),
  document(105, "Veridian_INV-2026-0910.pdf", "invoice"),
  document(201, "AcmeCloud_Master-Services-2026.pdf", "contract"),
  document(202, "Veridian_Connectivity-2026.pdf", "contract"),
  document(203, "Atlas_Data-License-2026.pdf", "contract"),
];
const sources: Source[] = docs.map((d, i) => ({
  id: id(500 + i),
  document_id: d.id,
  kind: d.document_type as "invoice" | "contract",
}));

function input(
  n: number,
  kind: string,
  doc: FinancialDocument,
  value: Record<string, unknown>,
  quote: string,
  location: string,
): ReviewRecord {
  const evidence: Evidence = {
    document_id: doc.id,
    location,
    quote,
    raw_value: quote,
    normalized_candidate: null,
    field_id: null,
    run_id: null,
    manual: true,
    supports: Object.keys(value).map((k) => `/${k}`),
    sha256: doc.sha256,
  };
  return {
    id: id(n),
    kind,
    key: kind === "term" ? "subscription-price" : "line-1",
    state: "approved",
    actor_id: id(1),
    created_at: "2026-10-14T10:15:00Z",
    payload: {
      value,
      reason: "Synthetic example: source meaning reviewed.",
      uncertainty_resolution: "Synthetic fixture; not an actual review.",
      evidence: [evidence],
    },
    provenance: [evidence],
  };
}

function evaluation(
  n: number,
  i: number,
  expected: string | null,
  actual: string | null,
  potential: string | null,
  currency: string,
  family: string,
  label: string,
  status: string | null,
): Assessment {
  const contract = docs[5 + Math.min(i, 2)],
    invoice = docs[i];
  const inputs =
    potential === null
      ? []
      : [
          input(
            800 + n * 10,
            "term",
            contract,
            { family, rate: i === 0 ? "42.000000" : expected, currency },
            i === 0
              ? "Subscription unit price: USD 42 per seat per month."
              : `Contractual fee: ${expected} ${currency}.`,
            "Page 4 · Pricing schedule · clause 3.2",
          ),
          input(
            801 + n * 10,
            "billing_scope",
            invoice,
            {
              label,
              posted_amount: actual,
              currency,
              ...(i === 0
                ? {
                    quantity: "640.000000",
                    billed_rate: "57.000000",
                    unit: "seat",
                  }
                : {}),
            },
            i === 0
              ? "640 enterprise seats at USD 57.00; total USD 36,480.00."
              : `Billed amount: ${actual} ${currency}.`,
            "Page 1 · Invoice line 1",
          ),
        ];
  return {
    id: id(n),
    invoice_source_id: sources[i].id,
    scope_key: "line-1",
    outcome: potential === null ? "NEEDS_REVIEW" : "POTENTIAL_OVERCHARGE",
    reason_code:
      potential === null ? "UNAPPROVED_FACT" : "SUPPORTED_DISCREPANCY",
    explanation:
      potential === null
        ? "The pricing schedule is missing. No financial amount can be assessed until the contractual basis is reviewed."
        : i === 0
          ? "640 seats were billed at USD 57.00 instead of the approved contractual rate of USD 42.00. The supported potential discrepancy is USD 9,600.00."
          : `The recorded ${family.replaceAll("_", " ")} assessment identifies a potential discrepancy against approved contractual facts.`,
    currency,
    expected,
    actual,
    discrepancy: potential,
    potential,
    stale: false,
    status,
    decision_id: status === "confirmed" ? id(900 + n) : null,
    created_at: `2026-10-${14 + i}T11:20:00Z`,
    fingerprint: "e".repeat(64),
    scope_summary: {
      label,
      quantity: i === 0 ? "640.000000" : null,
      unit: i === 0 ? "seat" : null,
      contracted_rate: i === 0 ? "42.000000" : null,
      billed_rate: i === 0 ? "57.000000" : null,
    },
    snapshot: {
      inputs,
      billing_scope:
        potential === null
          ? null
          : { label, posted_amount: actual, currency, members: ["line-1"] },
      calculation:
        potential === null
          ? null
          : {
              formula:
                i === 0
                  ? "640 × (57.00 − 42.00) = 9,600.00 USD"
                  : "Actual billed amount − approved expected amount",
              expected_raw: expected!,
              actual_bridge_raw: actual!,
              alternatives: [],
              rules: [family],
            },
      compiler: "SYNTHETIC_EXAMPLE",
      rules: "SYNTHETIC_EXAMPLE",
      coverage: "Synthetic example only; no backend evaluation executed.",
    },
  };
}

export function createDemoGateway(): WorkspaceGateway {
  const assessments = [
    evaluation(
      1001,
      0,
      "26880.000000",
      "36480.000000",
      "9600.000000",
      "USD",
      "unit_price",
      "Enterprise seats · October",
      "detected",
    ),
    evaluation(
      1002,
      1,
      "5600.000000",
      "8480.000000",
      "2880.000000",
      "USD",
      "fixed_fee",
      "Connectivity subscription",
      "confirmed",
    ),
    evaluation(
      1003,
      2,
      "7460.000000",
      "8840.000000",
      "1380.000000",
      "EUR",
      "percentage_discount",
      "Annual data license",
      "confirmed",
    ),
    evaluation(
      1004,
      3,
      null,
      null,
      null,
      "USD",
      "unit_price",
      "Additional storage · October",
      null,
    ),
  ];
  let sequence = 1;
  const check = (org: string, signal: AbortSignal) => {
    signal.throwIfAborted();
    if (org !== id(2))
      throw new WorkspaceError("Synthetic organization not found.", 404);
  };
  const get = (key: string) => {
    const a = assessments.find((a) => a.id === key);
    if (!a) throw new WorkspaceError("Synthetic assessment not found.", 404);
    return a;
  };
  const summary = (): WorkspaceData["summary"] => {
    // Fixed fixture currency values, never a browser reimplementation of approved financial rules.
    const excluded = assessments
      .filter((a) => a.status === "false_positive")
      .map((a) => a.id);
    const usd =
      !excluded.includes(id(1001)) && !excluded.includes(id(1002))
        ? "12480.000000"
        : !excluded.includes(id(1001))
          ? "9600.000000"
          : !excluded.includes(id(1002))
            ? "2880.000000"
            : "0.000000";
    return {
      potential_by_currency: {
        USD: usd,
        EUR: excluded.includes(id(1003)) ? "0.000000" : "1380.000000",
      },
      potential_by_rule: Object.fromEntries(
        assessments
          .filter((a) => a.potential !== null && a.status !== "false_positive")
          .map((a) => [
            a.snapshot!.calculation!.rules[0],
            { [a.currency!]: a.potential! },
          ]),
      ),
      counts: {
        findings: 3 - excluded.length,
        blocked: 1,
        assessed: 0,
        stale: 0,
        dismissed: excluded.length,
      },
      limited: false,
      coverage:
        "Synthetic current, undismissed, non-overlapping scopes. Potential leakage is not recovered cash or guaranteed savings.",
    };
  };
  return {
    async load(org, signal) {
      check(org, signal);
      return structuredClone({
        summary: summary(),
        documents: { items: docs, total: docs.length, limit: 100, offset: 0 },
        sources: {
          items: sources,
          total: sources.length,
          limit: 100,
          offset: 0,
        },
        assessments: {
          items: assessments,
          total: assessments.length,
          limit: 100,
          offset: 0,
        },
      });
    },
    async documents(org, offset, signal) {
      check(org, signal);
      return structuredClone({
        items: docs.slice(offset),
        total: docs.length,
        limit: 100,
        offset,
      });
    },
    async assessments(org, offset, signal) {
      check(org, signal);
      return structuredClone({
        items: assessments.slice(offset),
        total: assessments.length,
        limit: 100,
        offset,
      });
    },
    async assessment(org, key, signal) {
      check(org, signal);
      return structuredClone(get(key));
    },
    async proof(org, key, signal) {
      check(org, signal);
      const a = get(key);
      if (a.potential === null)
        return { proof: null, history: null, hasMorePackages: false };
      const proof: ProofPackage = {
        id: id(2000 + Number(key.slice(-4))),
        number: 1,
        family_id: id(7001),
        fingerprint: "f".repeat(64),
        created_at: a.created_at,
        previous_id: null,
        revision_reason: null,
        issued_completeness: "COMPLETE",
        identity: {
          evaluation_id: a.id,
          evaluation_fingerprint: a.fingerprint!,
          finding_id: id(3000),
          kind: "FINANCIAL_FINDING_EVIDENCE",
          scope_key: a.scope_key,
        },
        financial: {
          outcome: a.outcome,
          explanation: a.explanation,
          currency: a.currency,
          expected: a.expected,
          actual: a.actual,
          discrepancy: a.discrepancy,
          potential: a.potential,
        },
        overlays: {
          financial_currentness: "CURRENT",
          finding_decision: a.status,
          human_review: "NEEDS_REVIEW",
          review_id: null,
          successor_id: null,
          predecessor_id: null,
          evidence_availability: a.snapshot!.inputs.flatMap((r) =>
            r.provenance.map((e) => ({
              document_id: e.document_id,
              status: "SYNTHETIC_EXAMPLE",
            })),
          ),
        },
        core: {
          authority: a.snapshot!.inputs,
          governing: a.snapshot!.inputs[0].payload.value,
          billing: { scope: a.snapshot!.billing_scope },
          matching: { method: "SYNTHETIC_EXAMPLE" },
          behavior: { compiler: "SYNTHETIC_EXAMPLE" },
          calculation: {
            recorded_trace: a.snapshot!.calculation,
            bindings: [],
          },
          completeness: { requirements: {}, gaps: [] },
          limitations: [
            "Synthetic example. No source file, digest or backend proof was independently verified.",
          ],
          sources: a.snapshot!.inputs.flatMap((r) =>
            r.provenance.map((e) => ({
              document_id: e.document_id,
              sha256: e.sha256!,
              verified_at_issuance: false,
            })),
          ),
          evaluation_snapshot_digest: "e".repeat(64),
        },
      };
      return {
        proof: structuredClone(proof),
        history: {
          items: [
            {
              id: id(3001),
              number: 1,
              kind: "synthetic.proof.issued",
              actor_id: id(1),
              created_at: a.created_at,
              previous_id: null,
              audit_id: id(4001),
              detail: {
                text: "Synthetic proof issuance for product exploration only.",
              },
            },
          ],
          has_more: false,
          limit: 100,
          offset: 0,
        },
        hasMorePackages: false,
      };
    },
    async decide(org, key, decision: Decision, signal) {
      check(org, signal);
      const a = get(key);
      if (a.decision_id !== decision.expected_decision)
        throw new WorkspaceError(
          "This synthetic record changed. Refresh before deciding.",
          409,
        );
      if (!decision.reason.trim())
        throw new WorkspaceError("A reason is required.", 422);
      a.status = decision.status;
      a.decision_id = id(5000 + sequence++);
      return { id: a.decision_id, status: a.status, reason: decision.reason };
    },
  };
}
