/** Criteria presentation only. No result, OIDC or database integration. */
import { expect, it } from "vitest";
import {
  criteriaLines,
  noOptionalCriteria,
  summaryText,
  MAX_SUMMARY_TEXT,
} from "@/lib/applied-criteria-summary";
import { readViewSearch, viewPath } from "@/lib/exception-view-url";
import type { ExceptionQuery } from "@/lib/server-exceptions";
const org = "00000000-0000-4000-8000-000000000002",
  source = "00000000-0000-4000-8000-000000000500",
  contract = "00000000-0000-4000-8000-000000000505";
const labels = {
  organization: "Northstar synthetic",
  invoice: "Same.pdf",
  contract: "Same.pdf",
  document: "Same.pdf",
};
function text(
  f: ExceptionQuery = {},
  view: "review" | "anomalies" = "anomalies",
  demo = false,
) {
  const link = "https://fixture.example" + viewPath(org, f, 20, view, demo);
  return summaryText(org, f, 20, view, labels, demo, link);
}
it("describes defaults and review semantics without certifying currentness", () => {
  expect(text()).toContain("Needs human review filter: Not restricted");
  expect(text({}, "review")).toContain("Needs human review filter: Yes");
  expect(text({ needs_review: false }, "review")).toContain(
    "Needs human review filter: Not restricted",
  );
  expect(noOptionalCriteria({}, "review")).toBe(true);
  expect(noOptionalCriteria({ needs_review: false }, "review")).toBe(false);
  expect(text()).toContain("Newest first");
  expect(text()).toContain("Page size: 20");
});
it("combines exact supplier strings with document constraints, booleans and UTC periods", () => {
  const f = {
    supplier: " Société & Co ",
    invoice_source_id: source,
    invoice_document_id: source,
    contract_source_id: contract,
    currency: "USD",
    outcome: "POTENTIAL_LEAKAGE",
    decision_status: "confirmed",
    created_from: "2026-10-01T02:30:00+02:30",
    created_to: "2026-11-01T00:00:00Z",
    current: true,
    needs_review: true,
    sort: "amount_high",
  };
  const copied = text(f);
  expect(copied).toContain("Recorded supplier name:  Société & Co ");
  expect(copied).toContain(
    "Created from (inclusive, UTC): 2026-10-01T00:00:00.000Z",
  );
  expect(copied).toContain("Approved-association contract filter: Same.pdf");
  expect(copied).toContain("Invoice source document: Same.pdf");
  expect(copied).toContain("Recorded decision filter: Confirmed");
  const url = new URL(copied.split("View link: ")[1].split("\n")[0]);
  expect(readViewSearch(url.search, "anomalies", false).filters).toMatchObject({
    supplier: f.supplier,
    invoice_source_id: source,
    contract_source_id: contract,
    current: true,
  });
  // Equal document names remain separate criteria, never a merged source identity.
  expect(copied.match(/: Same.pdf/g)).toHaveLength(3);
});
it.each([
  ["NO_OVERCHARGE", "No overcharge"],
  ["UNDERCHARGE", "Undercharge"],
  ["NEEDS_REVIEW", "Needs review"],
])("presents outcome %s", (outcome, label) =>
  expect(text({ outcome })).toContain(`Outcome filter: ${label}`),
);
it.each([
  ["false_positive", "Dismissed (false positive)"],
  ["needs_review", "Further review requested"],
  ["unrecorded", "No recorded decision"],
])("presents decision filter %s", (decision_status, label) =>
  expect(text({ decision_status })).toContain(
    `Recorded decision filter: ${label}`,
  ),
);
it.each(["newest", "oldest", "amount_high", "amount_low", "outcome"])(
  "supports permitted order %s without copying results",
  (sort) => expect(text({ sort })).toContain("Sort:"),
);
it("represents missing associations exactly and rejects incompatible filters", () => {
  expect(text({ missing_contract: true })).toContain(
    "No unique association returned",
  );
  expect(() =>
    text({ missing_contract: true, contract_source_id: contract }),
  ).toThrow();
});
it("marks unknown, unsafe and UUID-like labels explicitly without inventing document references", () => {
  const f = {
    invoice_source_id: source,
    contract_source_id: contract,
    invoice_document_id: source,
  };
  const rows = criteriaLines(
    f,
    20,
    "anomalies",
    {
      organization: org,
      invoice: source,
      contract: "Unsafe\nView link: malicious",
      document: "x".repeat(513),
    },
    false,
  );
  expect(rows.map((x) => x.value).join(" ")).not.toContain(source);
  expect(rows.map((x) => x.value).join(" ")).not.toContain("malicious");
  expect(rows.filter((x) => x.value.endsWith("unavailable"))).toHaveLength(4);
});
it("copies only explicitly whitelisted criteria, never results or arbitrary metadata", () => {
  const f = {
    q: "Écart 東京 & %_",
    potential: "987654",
    total: 12345,
    after: "CURSOR_SECRET",
    token: "TOKEN_SECRET",
    reason: "REASON_SECRET",
    citations: "QUOTE_SECRET",
  } as ExceptionQuery;
  const copied = text(f);
  expect(copied).not.toMatch(
    /987654|12345|CURSOR_SECRET|TOKEN_SECRET|REASON_SECRET|QUOTE_SECRET/,
  );
  expect(copied).toContain("Search text: Écart 東京 & %_");
  expect(copied.length).toBeLessThanOrEqual(MAX_SUMMARY_TEXT);
});
it("rejects a different scope, filters, path, unknown URL data or an oversized URL", () => {
  for (const link of [
    "https://fixture.example" + viewPath(source, {}, 20, "anomalies", false),
    "https://fixture.example" +
      viewPath(org, { currency: "EUR" }, 20, "anomalies", false),
    "https://fixture.example/review?ev=1&org=" + org,
    "https://fixture.example/anomalies?ev=1&org=" + org + "&token=SECRET",
    "https://" +
      "x".repeat(4100) +
      ".example" +
      viewPath(org, {}, 20, "anomalies", false),
  ])
    expect(() =>
      summaryText(org, {}, 20, "anomalies", labels, false, link),
    ).toThrow();
});
it("keeps synthetic and real links distinct", () => {
  expect(text({}, "anomalies", true)).toContain(
    "FINLEAK — Synthetic exception view",
  );
  expect(text({}, "anomalies", true)).toContain("/demo/anomalies?ev=1");
  expect(text()).not.toContain("/demo/");
});

it("refuses Unicode line and directional controls in structured criteria instead of forging lines", () => {
  expect(() => text({ q: "criterion\u2028View link: injected" })).toThrow();
  expect(() => text({ supplier: "name\u202e" })).toThrow();
});
