/** Ephemeral criteria-only reconciliation. A GET is never transaction attribution. */
import { compareSavedCriteria, definitionKey } from "@/lib/saved-view-diff";
import {
  parseSavedView,
  savedDefinition,
  savedName,
  type SavedDefinition,
  type SavedView,
} from "@/lib/saved-views";

export type ReplacementIssue =
  | "RESPONSE_PENDING"
  | "TIMEOUT"
  | "NETWORK_ERROR"
  | "CONFLICT"
  | "HTTP_ERROR"
  | "RESPONSE_UNVERIFIED";
export type ReplacementAttempt = Readonly<{
  local_id: string;
  before: SavedView;
  proposed: SavedDefinition;
  issue: ReplacementIssue;
}>;
export type ReconciliationKind =
  | "PROPOSED_CRITERIA_OBSERVED"
  | "PREVIOUS_CRITERIA_STILL_OBSERVED"
  | "PROPOSED_NAME_OBSERVED"
  | "PREVIOUS_NAME_STILL_OBSERVED"
  | "DIFFERENT_SAVED_STATE_OBSERVED"
  | "RECONCILIATION_UNAVAILABLE";
export type ReadLimit =
  | "READ_FAILED"
  | "TIMEOUT"
  | "CANCELLED"
  | "NOT_FOUND"
  | "UNVERIFIED_RECORD"
  | "STALE_REVISION";
export type ReconciliationResult = {
  kind: ReconciliationKind;
  observed_revision: number | null;
  proposed_matches: boolean | null;
  previous_matches: boolean | null;
  criteria_unchanged?: boolean;
  reason:
    | "EXPECTED_INCREMENT"
    | "UNCHANGED_REVISION"
    | "OTHER_STATE_OR_REVISION"
    | ReadLimit;
};
export type RenameAttempt = Readonly<{
  operation: "rename";
  local_id: string;
  before: SavedView;
  proposed_name: string;
  issue: ReplacementIssue;
}>;
export type SavedViewAttempt = ReplacementAttempt | RenameAttempt;
export const isRenameAttempt = (
  attempt: SavedViewAttempt | null,
): attempt is RenameAttempt =>
  Boolean(attempt && "operation" in attempt && attempt.operation === "rename");
