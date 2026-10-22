"use client";
import { useEffect, useRef, useState } from "react";
import { money } from "@/lib/financial";
import type { Assessment } from "@/lib/financial";
import { proofRequest, proofUrl } from "@/lib/proof";
import type {
  Page,
  ProofArtifact,
  ProofEvent,
  ProofPackage,
} from "@/lib/proof";

function Exact({ value }: { value: unknown }) {
  return (
    <pre style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}
export function ProofWorkspace({
  organizationId,
  assessment,
  role,
  autoOpen = false,
}: {
  organizationId: string;
  assessment: Assessment;
  role: string;
  autoOpen?: boolean;
}) {
  const [opened, setOpened] = useState(autoOpen),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [packages, setPackages] = useState<Page<ProofPackage> | null>(null),
    [selected, setSelected] = useState<ProofPackage | null>(null);
  const [history, setHistory] = useState<Page<ProofEvent> | null>(null),
    [artifacts, setArtifacts] = useState<Page<ProofArtifact> | null>(null);
  const [offset, setOffset] = useState(0),
    [historyOffset, setHistoryOffset] = useState(0),
    [bindingOffset, setBindingOffset] = useState(0);
  const [mode, setMode] = useState(
    assessment.stale || assessment.status === "false_positive"
      ? "HISTORICAL"
      : "CURRENT",
  );
  const controller = useRef<AbortController | null>(null),
    pending = useRef(new Map<string, string>());
  const writable = role !== "viewer",
    finalAuthority = role === "owner" || role === "admin";
  useEffect(() => {
    const current = new AbortController();
    controller.current = current;
    return () => current.abort();
  }, []);
  async function request<T>(path: string, body?: unknown): Promise<T> {
    const identity = path + JSON.stringify(body),
      key =
        body === undefined
          ? undefined
          : (pending.current.get(identity) ?? crypto.randomUUID());
    if (key) pending.current.set(identity, key);
    const signal = controller.current?.signal ?? AbortSignal.timeout(30000);
    try {
      const result = await proofRequest<T>(
        organizationId,
        path,
        signal,
        body,
        key,
      );
      pending.current.delete(identity);
      return result;
    } catch (cause) {
      if (cause instanceof Error && cause.message.includes(": "))
        pending.current.delete(identity);
      throw cause;
    }
  }
  async function action(work: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await work();
    } catch (cause) {
      if (!controller.current?.signal.aborted)
        setError(
          cause instanceof Error ? cause.message : "Proof request failed",
        );
    } finally {
      if (!controller.current?.signal.aborted) setBusy(false);
    }
  }
  async function loadPackage(id: string) {
    const proof = await request<ProofPackage>(`packages/${id}`);
    if (controller.current?.signal.aborted) return;
    setSelected(proof);
    setBindingOffset(0);
    await loadHistory(id, 0);
    if (finalAuthority) {
      const exports = await request<Page<ProofArtifact>>(
        `packages/${id}/artifacts?limit=100&offset=0`,
      );
      if (!controller.current?.signal.aborted) setArtifacts(exports);
    }
  }
  async function loadHistory(id: string, page: number) {
    const data = await request<Page<ProofEvent>>(
      `packages/${id}/history?limit=100&offset=${page}`,
    );
    if (!controller.current?.signal.aborted) {
      setHistory(data);
      setHistoryOffset(page);
    }
  }
  useEffect(() => {
    if (!opened) return;
    let active = true;
    const signal = controller.current?.signal ?? AbortSignal.timeout(30000);
    void Promise.resolve()
      .then(() =>
        active
          ? proofRequest<Page<ProofPackage>>(
              organizationId,
              `evaluations/${assessment.id}/packages?limit=100&offset=${offset}`,
              signal,
            )
          : undefined,
      )
      .then((data) => {
        if (active && data) {
          setPackages(data);
          setError("");
        }
      })
      .catch((cause) => {
        if (active)
          setError(
            cause instanceof Error
              ? cause.message
              : "Unable to read proof history",
          );
      });
    return () => {
      active = false;
    };
  }, [opened, organizationId, assessment.id, offset]);
  async function refresh() {
    const data = await request<Page<ProofPackage>>(
      `evaluations/${assessment.id}/packages?limit=100&offset=${offset}`,
    );
    if (!controller.current?.signal.aborted) setPackages(data);
    if (selected) await loadPackage(selected.id);
  }
  async function mutate(kind: string, data: unknown) {
    if (!selected) return;
    await request(`packages/${selected.id}/${kind}`, data);
    await refresh();
  }
  const core = selected?.core,
    bindings = core?.calculation.bindings ?? [],
    blocked = selected?.identity.kind === "BLOCKED_ASSESSMENT_EVIDENCE";
  const proposalEvents =
      history?.items.filter((e) => e.kind === "disclosure.proposed") ?? [],
    approvedViews =
      history?.items.filter((e) => e.kind === "disclosure.approved") ?? [];
  return (
    <section aria-label="Leakage proof engine">
      <h3>Leakage proof</h3>
      {!opened ? (
        <button className="button" onClick={() => setOpened(true)}>
          View proof
        </button>
      ) : (
        <>
          <p>
            Proof explains the immutable assessment. Technical evidence
            completeness, financial decision and human proof review are
            separate.
          </p>
          {error && <p role="alert">{error}</p>}
          {busy && <p role="status">Working on proof…</p>}
          {packages && packages.items.length === 0 && (
            <p>No proof has been issued for this assessment.</p>
          )}
          {writable && (
            <div>
              <label>
                Generation context{" "}
                <select
                  value={mode}
                  disabled={busy}
                  onChange={(e) => setMode(e.target.value)}
                >
                  <option value="CURRENT">Current assessment</option>
                  <option value="HISTORICAL">
                    Explicit historical evidence
                  </option>
                </select>
              </label>{" "}
              <button
                disabled={busy || !packages || !assessment.fingerprint}
                onClick={() =>
                  void action(async () => {
                    const result = await request<{ package_id: string }>(
                      `evaluations/${assessment.id}/generate`,
                      { mode, expected_fingerprint: assessment.fingerprint },
                    );
                    await refresh();
                    await loadPackage(result.package_id);
                  })
                }
              >
                Generate proof
              </button>
            </div>
          )}
          {packages && (
            <>
              <label>
                Immutable content revision{" "}
                <select
                  value={selected?.id ?? ""}
                  disabled={busy}
                  onChange={(e) =>
                    void action(() => loadPackage(e.target.value))
                  }
                >
                  <option value="" disabled>
                    Select issued proof
                  </option>
                  {packages.items.map((p) => (
                    <option value={p.id} key={p.id}>
                      Revision {p.number} · {p.issued_completeness} at issue
                    </option>
                  ))}
                </select>
              </label>
              <div>
                <button
                  disabled={busy || offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - 100))}
                >
                  Newer content history
                </button>{" "}
                <button
                  disabled={busy || !packages.has_more}
                  onClick={() => setOffset(offset + 100)}
                >
                  Older content history
                </button>
              </div>
            </>
          )}
          {selected && core && (
            <>
              <h4>
                {blocked
                  ? "Assessment blocked"
                  : selected.financial.outcome === "UNDERCHARGE"
                    ? "Undercharge assessment evidence"
                    : selected.financial.potential === null
                      ? "Assessed comparison evidence"
                      : "Potential Leakage"}
              </h4>
              <p>
                {blocked
                  ? "Unknown monetary amount"
                  : money(
                      selected.financial.potential,
                      selected.financial.currency,
                    )}
              </p>
              <p>{selected.financial.explanation}</p>
              <dl>
                <div>
                  <dt>Evidence at issuance</dt>
                  <dd>
                    {selected.issued_completeness === "COMPLETE"
                      ? blocked
                        ? "Complete assessment explanation"
                        : "Evidence Complete"
                      : "Evidence Incomplete"}
                  </dd>
                </div>
                <div>
                  <dt>Financial currentness</dt>
                  <dd>{selected.overlays.financial_currentness}</dd>
                </div>
                <div>
                  <dt>Finding decision</dt>
                  <dd>
                    {selected.overlays.finding_decision ??
                      "No monetary finding"}
                  </dd>
                </div>
                <div>
                  <dt>Human proof review</dt>
                  <dd>{selected.overlays.human_review}</dd>
                </div>
                <div>
                  <dt>Explicit successor</dt>
                  <dd>{selected.overlays.successor_id ?? "None"}</dd>
                </div>
              </dl>
              {selected.overlays.as_of && (
                <p className="muted">
                  Current state observed at {selected.overlays.as_of}
                </p>
              )}
              {selected.overlays.financial_currentness !== "CURRENT" && (
                <p>
                  Historical evidence: the original amounts remain unchanged.
                </p>
              )}
              {selected.overlays.finding_decision === "false_positive" && (
                <p>
                  Evidence complete at issue can remain visible after a finding
                  is dismissed.
                </p>
              )}
              <p>
                Expected Financial Reality:{" "}
                {money(
                  selected.financial.expected,
                  selected.financial.currency,
                )}{" "}
                · Actual Financial Reality:{" "}
                {money(selected.financial.actual, selected.financial.currency)}{" "}
                · Discrepancy:{" "}
                {money(
                  selected.financial.discrepancy,
                  selected.financial.currency,
                )}
              </p>
              <div className="grid">
                <details>
                  <summary>Contractual basis and amendments</summary>
                  <Exact value={core.governing} />
                </details>
                <details>
                  <summary>Actual billing, tax and allocated credits</summary>
                  <Exact value={core.billing} />
                </details>
              </div>
              <details>
                <summary>Match and applicability</summary>
                <Exact value={core.matching} />
              </details>
              <details open>
                <summary>
                  Recorded calculation trace and rounding alternatives
                </summary>
                <Exact value={core.calculation.recorded_trace} />
                <p>
                  Unrecorded intermediates are not invented. Independent
                  arithmetic reconstruction verifies this historical result.
                </p>
              </details>
              <details>
                <summary>
                  Source evidence and approved meanings ({bindings.length}{" "}
                  bindings)
                </summary>
                <p>
                  Showing {bindings.length ? bindingOffset + 1 : 0}–
                  {Math.min(bindingOffset + 50, bindings.length)} of{" "}
                  {bindings.length}. The complete manifest preserves every
                  binding.
                </p>
                {bindings.slice(bindingOffset, bindingOffset + 50).map((b) => (
                  <article key={b.revision_id + b.input_pointer + b.binding_id}>
                    <p>
                      <strong>{b.input_pointer}</strong> · {b.role}
                    </p>
                    <p>
                      Reviewed meaning:{" "}
                      {b.typed_input.value === null
                        ? "Unknown / explicitly not applicable"
                        : String(b.typed_input.value)}{" "}
                      · {b.typed_input.type} · {b.typed_input.currency ?? ""}{" "}
                      {b.typed_input.denominator ?? b.typed_input.unit ?? ""}
                    </p>
                    <p>Raw source: {b.source.raw_value}</p>
                    <p>
                      Normalized candidate:{" "}
                      {b.source.normalized_candidate ?? "Not recorded"}
                    </p>
                    <p>
                      Reviewer citation: {b.source.location} — {b.source.quote}
                    </p>
                    {b.source.manual && (
                      <p>
                        Reviewer-supplied citation; exact page/coordinates
                        unavailable unless explicitly recorded. Quotation is not
                        machine-verified.
                      </p>
                    )}
                    <details>
                      <summary>Pinned lineage and locator</summary>
                      <Exact value={b.source} />
                    </details>
                    <a
                      href={proofUrl(
                        organizationId,
                        `packages/${selected.id}/sources/${b.source.document_id}/download`,
                      )}
                    >
                      Inspect verified original source
                    </a>
                  </article>
                ))}
                <button
                  disabled={bindingOffset === 0}
                  onClick={() =>
                    setBindingOffset(Math.max(0, bindingOffset - 50))
                  }
                >
                  Previous bindings
                </button>{" "}
                <button
                  disabled={bindingOffset + 50 >= bindings.length}
                  onClick={() => setBindingOffset(bindingOffset + 50)}
                >
                  Next bindings
                </button>
              </details>
              <details>
                <summary>Approval history and behavior versions</summary>
                <Exact value={core.authority} />
                <Exact value={core.behavior} />
              </details>
              <details open>
                <summary>Source integrity now</summary>
                {selected.overlays.evidence_availability.map((s) => (
                  <p key={s.document_id}>
                    {s.document_id}: {s.status}
                    {s.status === "MISMATCH"
                      ? " — quarantined; original download blocked"
                      : ""}
                  </p>
                ))}
              </details>
              <details>
                <summary>
                  Deterministic completeness requirements and gaps
                </summary>
                <Exact value={core.completeness} />
              </details>
              <details open>
                <summary>Limitations</summary>
                {core.limitations.map((text) => (
                  <p key={text}>{text}</p>
                ))}
              </details>
              {writable && selected.issued_completeness === "INCOMPLETE" && (
                <button
                  disabled={busy || !assessment.fingerprint}
                  onClick={() =>
                    void action(async () => {
                      const result = await request<{ package_id: string }>(
                        `evaluations/${assessment.id}/generate`,
                        {
                          mode,
                          expected_fingerprint: assessment.fingerprint,
                          previous_package_id: selected.id,
                          revision_reason: "REPAIRED_EVIDENCE",
                        },
                      );
                      await refresh();
                      await loadPackage(result.package_id);
                    })
                  }
                >
                  Request explicit evidence availability repair
                </button>
              )}
              {writable && (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const data = new FormData(e.currentTarget);
                    void action(() =>
                      mutate("events", {
                        kind: "annotation.appended",
                        text: String(data.get("text")),
                        previous_id: data.get("previous") || null,
                      }),
                    );
                  }}
                >
                  <h4>Nonfinancial annotations</h4>
                  <label>
                    Annotation text{" "}
                    <textarea name="text" maxLength={4000} required />
                  </label>
                  <label>
                    Prior annotation ID (optional revision){" "}
                    <input name="previous" />
                  </label>
                  <button disabled={busy}>Append annotation</button>
                  <p>
                    Annotations cannot change financial facts, amounts,
                    decisions or evidence.
                  </p>
                </form>
              )}
              {writable && (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const data = new FormData(e.currentTarget);
                    void action(() =>
                      mutate("events", {
                        kind: finalAuthority
                          ? "review.finalized"
                          : "review.proposed",
                        text: String(data.get("reason")),
                        status: String(data.get("status")),
                        previous_id: finalAuthority
                          ? selected.overlays.review_id
                          : null,
                      }),
                    );
                  }}
                >
                  <h4>
                    {finalAuthority
                      ? "Human proof review"
                      : "Proof review proposal"}
                  </h4>
                  <label>
                    Review state{" "}
                    <select name="status">
                      <option value="REVIEWED">Reviewed</option>
                      <option value="NEEDS_REVIEW">Needs Review</option>
                    </select>
                  </label>
                  <label>
                    Attributed reason{" "}
                    <textarea name="reason" maxLength={4000} required />
                  </label>
                  <button disabled={busy}>
                    {finalAuthority
                      ? "Save proof review"
                      : "Propose proof review"}
                  </button>
                </form>
              )}
              {writable && (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const data = new FormData(e.currentTarget);
                    void action(() =>
                      mutate("events", {
                        kind: "disclosure.proposed",
                        text: String(data.get("reason")),
                        paths: String(data.get("paths"))
                          .split(/\r?\n/)
                          .filter(Boolean),
                        previous_id: data.get("previous") || null,
                      }),
                    );
                  }}
                >
                  <h4>Disclosure proposal</h4>
                  <p>
                    Use exact scalar field paths in the canonical core, one per
                    line. The separate view masks duplicated sensitive content
                    and labels independent verification as limited.
                  </p>
                  <label>
                    Paths to hide <textarea name="paths" required />
                  </label>
                  <label>
                    Disclosure reason{" "}
                    <textarea name="reason" maxLength={4000} required />
                  </label>
                  <label>
                    Prior proposal ID (optional revision){" "}
                    <input name="previous" />
                  </label>
                  <button disabled={busy}>Propose disclosure</button>
                </form>
              )}
              {finalAuthority && proposalEvents.length > 0 && (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const data = new FormData(e.currentTarget);
                    void action(() =>
                      mutate("events", {
                        kind: "disclosure.approved",
                        text: String(data.get("reason")),
                        previous_id: String(data.get("proposal")),
                      }),
                    );
                  }}
                >
                  <label>
                    Disclosure proposal{" "}
                    <select name="proposal">
                      {proposalEvents.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.id} · {p.detail.text}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Approval reason{" "}
                    <textarea name="reason" maxLength={4000} required />
                  </label>
                  <button disabled={busy}>Approve disclosure</button>
                </form>
              )}
              {finalAuthority && (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const data = new FormData(e.currentTarget);
                    void action(() =>
                      mutate("export", {
                        disclosure_id: data.get("view") || null,
                      }),
                    );
                  }}
                >
                  <h4>Private JSON export</h4>
                  <label>
                    Disclosure view{" "}
                    <select name="view">
                      <option value="">Canonical internal manifest</option>
                      {approvedViews.map((p) => (
                        <option value={p.id} key={p.id}>
                          Approved disclosure {p.id}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button disabled={busy}>Prepare JSON export</button>
                  <p>
                    Downloaded files leave application access controls. PDF and
                    external delivery are deferred.
                  </p>
                </form>
              )}
              {artifacts && (
                <details>
                  <summary>Private export artifacts</summary>
                  {artifacts.items.map((a) => (
                    <p key={a.id}>
                      <a
                        href={proofUrl(
                          organizationId,
                          `artifacts/${a.id}/download`,
                        )}
                      >
                        Download JSON {a.id}
                      </a>{" "}
                      · {a.size_bytes} bytes · SHA-256 {a.content_hash} ·{" "}
                      {a.actor_id} at {a.created_at}
                    </p>
                  ))}
                  {artifacts.has_more && (
                    <button
                      disabled={busy}
                      onClick={() =>
                        void action(async () => {
                          const data = await request<Page<ProofArtifact>>(
                            `packages/${selected.id}/artifacts?limit=100&offset=${artifacts.offset + 100}`,
                          );
                          setArtifacts(data);
                        })
                      }
                    >
                      Older export artifacts
                    </button>
                  )}
                </details>
              )}
              {finalAuthority && (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const data = new FormData(e.currentTarget);
                    void action(() =>
                      mutate("successor", {
                        successor_id: String(data.get("id")),
                        reason: String(data.get("reason")),
                      }),
                    );
                  }}
                >
                  <h4>Explicit same-scope successor</h4>
                  <label>
                    Successor proof ID <input name="id" required />
                  </label>
                  <label>
                    Relationship reason{" "}
                    <textarea name="reason" maxLength={2000} required />
                  </label>
                  <button disabled={busy}>Record explicit successor</button>
                  <p>
                    This relationship changes neither evaluation amount nor
                    financial decision.
                  </p>
                </form>
              )}
              <details>
                <summary>
                  Attributed annotation, disclosure, integrity and review
                  history
                </summary>
                {history?.items.map((e) => (
                  <article key={e.id}>
                    <p>
                      {e.kind} · {e.actor_id} at {e.created_at} · Event {e.id} ·
                      Audit {e.audit_id}
                    </p>
                    <Exact value={e.detail} />
                    {writable && e.kind === "annotation.appended" && (
                      <button
                        disabled={busy}
                        onClick={() =>
                          void action(() =>
                            mutate("events", {
                              kind: "annotation.retracted",
                              text: "Attributed annotation retraction",
                              previous_id: e.id,
                            }),
                          )
                        }
                      >
                        Retract annotation {e.id}
                      </button>
                    )}
                  </article>
                ))}
                <button
                  disabled={busy || historyOffset === 0}
                  onClick={() =>
                    void action(() =>
                      loadHistory(
                        selected.id,
                        Math.max(0, historyOffset - 100),
                      ),
                    )
                  }
                >
                  Newer action history
                </button>{" "}
                <button
                  disabled={busy || !history?.has_more}
                  onClick={() =>
                    void action(() =>
                      loadHistory(selected.id, historyOffset + 100),
                    )
                  }
                >
                  Older action history
                </button>
              </details>
              <details>
                <summary>
                  Canonical manifest, issuance envelope and audit identifiers
                </summary>
                <p>Manifest SHA-256 {selected.fingerprint}</p>
                <p>
                  Evaluation snapshot SHA-256 {core.evaluation_snapshot_digest}
                </p>
                <p>
                  Content predecessor {selected.previous_id ?? "None"} ·{" "}
                  {selected.revision_reason ?? "Initial issuance"}
                </p>
                <Exact value={core} />
                <Exact value={selected.envelope} />
              </details>
            </>
          )}
        </>
      )}
    </section>
  );
}
