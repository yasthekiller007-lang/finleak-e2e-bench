/** Pure query-edit contracts, not financial policy or native PostgreSQL tests. */
import { expect, it } from "vitest";
import {
  criterionAction,
  withoutCriterion,
  type RemovableCriterion,
} from "@/lib/criteria-removal";
import { validatedCriteria, viewDefaults } from "@/lib/exception-view-url";
import type { ExceptionQuery } from "@/lib/server-exceptions";
const id = "00000000-0000-4000-8000-000000000500",
  contract = "00000000-0000-4000-8000-000000000505";
const combined: ExceptionQuery = {
  q: "Enterprise",
  supplier: "AcmeCloud",
  invoice_source_id: id,
  invoice_document_id: id,
  contract_source_id: contract,
  currency: "USD",
  outcome: "POTENTIAL_LEAKAGE",
  decision_status: "unrecorded",
  created_from: "2026-10-01T00:00:00Z",
  created_to: "2026-11-01T00:00:00Z",
  current: true,
  needs_review: true,
  sort: "amount_high",
};
it.each<RemovableCriterion>([
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
])("removes only %s, preserving other criteria and order", (field) => {
  const before = JSON.stringify(combined),
    expected = validatedCriteria(combined, "anomalies");
  delete expected[field];
  if (field === "needs_review") expected.needs_review = false;
  expect(withoutCriterion(combined, field, "anomalies")).toEqual(expected);
  expect(JSON.stringify(combined)).toBe(before);
  expect(criterionAction(combined, field, "anomalies")?.label).toContain(
    "Remove",
  );
});
it("preserves independent contract and document constraints when removing their related selectors", () => {
  expect(
    withoutCriterion(combined, "supplier", "anomalies").contract_source_id,
  ).toBe(contract);
  expect(
    withoutCriterion(combined, "invoice_source_id", "anomalies")
      .invoice_document_id,
  ).toBe(id);
  expect(
    withoutCriterion(combined, "invoice_document_id", "anomalies")
      .invoice_source_id,
  ).toBe(id);
  expect(
    withoutCriterion(combined, "contract_source_id", "anomalies")
      .missing_contract,
  ).toBeUndefined();
});
it("removes the missing-association restriction without choosing or approving a contract", () => {
  const f = withoutCriterion(
    { missing_contract: true, currency: "EUR" },
    "missing_contract",
    "anomalies",
  );
  expect(f).toEqual({ ...viewDefaults("anomalies"), currency: "EUR" });
  expect(f.contract_source_id).toBeUndefined();
  expect(() =>
    withoutCriterion(
      { missing_contract: true, contract_source_id: contract },
      "missing_contract",
      "anomalies",
    ),
  ).toThrow();
});
it("never offers removal of implicit route defaults; restores explicit review overrides", () => {
  expect(criterionAction({}, "needs_review", "review")).toBeNull();
  expect(
    criterionAction({ needs_review: true }, "needs_review", "review"),
  ).toBeNull();
  expect(
    criterionAction({ needs_review: false }, "needs_review", "review")?.label,
  ).toBe("Restore default needs review filter");
  expect(
    withoutCriterion(
      { needs_review: false, currency: "USD" },
      "needs_review",
      "review",
    ),
  ).toEqual({ ...viewDefaults("review"), currency: "USD" });
  expect(criterionAction({}, "current", "anomalies")).toBeNull();
  expect(
    criterionAction({ missing_contract: false }, "missing_contract", "review"),
  ).toBeNull();
});
it.each(["organization", "org", "sort", "limit", "__proto__", "constructor"])(
  "refuses non-filter/prototype action %s",
  (key) =>
    expect(() =>
      withoutCriterion(combined, key as RemovableCriterion, "anomalies"),
    ).toThrow(),
);
it("rejects absent filters and invalid snapshots rather than widening silently", () => {
  expect(() => withoutCriterion({}, "supplier", "anomalies")).toThrow();
  expect(() =>
    withoutCriterion({ currency: "invalid" }, "currency", "anomalies"),
  ).toThrow();
});
