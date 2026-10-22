"use client";
import { useEffect, useId, useRef } from "react";
import {
  isRenameAttempt,
  type SavedViewAttempt,
  type ReconciliationResult,
} from "@/lib/saved-view-reconciliation";
const messages = {
  PROPOSED_CRITERIA_OBSERVED: "Proposed criteria found in the saved view.",
  PREVIOUS_CRITERIA_STILL_OBSERVED:
    "Previous criteria are still recorded as of the latest read.",
  PROPOSED_NAME_OBSERVED: "Proposed name found in the saved view.",
  PREVIOUS_NAME_STILL_OBSERVED:
    "Previous name is still recorded as of the latest read.",
  DIFFERENT_SAVED_STATE_OBSERVED:
    "The saved view differs from both compared states.",
  RECONCILIATION_UNAVAILABLE: "Unable to determine the saved state.",
};
export function SavedViewReconciliation({
  attempt,
  result,
  checking,
  canReview,
  onCheck,
  onReview,
  onClose,
}: {
  attempt: SavedViewAttempt;
  result: ReconciliationResult | null;
  checking: boolean;
  canReview: boolean;
  onCheck: () => void;
  onReview: () => void;
  onClose: () => void;
}) {
  const id = useId(),
    heading = useRef<HTMLHeadingElement>(null);
  const rename = isRenameAttempt(attempt);
  useEffect(() => {
    heading.current?.focus();
  }, []);
  return (
    <section
      className={`p-reconciliation ${result?.kind === "RECONCILIATION_UNAVAILABLE" ? "unavailable" : ""}`}
      aria-labelledby={id}
    >
      <h4 id={id} ref={heading} tabIndex={-1}>
        Saved view reconciliation
      </h4>
      <p>
        <strong>{attempt.before.name}</strong> · Version before attempt{" "}
        {attempt.before.revision}
      </p>
      {rename && (
        <>
          <p>
            Operation: <strong>Rename saved view</strong>
          </p>
          <p>
            Old name: <strong>{attempt.before.name}</strong>
            <br />
            Proposed new name: <strong>{attempt.proposed_name}</strong>
          </p>
        </>
      )}
      <p className="p-muted">
        Local attempt reference {attempt.local_id}. UI correlation only; not a
        server transaction ID.
      </p>
      <p>
        {rename
          ? attempt.issue === "CONFLICT"
            ? "The rename request returned a conflict. Read the current state before reviewing again."
            : "The rename response is unconfirmed. The write may have reached the server."
          : attempt.issue === "CONFLICT"
            ? "The replacement request returned a version conflict. Read the current state before reviewing again."
            : "The replacement response is unconfirmed. The write may have reached the server."}
      </p>
      <div role="status" aria-live="polite" aria-atomic="true">
        {checking ? (
          <p>Checking the saved view with one authorized read…</p>
        ) : result ? (
          <>
            <p>
              <strong>{messages[result.kind]}</strong>
            </p>
            {result.observed_revision !== null && (
              <p>
                Observed version {result.observed_revision}.{" "}
                {rename
                  ? result.criteria_unchanged
                    ? "Saved criteria remain unchanged."
                    : "Saved criteria have changed since the attempt."
                  : result.proposed_matches
                    ? "Recorded criteria match the proposal."
                    : result.previous_matches
                      ? "Recorded criteria match the previous criteria."
                      : "Recorded criteria match neither criteria snapshot."}
              </p>
            )}
            {(result.kind === "PROPOSED_CRITERIA_OBSERVED" ||
              result.kind === "PROPOSED_NAME_OBSERVED") && (
              <p>
                Certainty: current state observed by a fresh read. This does not
                prove that this particular attempt performed the write.
              </p>
            )}
            {(result.kind === "PREVIOUS_CRITERIA_STILL_OBSERVED" ||
              result.kind === "PREVIOUS_NAME_STILL_OBSERVED") && (
              <p>
                Certainty:{" "}
                {rename
                  ? "previous name and unchanged criteria"
                  : "previous criteria"}{" "}
                observed at the original version. This is not proof that the
                write failed; delayed or concurrent activity remains possible.
              </p>
            )}
            {result.kind === "DIFFERENT_SAVED_STATE_OBSERVED" && (
              <p>
                New review required. A concurrent change, a later update or an
                unexpected revision may explain this state. No version will be
                overwritten.{" "}
                {rename
                  ? "A matching name alone does not establish the outcome; criteria and revision must also be coherent."
                  : "Matching criteria at a later revision do not establish this attempt’s outcome."}
              </p>
            )}
            {result.kind === "RECONCILIATION_UNAVAILABLE" && (
              <p>
                Read{" "}
                {result.reason === "TIMEOUT"
                  ? "timed out"
                  : result.reason === "CANCELLED"
                    ? "was cancelled"
                    : result.reason === "NOT_FOUND"
                      ? "could not find an accessible view"
                      : "could not be verified"}
                . Certainty: the write outcome remains unknown. This read does
                not establish write failure.
              </p>
            )}
          </>
        ) : (
          <p>Outcome uncertain. No reconciliation read has completed.</p>
        )}
      </div>
      <p>
        {rename
          ? "No rename is retried. Any new rename requires a fresh read, review and explicit confirmation."
          : "No write is retried. Any new replacement requires a fresh comparison and explicit confirmation."}
      </p>
      <div className="p-diff-actions">
        <button disabled={checking} onClick={onCheck}>
          {rename ? "Check rename state" : "Check saved view state"}
        </button>
        <button disabled={checking || !canReview} onClick={onReview}>
          {rename ? "Review rename again" : "Review changes again"}
        </button>
        <button onClick={onClose}>Close summary</button>
      </div>
    </section>
  );
}
