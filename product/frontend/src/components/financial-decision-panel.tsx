"use client";

import { useEffect, useRef, useState } from "react";
import type { Assessment } from "@/lib/financial";
import {
  WorkspaceError,
  type Decision,
  type WorkspaceGateway,
} from "@/lib/product-workspace";
import { ProductIcon } from "@/components/product-icons";

type Phase =
  | "ready"
  | "saving"
  | "saved"
  | "conflict"
  | "unknown"
  | "accepted"
  | "reading"
  | "observed"
  | "forbidden";
type Receipt = { id: string; status: Decision["status"]; reason: string };
function receipt(value: unknown, status: Decision["status"]): Receipt | null {
  if (!value || typeof value !== "object") return null;
  const item = value as Record<string, unknown>;
  return typeof item.id === "string" &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
      item.id,
    ) &&
    item.status === status &&
    typeof item.reason === "string"
    ? (item as Receipt)
    : null;
}

/** No retries of writes. A lost response is reconciled through GET and explicit new intent. */
export function FinancialDecisionPanel({
  detail,
  orgId,
  role,
  gateway,
  demo,
  status,
  onDecision,
}: {
  detail: Assessment;
  orgId: string;
  role: string;
  gateway: WorkspaceGateway;
  demo: boolean;
  status: React.ReactNode;
  onDecision: (updated: Assessment) => void;
}) {
  const [reason, setReason] = useState(""),
    [decision, setDecision] = useState<Decision["status"]>("confirmed"),
    [acknowledged, setAcknowledged] = useState(false);
  const [phase, setPhase] = useState<Phase>("ready"),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [accepted, setAccepted] = useState<Receipt | null>(null);
  const controller = useRef<AbortController | null>(null),
    busy = useRef(false),
    submitted = useRef<Receipt | null>(null);
  useEffect(() => {
    const current = new AbortController();
    controller.current = current;
    return () => current.abort();
  }, [orgId, detail.id]);
  const writable = role === "owner" || role === "admin";
  const allowed = writable && detail.potential !== null && !detail.stale;
  const locked = phase !== "ready";
  const success = demo
    ? "Synthetic decision saved locally. No backend record was changed."
    : "Decision recorded. Historical calculations and evidence remain unchanged.";
  function recordObserved(updated: Assessment) {
    onDecision(updated);
    setAcknowledged(false);
    if (
      submitted.current &&
      updated.decision_id === submitted.current.id &&
      updated.status === submitted.current.status
    ) {
      setPhase("saved");
      setNotice(success);
      setError("");
      setReason("");
    } else {
      setPhase("observed");
      setNotice(
        "Latest decision loaded. Review its audit entry before preparing a new decision. A changed ID alone does not establish who submitted it.",
      );
      setError(
        submitted.current
          ? "The latest decision differs from the acknowledged receipt. No additional decision was submitted."
          : "",
      );
    }
  }
  async function recheck() {
    if (busy.current) return;
    const signal = controller.current!.signal;
    busy.current = true;
    setPhase("reading");
    setError("");
    try {
      const updated = await gateway.assessment(orgId, detail.id, signal);
      if (!signal.aborted) recordObserved(updated);
    } catch {
      if (!signal.aborted) {
        setPhase(submitted.current ? "accepted" : "unknown");
        setError(
          "The latest decision could not be read. Submission remains locked. No write was retried.",
        );
      }
    } finally {
      busy.current = false;
    }
  }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!allowed || locked || !reason.trim() || !acknowledged || busy.current)
      return;
    const signal = controller.current!.signal;
    busy.current = true;
    setPhase("saving");
    setError("");
    setNotice("");
    submitted.current = null;
    setAccepted(null);
    try {
      const result = await gateway.decide(
        orgId,
        detail.id,
        {
          status: decision,
          reason: reason.trim(),
          expected_decision: detail.decision_id,
        },
        signal,
      );
      if (signal.aborted) return;
      const verified = receipt(result, decision);
      if (!verified) {
        setPhase("unknown");
        setError(
          "The decision response could not be verified. Its outcome is unknown. Reload the current decision; do not resubmit.",
        );
        return;
      }
      submitted.current = verified;
      setAccepted(verified);
      try {
        const updated = await gateway.assessment(orgId, detail.id, signal);
        if (!signal.aborted) recordObserved(updated);
      } catch {
        if (!signal.aborted) {
          setPhase("accepted");
          setError(
            demo
              ? "The local synthetic decision was acknowledged, but its latest state could not be read. Do not resubmit. Reload the current decision to verify it."
              : "The backend acknowledged this decision, but its latest state could not be read. Do not resubmit. Reload the current decision to verify it.",
          );
        }
      }
    } catch (cause) {
      if (signal.aborted) return;
      const reference =
        cause instanceof WorkspaceError && cause.requestId
          ? ` Reference: ${cause.requestId}`
          : "";
      if (cause instanceof WorkspaceError && cause.status === 409) {
        setPhase("conflict");
        setError(`${cause.message} No automatic retry was made.${reference}`);
      } else if (
        cause instanceof WorkspaceError &&
        (cause.status === 401 || cause.status === 403)
      ) {
        setPhase("forbidden");
        setError(
          `${cause.message} Submission is locked; sign in or refresh your permissions.${reference}`,
        );
      } else if (
        cause instanceof WorkspaceError &&
        [400, 404, 415, 422].includes(cause.status)
      ) {
        setPhase("ready");
        setError(`${cause.message}${reference}`);
      } else {
        setPhase("unknown");
        setError(
          `The save outcome is unknown. The response may have been lost after a commit. Reload the current decision before preparing another submission.${reference}`,
        );
      }
    } finally {
      busy.current = false;
    }
  }
  return (
    <section className="p-card p-decision-card">
      <div className="p-decision-icon">
        <ProductIcon name="review" size={23} />
      </div>
      <p className="p-eyebrow">HUMAN JUDGMENT</p>
      <h3>Your decision matters.</h3>
      <p>
        Confirm the financial finding only after reviewing its source evidence.
        This does not recognize recovered funds.
      </p>
      {status}
      {notice && (
        <p className="p-success-message" role="status">
          {notice}
        </p>
      )}
      {accepted && (
        <p className="p-decision-receipt">
          {demo ? "Synthetic receipt" : "Backend acknowledgment"}
          <code>{accepted.id}</code>Current state{" "}
          {phase === "saved"
            ? "matched by a separate read"
            : "not yet verified against this receipt"}
          . No restart or database durability is inferred.
        </p>
      )}
      {error && (
        <div className="p-error" role="alert">
          <div>
            <strong>Review submission status</strong>
            <p>{error}</p>
          </div>
        </div>
      )}
      {["conflict", "unknown", "accepted", "reading"].includes(phase) && (
        <button
          className="p-button p-reconcile"
          disabled={phase === "reading"}
          onClick={() => void recheck()}
        >
          {phase === "reading"
            ? "Reading current decision…"
            : "Reload current decision"}
        </button>
      )}
      {["saved", "observed"].includes(phase) && allowed && (
        <button
          className="p-reconcile"
          onClick={() => {
            setPhase("ready");
            setReason("");
            setAcknowledged(false);
            setNotice("");
            setError("");
            submitted.current = null;
            setAccepted(null);
          }}
        >
          Prepare another decision
        </button>
      )}
      {phase === "forbidden" && (
        <a className="p-text-link" href="/login">
          Return to sign in
        </a>
      )}
      {allowed ? (
        <form onSubmit={save}>
          <label>
            Finding decision
            <select
              aria-label="Finding decision"
              value={decision}
              disabled={locked}
              onChange={(e) =>
                setDecision(e.target.value as Decision["status"])
              }
            >
              <option value="confirmed">Confirm discrepancy</option>
              <option value="needs_review">Request further review</option>
              <option value="false_positive">Dismiss finding</option>
            </select>
          </label>
          <label>
            Reason for decision
            <textarea
              aria-label="Reason for decision"
              required
              maxLength={2000}
              rows={4}
              disabled={locked}
              placeholder="Explain the evidence behind your decision…"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
          <label className="p-acknowledgment">
            <input
              type="checkbox"
              checked={acknowledged}
              disabled={locked}
              onChange={(e) => setAcknowledged(e.target.checked)}
            />
            I reviewed the source evidence and current assessment.
          </label>
          {decision === "false_positive" && (
            <p className="p-warning">
              Dismissal removes this finding from current potential totals.
              Historical evidence remains unchanged.
            </p>
          )}
          <button
            className="p-button"
            disabled={locked || !reason.trim() || !acknowledged}
          >
            {phase === "saving"
              ? "Recording decision…"
              : demo
                ? "Save demo decision"
                : "Record financial decision"}
            <ProductIcon name="arrow" size={16} />
          </button>
          <small>
            {demo
              ? "Local synthetic action only."
              : "Attributed by the backend. Concurrent decisions are checked."}
          </small>
        </form>
      ) : (
        <p className="p-role-note">
          {!writable
            ? "An owner or administrator must finalize financial finding decisions. Your role can inspect the evidence."
            : "Resolve the missing or changed inputs before making a financial decision."}
        </p>
      )}
    </section>
  );
}
