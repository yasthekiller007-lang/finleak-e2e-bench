/** Pure criteria/state contracts; no native database or OIDC evidence. */
import { expect, it } from "vitest";
import {
  replacementAttempt,
  reconcileSavedReplacement,
  unavailableReconciliation,
} from "@/lib/saved-view-reconciliation";
import { savedDefinition, type SavedView } from "@/lib/saved-views";
const org = "aaaaaaaa-0000-4000-8000-000000000001",
  owner = "aaaaaaaa-0000-4000-8000-000000000002";
const definition = (currency: string) =>
  savedDefinition({
    view_type: "anomalies",
    format_version: 1,
    criteria: { currency },
    page_size: 20,
  });
const before: SavedView = {
  ...definition("USD"),
  id: "aaaaaaaa-0000-4000-8000-000000000003",
  organization_id: org,
  user_id: owner,
  name: "CFO watchlist",
  revision: 4,
  created_at: "2026-10-19T00:00:00Z",
  updated_at: "2026-10-19T00:00:00Z",
};
const proposed = definition("EUR");
const read = (patch: Partial<SavedView> = {}) => ({
  ...before,
  ...definition("EUR"),
  revision: 5,
  ...patch,
});
const reconcile = (row: unknown) =>
  reconcileSavedReplacement(before, proposed, row, org, owner);
it("captures only validated criteria and ordinary view metadata, copied and frozen", () => {
  const source = structuredClone(before),
    target = structuredClone(proposed);
  const attempt = replacementAttempt(source, target, org, owner, "local-1");
  source.criteria.currency = "GBP";
  target.criteria.currency = "CAD";
  expect(attempt.before.criteria.currency).toBe("USD");
  expect(attempt.proposed.criteria.currency).toBe("EUR");
  expect(Object.isFrozen(attempt.proposed.criteria)).toBe(true);
  expect(Object.isFrozen(attempt.before)).toBe(true);
  expect(Object.keys(attempt).sort()).toEqual([
    "before",
    "issue",
    "local_id",
    "proposed",
  ]);
});
it("observes the proposal at the expected increment without returning attribution or financial results", () => {
  expect(reconcile(read())).toEqual({
    kind: "PROPOSED_CRITERIA_OBSERVED",
    observed_revision: 5,
    proposed_matches: true,
    previous_matches: false,
    reason: "EXPECTED_INCREMENT",
  });
  expect(Object.keys(reconcile(read()))).not.toContain("transaction_id");
});
it("observes previous criteria at unchanged revision without concluding failure", () => {
  expect(reconcile(before)).toMatchObject({
    kind: "PREVIOUS_CRITERIA_STILL_OBSERVED",
    observed_revision: 4,
    previous_matches: true,
  });
});
it.each([
  ["other criteria", { ...definition("GBP"), revision: 5 }],
  ["proposal at unchanged revision", { revision: 4 }],
  ["previous criteria after increment", { ...definition("USD"), revision: 5 }],
  ["proposal after multiple increments", { revision: 7 }],
  [
    "previous criteria after multiple increments",
    { ...definition("USD"), revision: 7 },
  ],
])("reports different full saved state for %s", (_, patch) => {
  expect(reconcile(read(patch))).toMatchObject({
    kind: "DIFFERENT_SAVED_STATE_OBSERVED",
    observed_revision: patch.revision,
  });
});
it("refuses a revision older than the starting snapshot", () => {
  expect(reconcile(read({ revision: 3 }))).toMatchObject({
    kind: "RECONCILIATION_UNAVAILABLE",
    reason: "STALE_REVISION",
    observed_revision: null,
  });
});
it.each([
  ["homonymous different ID", { id: "aaaaaaaa-0000-4000-8000-000000000004" }],
  ["wrong organization", { organization_id: owner }],
  ["wrong owner", { user_id: org }],
  ["wrong type", { view_type: "review" }],
  ["wrong format", { format_version: 2 }],
  ["fractional revision", { revision: 4.5 }],
  ["missing revision", { revision: undefined }],
  ["unsafe revision", { revision: Number.MAX_SAFE_INTEGER + 1 }],
  ["unknown money", { potential_amount: "1000.00" }],
  ["unknown token", { access_token: "forbidden" }],
  ["unknown cursor", { after: "forbidden" }],
  ["invalid criterion", { criteria: { currency: "bad" } }],
])("refuses %s without copying unverified data to the result", (_, patch) => {
  expect(reconcile({ ...read(), ...patch })).toEqual(
    unavailableReconciliation("UNVERIFIED_RECORD"),
  );
});
it.each([null, [], {}, "bad"])(
  "refuses malformed observed records %j",
  (value) => {
    expect(reconcile(value).kind).toBe("RECONCILIATION_UNAVAILABLE");
  },
);
it("uses existing normalization, not displayed labels", () => {
  const a = { ...before, criteria: { q: "invoice", currency: "USD" } };
  const b = { ...proposed, criteria: { q: " invoice ", currency: "EUR" } };
  expect(
    reconcileSavedReplacement(
      a,
      b,
      { ...read(), criteria: { q: "invoice", currency: "EUR" } },
      org,
      owner,
    ).kind,
  ).toBe("PROPOSED_CRITERIA_OBSERVED");
});
it("rejects no-op attempts, malformed contexts and unsafe starting revision", () => {
  expect(() =>
    replacementAttempt(before, definition("USD"), org, owner, "local-1"),
  ).toThrow("No changes");
  expect(() =>
    replacementAttempt(before, proposed, org, owner, "Bearer secret"),
  ).toThrow();
  expect(() =>
    replacementAttempt(
      { ...before, revision: Number.MAX_SAFE_INTEGER },
      proposed,
      org,
      owner,
      "local-1",
    ),
  ).toThrow();
  expect(
    reconcileSavedReplacement(
      { ...before, user_id: org },
      proposed,
      read(),
      org,
      owner,
    ).kind,
  ).toBe("RECONCILIATION_UNAVAILABLE");
});
it("preserves exact review-route implicit criteria semantics", () => {
  const start = { ...before, view_type: "review", criteria: {} };
  const target = {
    ...definition("EUR"),
    view_type: "review",
    criteria: { needs_review: false },
  };
  expect(
    reconcileSavedReplacement(
      start,
      target,
      { ...read(), ...target },
      org,
      owner,
    ).kind,
  ).toBe("PROPOSED_CRITERIA_OBSERVED");
});