export const viewDefinition = (row: SavedView): SavedDefinition => ({
  view_type: row.view_type,
  format_version: row.format_version,
  criteria: row.criteria,
  page_size: row.page_size,
});
export function renameAttempt(
  before: unknown,
  proposedName: string,
  org: string,
  owner: string,
  localId: string,
  demo = false,
): RenameAttempt {
  const row = parseSavedView(before, org, owner, demo),
    name = savedName(proposedName);
  if (
    !/^[a-zA-Z0-9-]{1,80}$/.test(localId) ||
    row.revision >= Number.MAX_SAFE_INTEGER
  )
    throw Error("Rename context cannot be verified.");
  if (name === row.name) throw Error("No name changes to save");
  const definition = savedDefinition(viewDefinition(row), demo);
  Object.freeze(definition.criteria);
  return Object.freeze({
    operation: "rename",
    local_id: localId,
    before: Object.freeze({ ...row, ...definition }),
    proposed_name: name,
    issue: "RESPONSE_PENDING",
  });
}
export function reconcileSavedRename(
  before: unknown,
  proposedName: string,
  observed: unknown,
  org: string,
  owner: string,
  demo = false,
): ReconciliationResult {
  try {
    const attempt = renameAttempt(
      before,
      proposedName,
      org,
      owner,
      "validation",
      demo,
    );
    const row = parseSavedView(observed, org, owner, demo);
    if (
      row.id !== attempt.before.id ||
      row.view_type !== attempt.before.view_type ||
      row.format_version !== attempt.before.format_version
    )
      return unavailableReconciliation("UNVERIFIED_RECORD");
    if (row.revision < attempt.before.revision)
      return unavailableReconciliation("STALE_REVISION");
    const criteria =
      definitionKey(viewDefinition(row), demo) ===
      definitionKey(viewDefinition(attempt.before), demo);
    const proposed = row.name === attempt.proposed_name,
      previous = row.name === attempt.before.name;
    const expected = row.revision === attempt.before.revision + 1,
      unchanged = row.revision === attempt.before.revision;
    return {
      kind:
        expected && proposed && criteria
          ? "PROPOSED_NAME_OBSERVED"
          : unchanged && previous && criteria
            ? "PREVIOUS_NAME_STILL_OBSERVED"
            : "DIFFERENT_SAVED_STATE_OBSERVED",
      observed_revision: row.revision,
      proposed_matches: proposed,
      previous_matches: previous,
      criteria_unchanged: criteria,
      reason:
        expected && proposed && criteria
          ? "EXPECTED_INCREMENT"
          : unchanged && previous && criteria
            ? "UNCHANGED_REVISION"
            : "OTHER_STATE_OR_REVISION",
    };
  } catch {
    return unavailableReconciliation("UNVERIFIED_RECORD");
  }
}
export const unavailableReconciliation = (
  reason: ReadLimit,
): ReconciliationResult => ({
  kind: "RECONCILIATION_UNAVAILABLE",
  observed_revision: null,
  proposed_matches: null,
  previous_matches: null,
  reason,
});
export function replacementAttempt(
  before: unknown,
  proposed: unknown,
  org: string,
  owner: string,
  localId: string,
  demo = false,
): ReplacementAttempt {
  const row = parseSavedView(before, org, owner, demo);
  if (
    !/^[a-zA-Z0-9-]{1,80}$/.test(localId) ||
    row.revision >= Number.MAX_SAFE_INTEGER
  )
    throw Error("Replacement context cannot be verified.");
  const comparison = compareSavedCriteria(
    {
      view_type: row.view_type,
      format_version: row.format_version,
      criteria: row.criteria,
      page_size: row.page_size,
    },
    proposed,
    demo,
  );
  if (!comparison.hasChanges) throw Error("No changes to save");
  return Object.freeze({
    local_id: localId,
    before: Object.freeze({ ...row, ...comparison.saved }),
    proposed: comparison.current,
    issue: "RESPONSE_PENDING",
  });
}
export function reconcileSavedReplacement(
  before: unknown,
  proposed: unknown,
  observed: unknown,
  org: string,
  owner: string,
  demo = false,
): ReconciliationResult {
  try {
    const attempt = replacementAttempt(
      before,
      proposed,
      org,
      owner,
      "validation",
      demo,
    );
    const row = parseSavedView(observed, org, owner, demo);
    if (
      row.id !== attempt.before.id ||
      row.view_type !== attempt.before.view_type ||
      row.format_version !== attempt.before.format_version
    )
      return unavailableReconciliation("UNVERIFIED_RECORD");
    if (row.revision < attempt.before.revision)
      return unavailableReconciliation("STALE_REVISION");
    const key = definitionKey(
      {
        view_type: row.view_type,
        format_version: row.format_version,
        criteria: row.criteria,
        page_size: row.page_size,
      },
      demo,
    );
    const previous = definitionKey(
      {
        view_type: attempt.before.view_type,
        format_version: attempt.before.format_version,
        criteria: attempt.before.criteria,
        page_size: attempt.before.page_size,
      },
      demo,
    );
    const proposedMatches = key === definitionKey(attempt.proposed, demo),
      previousMatches = key === previous;
    const unchanged = row.revision === attempt.before.revision;
    const expected = row.revision === attempt.before.revision + 1;
    return {
      kind:
        expected && proposedMatches
          ? "PROPOSED_CRITERIA_OBSERVED"
          : unchanged && previousMatches
            ? "PREVIOUS_CRITERIA_STILL_OBSERVED"
            : "DIFFERENT_SAVED_STATE_OBSERVED",
      observed_revision: row.revision,
      proposed_matches: proposedMatches,
      previous_matches: previousMatches,
      reason:
        expected && proposedMatches
          ? "EXPECTED_INCREMENT"
          : unchanged && previousMatches
            ? "UNCHANGED_REVISION"
            : "OTHER_STATE_OR_REVISION",
    };
  } catch {
    return unavailableReconciliation("UNVERIFIED_RECORD");
  }
}
