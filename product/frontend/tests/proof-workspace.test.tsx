import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, afterEach, it, expect, vi } from "vitest";
import { ProofWorkspace } from "@/components/proof-workspace";
import type { Assessment } from "@/lib/financial";
const assessment: Assessment = {
  id: "evaluation",
  fingerprint: "f".repeat(64),
  invoice_source_id: "invoice",
  scope_key: "line-1",
  outcome: "POTENTIAL_LEAKAGE",
  reason_code: "POTENTIAL_LEAKAGE",
  explanation: "Approved rate comparison",
  currency: "USD",
  expected: "803104.800000",
  actual: "877304.700000",
  discrepancy: "74199.900000",
  potential: "74199.900000",
  stale: false,
  status: "detected",
  decision_id: null,
  created_at: "2026-10-03",
};
let packageData: Record<string, unknown>;
const fetchMock = vi.fn();
beforeEach(() => {
  packageData = {
    id: "package",
    number: 1,
    family_id: "family",
    fingerprint: "a".repeat(64),
    issued_completeness: "COMPLETE",
    created_at: "2026-10-03",
    previous_id: null,
    revision_reason: null,
    identity: {
      evaluation_id: "evaluation",
      kind: "MONETARY_FINDING_PROOF",
      finding_id: "evaluation",
      scope_key: "line-1",
    },
    financial: assessment,
    overlays: {
      financial_currentness: "CURRENT",
      finding_decision: "detected",
      human_review: "UNREVIEWED",
      review_id: null,
      successor_id: null,
      predecessor_id: null,
      evidence_availability: [
        { document_id: "doc", status: "AVAILABLE_VERIFIED" },
      ],
    },
    core: {
      governing: [],
      billing: { scope: { quantity: "43647", unit: "unit" } },
      matching: { outcome: "MATCHED" },
      authority: [],
      behavior: { compiler: "reviewed-compiler/1" },
      calculation: {
        recorded_trace: {
          formula: "contracted unit price × billed quantity",
          expected_raw: "803104.800000",
          alternatives: [
            {
              expected: "803104.80",
              actual: "877304.70",
              discrepancy: "74199.90",
            },
          ],
        },
        bindings: [
          {
            binding_id: "evidence",
            revision_id: "revision",
            input_pointer: "/rate",
            role: "approved_input",
            typed_input: {
              type: "unit_price",
              value: "18.40",
              currency: "USD",
              denominator: "unit",
            },
            source: {
              document_id: "doc",
              sha256: "b".repeat(64),
              quote: "<script>alert('x')</script>",
              location: "Document-level reviewer citation",
              raw_value: "18.40",
              normalized_candidate: null,
              manual: true,
              run_id: null,
              field_id: null,
              source_location: "Document-level",
            },
            location_precision: "reviewer_citation",
          },
        ],
      },
      completeness: {
        requirements: { C01: { passed: true, gaps: [] } },
        gaps: [],
      },
      limitations: [
        "Evidence completeness is not legal certification, financial confirmation or recovery.",
      ],
      sources: [],
      evaluation_snapshot_digest: "c".repeat(64),
    },
    envelope: { audit_id: "audit" },
  };
  vi.stubGlobal(
    "fetch",
    fetchMock
      .mockReset()
      .mockImplementation(async (url: string, options?: RequestInit) => {
        if (options?.method === "POST")
          return Response.json({
            package_id: "package",
            event_id: "event",
            artifact_id: "artifact",
          });
        if (url.includes("/evaluations/"))
          return Response.json({
            items: [packageData],
            has_more: false,
            limit: 100,
            offset: 0,
          });
        if (url.includes("/history") || url.includes("/artifacts"))
          return Response.json({
            items: [],
            has_more: false,
            limit: 100,
            offset: 0,
          });
        return Response.json(packageData);
      }),
  );
});
afterEach(() => vi.unstubAllGlobals());
async function open(role = "owner") {
  render(
    <ProofWorkspace
      organizationId="org"
      assessment={assessment}
      role={role}
      autoOpen
    />,
  );
  await screen.findByRole("option", { name: "Revision 1 · COMPLETE at issue" });
  fireEvent.change(screen.getByLabelText("Immutable content revision"), {
    target: { value: "package" },
  });
  await screen.findByText("74,199.90 USD");
}
it("does no implicit generation or source work before explicit viewing", () => {
  render(
    <ProofWorkspace
      organizationId="org"
      assessment={assessment}
      role="owner"
    />,
  );
  expect(
    screen.getByRole("button", { name: "View proof" }),
  ).toBeInTheDocument();
  expect(fetchMock).not.toHaveBeenCalled();
});
it("shows exact executive money, orthogonal states, lineage and honest manual citation", async () => {
  await open();
  expect(screen.getByText("Evidence Complete")).toBeInTheDocument();
  expect(screen.getByText("CURRENT")).toBeInTheDocument();
  expect(screen.getByText("UNREVIEWED")).toBeInTheDocument();
  expect(screen.getByText(/803,104.80 USD/)).toBeInTheDocument();
  expect(screen.getByText(/18.40 · unit_price/)).toBeInTheDocument();
  expect(
    screen.getByText(/Quotation is not machine-verified/),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: "Inspect verified original source" }),
  ).toHaveAttribute(
    "href",
    "/api/organizations/org/proof/packages/package/sources/doc/download",
  );
  expect(document.querySelector("script")).toBeNull();
});
it.each(["owner", "admin", "analyst", "viewer"])(
  "enforces visible controls for %s",
  async (role) => {
    await open(role);
    expect(
      Boolean(screen.queryByRole("button", { name: "Generate proof" })),
    ).toBe(role !== "viewer");
    expect(
      Boolean(screen.queryByRole("button", { name: "Append annotation" })),
    ).toBe(role !== "viewer");
    expect(
      Boolean(screen.queryByRole("button", { name: "Prepare JSON export" })),
    ).toBe(["owner", "admin"].includes(role));
    expect(
      Boolean(
        screen.queryByRole("button", { name: "Record explicit successor" }),
      ),
    ).toBe(["owner", "admin"].includes(role));
    if (role === "analyst")
      expect(
        screen.getByRole("button", { name: "Propose proof review" }),
      ).toBeInTheDocument();
  },
);
it("keeps annotation text inert and sends UUID idempotency with no financial fields", async () => {
  await open("analyst");
  fireEvent.change(screen.getByLabelText("Annotation text"), {
    target: { value: "Nonfinancial verification note" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Append annotation" }));
  await waitFor(() =>
    expect(fetchMock.mock.calls.some(([, o]) => o?.method === "POST")).toBe(
      true,
    ),
  );
  const [, options] = fetchMock.mock.calls.find(
    ([, o]) => o?.method === "POST",
  )!;
  expect(JSON.parse(options.body)).toEqual({
    kind: "annotation.appended",
    text: "Nonfinancial verification note",
    previous_id: null,
  });
  expect(options.headers["Idempotency-Key"]).toMatch(/^[0-9a-f-]{36}$/);
});
it("keeps stale and dismissed historical evidence distinct from completeness", async () => {
  packageData.overlays = {
    financial_currentness: "STALE",
    finding_decision: "false_positive",
    human_review: "NEEDS_REVIEW",
    review_id: null,
    successor_id: null,
    evidence_availability: [],
  };
  await open();
  expect(screen.getByText("Evidence Complete")).toBeInTheDocument();
  expect(screen.getByText("STALE")).toBeInTheDocument();
  expect(screen.getByText(/after a finding is dismissed/)).toBeInTheDocument();
  expect(screen.getByText("NEEDS_REVIEW")).toBeInTheDocument();
});
it("displays blocked completeness as explanation and unknown money without zero", async () => {
  packageData.identity = {
    evaluation_id: "evaluation",
    kind: "BLOCKED_ASSESSMENT_EVIDENCE",
    finding_id: null,
    scope_key: "line-1",
  };
  packageData.financial = {
    ...assessment,
    outcome: "NEEDS_REVIEW",
    potential: null,
    expected: null,
    actual: null,
    discrepancy: null,
  };
  render(
    <ProofWorkspace
      organizationId="org"
      assessment={assessment}
      role="viewer"
      autoOpen
    />,
  );
  await screen.findByRole("option", { name: "Revision 1 · COMPLETE at issue" });
  fireEvent.change(screen.getByLabelText("Immutable content revision"), {
    target: { value: "package" },
  });
  await screen.findByText("Unknown monetary amount");
  expect(
    screen.getByText("Complete assessment explanation"),
  ).toBeInTheDocument();
  expect(screen.queryByText("0.00 USD")).toBeNull();
});
it("presents undercharge as informational comparison without positive leakage", async () => {
  packageData.financial = {
    ...assessment,
    outcome: "UNDERCHARGE",
    potential: null,
    discrepancy: "-100.000000",
  };
  packageData.identity = {
    evaluation_id: "evaluation",
    kind: "ASSESSED_COMPARISON_EVIDENCE",
    finding_id: null,
    scope_key: "line-1",
  };
  render(
    <ProofWorkspace
      organizationId="org"
      assessment={assessment}
      role="viewer"
      autoOpen
    />,
  );
  await screen.findByRole("option", { name: "Revision 1 · COMPLETE at issue" });
  fireEvent.change(screen.getByLabelText("Immutable content revision"), {
    target: { value: "package" },
  });
  await screen.findByText("Undercharge assessment evidence");
  expect(
    screen.queryByRole("heading", { name: "Potential Leakage" }),
  ).toBeNull();
  expect(screen.getByText(/-100.00 USD/)).toBeInTheDocument();
});
it("surfaces bounded-resource errors without fabricating zero or incomplete content", async () => {
  await open("analyst");
  fetchMock.mockImplementationOnce(async () =>
    Response.json(
      {
        error: {
          code: "proof_resource_limit",
          message: "Proof exceeds the source_bytes limit",
        },
      },
      { status: 413 },
    ),
  );
  fireEvent.click(screen.getByRole("button", { name: "Generate proof" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "proof_resource_limit",
  );
  expect(screen.getByText("74,199.90 USD")).toBeInTheDocument();
});
