"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import type { MembershipRole } from "@/lib/documents";
type Status = { state: string; scan_id: string | null };
const labels: Record<string, string> = {
  UNSCANNED: "Quarantined: not yet scanned",
  CLEAN_AWAITING_RELEASE: "Clean scan: awaiting owner/admin release",
  RELEASED: "Released original: processing and download available",
  INFECTED: "Quarantined: infected",
  SUSPICIOUS: "Quarantined: suspicious",
  UNAVAILABLE: "Quarantined: scanner unavailable",
  TIMEOUT: "Quarantined: scan timed out",
  MISMATCH: "Unavailable: source integrity mismatch",
  ERROR: "Quarantined: scan could not complete",
};
export function SourceAvailability({
  base,
  role,
  onAvailability,
}: {
  base: string;
  role: MembershipRole;
  onAvailability: (value: boolean) => void;
}) {
  const [status, setStatus] = useState<Status | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const keys = useRef<Record<string, { key: string; body: string }>>({});
  const mounted = useRef(true);
  const load = useCallback(
    async (signal?: AbortSignal) => {
      onAvailability(false);
      const response = await fetch(`${base}/source-status`, {
        cache: "no-store",
        signal,
      });
      const result = await response.json();
      if (!response.ok || typeof result.state !== "string")
        throw new Error("Source availability is unavailable.");
      if (!signal?.aborted && mounted.current) {
        setStatus(result);
        onAvailability(result.state === "RELEASED");
      }
    },
    [base, onAvailability],
  );
  useEffect(() => {
    mounted.current = true;
    const controller = new AbortController();
    Promise.resolve()
      .then(() => load(controller.signal))
      .catch(() => {
        if (!controller.signal.aborted) {
          setError(
            "Source availability is unavailable. Processing and download remain blocked.",
          );
          onAvailability(false);
        }
      });
    return () => {
      mounted.current = false;
      controller.abort();
    };
  }, [load, onAvailability]);
  async function act(action: "scan" | "release") {
    if (busy || !reason.trim()) return;
    if (
      action === "release" &&
      !window.confirm(
        "Release this exact clean-scanned original for processing and download? Financial facts still require separate approval.",
      )
    )
      return;
    const body = JSON.stringify({
      reason,
      ...(action === "release" ? { scan_id: status?.scan_id } : {}),
    });
    if (keys.current[action] && keys.current[action].body !== body)
      delete keys.current[action];
    keys.current[action] ??= { key: crypto.randomUUID(), body };
    setBusy(true);
    setError("");
    setNotice("");
    onAvailability(false);
    try {
      const response = await fetch(`${base}/${action}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": keys.current[action].key,
        },
        body,
      });
      const result = await response.json();
      if (!response.ok)
        throw new Error(
          result.error?.message ??
            "Source action failed. Refresh before retrying.",
        );
      delete keys.current[action];
      if (!mounted.current) return;
      setNotice(
        action === "scan"
          ? "Scan recorded. Release and financial approval are separate."
          : "Original released. No processing or financial workflow has run.",
      );
      await load();
    } catch (cause) {
      if (mounted.current) {
        setStatus(null);
        setError(
          cause instanceof Error ? cause.message : "Source action failed.",
        );
      }
    } finally {
      if (mounted.current) setBusy(false);
    }
  }
  return (
    <section className="card settings-card" aria-label="Original availability">
      <h2>Original availability</h2>
      <p>
        Current role: {role}. Scanning and release preserve the original; they
        do not approve facts or create financial results.
      </p>
      <p role="status">
        {busy
          ? "Checking original…"
          : status
            ? (labels[status.state] ?? "Unavailable: unknown scan outcome")
            : "Availability not verified"}
      </p>
      {error && <p role="alert">{error}</p>}
      {notice && <p role="status">{notice}</p>}
      {role !== "viewer" && (
        <>
          <label htmlFor="source-reason">Source action reason</label>
          <textarea
            id="source-reason"
            maxLength={4000}
            value={reason}
            disabled={busy}
            onChange={(e) => setReason(e.target.value)}
          />
          <button disabled={busy || !reason.trim()} onClick={() => act("scan")}>
            Scan exact original
          </button>
          {(role === "owner" || role === "admin") && (
            <button
              disabled={
                busy ||
                !reason.trim() ||
                status?.state !== "CLEAN_AWAITING_RELEASE"
              }
              onClick={() => act("release")}
            >
              Release clean original
            </button>
          )}
        </>
      )}
      <button
        disabled={busy}
        onClick={() => {
          setBusy(true);
          setError("");
          load()
            .catch(() => {
              setStatus(null);
              onAvailability(false);
              setError("Source availability is unavailable.");
            })
            .finally(() => setBusy(false));
        }}
      >
        Refresh availability
      </button>
      <p>
        Unknown, failed, infected or suspicious originals remain unavailable. A
        clean scan does not guarantee absence of threats.
      </p>
    </section>
  );
}
