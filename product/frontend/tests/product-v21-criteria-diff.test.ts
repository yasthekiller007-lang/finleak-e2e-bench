import { expect, it } from "vitest";
import {
  compareSavedCriteria,
  definitionKey,
  type DiffField,
} from "@/lib/saved-view-diff";
import type { ExceptionQuery } from "@/lib/server-exceptions";
const a = "aaaaaaaa-0000-4000-8000-000000000001",
  b = "aaaaaaaa-0000-4000-8000-000000000002";
const def = (
  criteria: ExceptionQuery = {},
  view_type: "anomalies" | "review" = "anomalies",
  page_size = 20,
) => ({ view_type, format_version: 1, criteria, page_size });
const status = (before: unknown, after: unknown, key: DiffField) =>
  compareSavedCriteria(before, after).rows.find((r) => r.field === key)!;
it("returns every approved criterion and a complete unchanged count", () => {
  const r = compareSavedCriteria(def(), def());
  expect(r.rows).toHaveLength(15);
  expect(r.hasChanges).toBe(false);
  expect(r.counts).toEqual({ ADDED: 0, REMOVED: 0, CHANGED: 0, UNCHANGED: 15 });
});
it.each([
  ["supplier", {}, { supplier: "Acme" }, "ADDED"],
  ["supplier", { supplier: "Acme" }, { supplier: "ACME" }, "CHANGED"],
  ["supplier", { supplier: "Acme" }, {}, "REMOVED"],
  ["q", {}, { q: "invoice" }, "ADDED"],
  [
    "contract_source_id",
    { contract_source_id: a },
    { contract_source_id: b },
    "CHANGED",
  ],
  [
    "invoice_source_id",
    { invoice_source_id: a },
    { invoice_source_id: b },
    "CHANGED",
  ],
  ["invoice_document_id", { invoice_document_id: a }, {}, "REMOVED"],
  ["currency", {}, { currency: "USD" }, "ADDED"],
  ["currency", { currency: "USD" }, { currency: "EUR" }, "CHANGED"],
  [
    "outcome",
    { outcome: "NEEDS_REVIEW" },
    { outcome: "POTENTIAL_LEAKAGE" },
    "CHANGED",
  ],
  [
    "decision_status",
    { decision_status: "unrecorded" },
    { decision_status: "confirmed" },
    "CHANGED",
  ],
  ["created_from", {}, { created_from: "2026-10-19T00:00:00Z" }, "ADDED"],
  ["created_to", { created_to: "2026-10-19T00:00:00Z" }, {}, "REMOVED"],
  ["current", {}, { current: true }, "CHANGED"],
  ["needs_review", {}, { needs_review: true }, "CHANGED"],
  ["missing_contract", {}, { missing_contract: true }, "CHANGED"],
  ["sort", {}, { sort: "oldest" }, "CHANGED"],
] as [DiffField, ExceptionQuery, ExceptionQuery, string][])(
  "classifies %s structured change",
  (key, before, after, expected) =>
    expect(status(def(before), def(after), key).status).toBe(expected),
);
it("counts independent additions removals and changed values", () => {
  const r = compareSavedCriteria(
    def({ supplier: "Acme", currency: "USD", q: "old" }),
    def({ currency: "EUR", outcome: "NEEDS_REVIEW", sort: "oldest" }),
  );
  expect(r.counts).toEqual({ ADDED: 1, REMOVED: 2, CHANGED: 2, UNCHANGED: 10 });
});
it("normalizes only according to existing query contracts", () => {
  expect(
    definitionKey(
      def({
        q: "  seats  ",
        invoice_source_id: a.toUpperCase(),
        created_from: "2026-10-19T01:00:00+01:00",
      }),
    ),
  ).toBe(
    definitionKey(
      def({
        q: "seats",
        invoice_source_id: a,
        created_from: "2026-10-19T00:00:00.000Z",
      }),
    ),
  );
  expect(
    status(def({ supplier: "Acme " }), def({ supplier: "Acme" }), "supplier")
      .status,
  ).toBe("CHANGED");
});
it("treats missing false and empty query as equal only when semantically unrestricted", () => {
  expect(
    compareSavedCriteria(
      def({ q: "", current: false, missing_contract: false }),
      def(),
    ).hasChanges,
  ).toBe(false);
  expect(
    compareSavedCriteria(def({ needs_review: false }), def()).hasChanges,
  ).toBe(false);
});
it("preserves review default true and distinguishes its explicit false override", () => {
  expect(
    compareSavedCriteria(
      def({}, "review"),
      def({ needs_review: true }, "review"),
    ).hasChanges,
  ).toBe(false);
  expect(
    status(
      def({}, "review"),
      def({ needs_review: false }, "review"),
      "needs_review",
    ),
  ).toMatchObject({ before: true, after: false, status: "CHANGED" });
});
it("compares presentation size and rejects cross-type equality", () => {
  expect(status(def(), def({}, "anomalies", 50), "page_size").status).toBe(
    "CHANGED",
  );
  expect(() => compareSavedCriteria(def(), def({}, "review"))).toThrow();
});
it.each([
  { ...def(), format_version: 2 },
  { ...def(), criteria: { token: "secret" } },
  { ...def(), criteria: { after: "cursor" } },
  { ...def(), potential: "9999" },
  { ...def(), criteria: { amount: "9999" } },
  { ...def(), criteria: { current: "false" } },
  { ...def(), criteria: { invoice_source_id: "bad" } },
  { ...def(), criteria: { missing_contract: true, contract_source_id: a } },
])(
  "refuses unsupported definitions rather than silently comparing them",
  (value) => expect(() => compareSavedCriteria(def(), value)).toThrow(),
);
it("does not accept document labels as identity or compare them instead of ids", () => {
  const r = compareSavedCriteria(
    def({ invoice_source_id: a }),
    def({ invoice_source_id: b }),
  );
  expect(r.rows.find((v) => v.field === "invoice_source_id")).toMatchObject({
    before: a,
    after: b,
    status: "CHANGED",
  });
  expect(() =>
    compareSavedCriteria({ ...def(), labels: { [a]: "Same.pdf" } }, def()),
  ).toThrow();
});
it("keeps returned snapshot independent from later input mutation", () => {
  const source = def({ supplier: "Acme" });
  const r = compareSavedCriteria(source, def({ supplier: "Other" }));
  source.criteria.supplier = "Changed later";
  expect(r.saved.criteria.supplier).toBe("Acme");
  expect(Object.isFrozen(r.current.criteria)).toBe(true);
});
it("limits the output to criteria metadata with no result fields", () => {
  const r = compareSavedCriteria(def(), def({ supplier: "Acme" }));
  expect(Object.keys(r)).toEqual([
    "saved",
    "current",
    "rows",
    "counts",
    "hasChanges",
  ]);
  expect(JSON.stringify(r)).not.toMatch(
    /potential|recovered|citations|cookie|token|cursor|reason|evaluations/,
  );
});
it("allows only the explicitly synthetic size 2 when requested", () => {
  expect(() => compareSavedCriteria(def({}, "anomalies", 2), def())).toThrow();
  expect(
    compareSavedCriteria(
      def({}, "anomalies", 2),
      def({}, "anomalies", 20),
      true,
    ).hasChanges,
  ).toBe(true);
});
