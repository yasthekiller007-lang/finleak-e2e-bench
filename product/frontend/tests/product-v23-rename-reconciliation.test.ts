/** Pure rename contracts; no native PostgreSQL/identity evidence. */
import { expect, it } from "vitest";
import {
  renameAttempt,
  reconcileSavedRename,
  isRenameAttempt,
  unavailableReconciliation,
} from "@/lib/saved-view-reconciliation";
import { savedDefinition, type SavedView } from "@/lib/saved-views";
const org = "aaaaaaaa-0000-4000-8000-000000000001",
  owner = "aaaaaaaa-0000-4000-8000-000000000002";
const definition = savedDefinition({
  view_type: "anomalies",
  format_version: 1,
  criteria: { currency: "USD" },
  page_size: 20,
});
const before: SavedView = {
  ...definition,
  id: "aaaaaaaa-0000-4000-8000-000000000003",
  organization_id: org,
  user_id: owner,
  name: "CFO watchlist",
  revision: 4,
  created_at: "2026-10-19T00:00:00Z",
  updated_at: "2026-10-19T00:00:00Z",
};
const proposed = "CFO monthly review";
const fresh = (patch: Partial<SavedView> = {}) => ({
  ...before,
  name: proposed,
  revision: 5,
  ...patch,
});
const reconcile = (observed: unknown) =>
  reconcileSavedRename(before, proposed, observed, org, owner);
it("captures a frozen name-only attempt with normalized name and stable prior criteria", () => {
  const source = structuredClone(before);
  const attempt = renameAttempt(
    source,
    " ＣＦＯ   monthly review ",
    org,
    owner,
    "local-1",
  );
  source.criteria.currency = "EUR";
  expect(isRenameAttempt(attempt)).toBe(true);
  expect(attempt.proposed_name).toBe(proposed);
  expect(attempt.before.criteria.currency).toBe("USD");
  expect(Object.isFrozen(attempt.before.criteria)).toBe(true);
  expect(Object.keys(attempt).sort()).toEqual([
    "before",
    "issue",
    "local_id",
    "operation",
    "proposed_name",
  ]);
});
it("observes the proposed name only with the expected revision and unchanged criteria", () => {
  expect(reconcile(fresh())).toEqual({
    kind: "PROPOSED_NAME_OBSERVED",
    observed_revision: 5,
    proposed_matches: true,
    previous_matches: false,
    criteria_unchanged: true,
    reason: "EXPECTED_INCREMENT",
  });
});
it("observes the previous name and unchanged criteria without concluding write failure", () => {
  expect(reconcile(before)).toMatchObject({
    kind: "PREVIOUS_NAME_STILL_OBSERVED",
    observed_revision: 4,
    criteria_unchanged: true,
  });
});
it.each([
  ["other name", { name: "Another tab" }],
  ["proposal without increment", { revision: 4 }],
  ["previous name after increment", { name: before.name }],
  ["proposal after several increments", { revision: 7 }],
  [
    "same proposed name but different currency",
    { criteria: { currency: "EUR" } },
  ],
  ["same proposed name but different page size", { page_size: 50 }],
  [
    "old name and revision but changed criteria",
    { name: before.name, revision: 4, criteria: { currency: "GBP" } },
  ],
])("reports divergent state for %s", (_label, patch) => {
  expect(reconcile(fresh(patch))).toMatchObject({
    kind: "DIFFERENT_SAVED_STATE_OBSERVED",
  });
});
it("preserves structured document identity even when all displayed names match", () => {
  const start = {
    ...before,
    criteria: { invoice_source_id: "bbbbbbbb-0000-4000-8000-000000000001" },
  };
  const changed = {
    ...fresh(),
    criteria: { invoice_source_id: "bbbbbbbb-0000-4000-8000-000000000002" },
  };
  expect(
    reconcileSavedRename(start, proposed, changed, org, owner),
  ).toMatchObject({
    kind: "DIFFERENT_SAVED_STATE_OBSERVED",
    criteria_unchanged: false,
  });
});
it.each([
  ["homonymous different view", { id: "bbbbbbbb-0000-4000-8000-000000000001" }],
  ["foreign owner", { user_id: org }],
  ["foreign organization", { organization_id: owner }],
  ["wrong format", { format_version: 2 }],
  ["wrong type", { view_type: "review" }],
  ["fractional revision", { revision: 4.5 }],
  ["missing revision", { revision: undefined }],
  ["unvalidated name", { name: " ＣＦＯ monthly review " }],
  ["secret field", { access_token: "SECRET_SENTINEL" }],
  ["financial result", { potential_amount: "1000.00" }],
])("refuses %s without copying unverified values", (_label, patch) => {
  expect(reconcile({ ...fresh(), ...patch })).toEqual(
    unavailableReconciliation("UNVERIFIED_RECORD"),
  );
});
it("refuses older reads rather than treating them as current", () => {
  expect(reconcile(fresh({ revision: 3 }))).toEqual(
    unavailableReconciliation("STALE_REVISION"),
  );
});
it.each(["CFO watchlist", " ＣＦＯ   watchlist "])(
  "rejects an effective no-op %s",
  (name) => {
    expect(() => renameAttempt(before, name, org, owner, "local-1")).toThrow(
      "No name changes to save",
    );
  },
);
it.each(["", "\u200bHidden", "x".repeat(81)])(
  "rejects invalid names %j",
  (name) => {
    expect(() => renameAttempt(before, name, org, owner, "local-1")).toThrow();
  },
);
it("keeps a case-only display rename meaningful without inventing uniqueness rules", () => {
  const attempt = renameAttempt(before, "CFO WATCHLIST", org, owner, "local-1");
  expect(attempt.proposed_name).toBe("CFO WATCHLIST");
});
it("uses existing route defaults and criteria canonicalization", () => {
  const start = { ...before, view_type: "review", criteria: {} };
  const result = reconcileSavedRename(
    start,
    proposed,
    {
      ...fresh(),
      view_type: "review",
      criteria: { needs_review: true, sort: "newest" },
    },
    org,
    owner,
  );
  expect(result.kind).toBe("PROPOSED_NAME_OBSERVED");
});
it("rejects malformed contexts and unsafe starting revisions", () => {
  expect(() =>
    renameAttempt(
      { ...before, revision: Number.MAX_SAFE_INTEGER },
      proposed,
      org,
      owner,
      "local-1",
    ),
  ).toThrow();
  expect(() =>
    renameAttempt(before, proposed, org, owner, "Bearer secret"),
  ).toThrow();
  expect(
    reconcileSavedRename(
      { ...before, user_id: org },
      proposed,
      fresh(),
      org,
      owner,
    ).kind,
  ).toBe("RECONCILIATION_UNAVAILABLE");
});
