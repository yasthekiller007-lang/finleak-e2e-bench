"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import type { CurrentUser, FinancialDocument } from "@/lib/documents";
import type { Assessment } from "@/lib/financial";
import { financialRequest } from "@/lib/financial";
import { RecoveryProposalForm } from "@/components/recovery-proposal-form";
import { recoveryRequest } from "@/lib/recovery";
import type {
  Instrument,
  LedgerRecord,
  Page,
  RecoveryCase,
} from "@/lib/recovery";
const show = (value: string | null, currency: string) =>
  value === null ? "Unknown / not recorded" : `${currency} ${value}`;
export function RecoveryWorkspace({ user }: { user: CurrentUser }) {
  const [org, setOrg] = useState(user.organizations[0]?.id ?? "");
  const [cases, setCases] = useState<Page<RecoveryCase>>({
    items: [],
    has_more: false,
    offset: 0,
    limit: 20,
  });
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState("");
  const [detail, setDetail] = useState<RecoveryCase | null>(null);
  const [historyOffset, setHistoryOffset] = useState(0);
  const [proposalOffset, setProposalOffset] = useState(0);
  const [historyMore, setHistoryMore] = useState(false);
  const [proposalsMore, setProposalsMore] = useState(false);
  const [history, setHistory] = useState<LedgerRecord[]>([]);
  const [proposals, setProposals] = useState<LedgerRecord[]>([]);
  const [documents, setDocuments] = useState<FinancialDocument[]>([]);
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [evaluation, setEvaluation] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [listError, setListError] = useState("");
  const [detailError, setDetailError] = useState("");
  const [notice, setNotice] = useState("");
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [priority, setPriority] = useState("NORMAL");
  const [assignee, setAssignee] = useState("");
  const [nextAction, setNextAction] = useState("");
  const [followUp, setFollowUp] = useState("");
  const [targetDate, setTargetDate] = useState("");
  const [escalation, setEscalation] = useState("NONE");
  const [closureReason, setClosureReason] = useState("MANAGEMENT");
  const [instrumentKind, setInstrumentKind] = useState("CASH");
  const [namespace, setNamespace] = useState("");
  const [issuer, setIssuer] = useState("");
  const [reference, setReference] = useState("");
  const [currency, setCurrency] = useState("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [knownAt, setKnownAt] = useState("");
  const [customer, setCustomer] = useState("");
  const [report, setReport] = useState<{
    realized_flow: string;
    active_eligible_realized: string;
    matching_validated: string;
    historical_exception_realized: string;
    ratio: string | null;
    context: { coverage: string; known_at: string };
    digest: string;
  } | null>(null);
  const role = user.organizations.find((o) => o.id === org)?.role;
  const writable = role !== undefined && role !== "viewer";
  const final = role === "owner" || role === "admin";
  useEffect(() => {
    if (!org) return;
    let active = true;
    Promise.resolve()
      .then(async () => {
        if (!active) return null;
        // Keep budgeted reads sequential; the tenant's two slots also serve
        // current-case detail and other reviewers. Discard cleaned-up effects.
        const c = await recoveryRequest<Page<RecoveryCase>>(
          org,
          `cases?limit=20&offset=${offset}`,
        );
        if (!active) return null;
        const i = await recoveryRequest<Page<Instrument>>(
          org,
          "instruments?limit=100",
        );
        if (!active) return null;
        const [a, d] = await Promise.all([
          financialRequest<{ items: Assessment[] }>(
            org,
            "evaluations?limit=100",
          ),
          fetch(`/api/organizations/${org}/documents?limit=100`, {
            cache: "no-store",
          }).then(async (r) => {
            if (!r.ok)
              throw new Error("Protected documents could not be loaded.");
            return r.json() as Promise<{ items: FinancialDocument[] }>;
          }),
        ]);
        return [c, i, a, d] as const;
      })
      .then((result) => {
        if (active && result) {
          const [c, i, a, d] = result;
          setCases(c);
          setInstruments(i.items);
          setAssessments(
            a.items.filter(
              (v) =>
                v.outcome === "POTENTIAL_LEAKAGE" &&
                v.status !== "false_positive",
            ),
          );
          setDocuments(d.items);
          setListError("");
        }
      })
      .catch((e) => {
        if (active) {
          setCases({ items: [], has_more: false, offset: 0, limit: 20 });
          setInstruments([]);
          setAssessments([]);
          setDocuments([]);
          setDetail(null);
          setHistory([]);
          setProposals([]);
          setReport(null);
          setNotice("");
          setListError(e.message);
        }
      });
    return () => {
      active = false;
    };
  }, [org, refresh, offset]);
  useEffect(() => {
    if (!org || !selected) return;
    let active = true;
    Promise.resolve()
      .then(async () => {
        if (!active) return null;
        const d = await recoveryRequest<RecoveryCase>(org, `cases/${selected}`);
        if (!active) return null;
        const h = await recoveryRequest<Page<LedgerRecord>>(
          org,
          `cases/${selected}/history?limit=100&offset=${historyOffset}`,
        );
        if (!active) return null;
        const p = await recoveryRequest<Page<LedgerRecord>>(
          org,
          `cases/${selected}/history?limit=100&offset=${proposalOffset}&proposals=true`,
        );
        return [d, h, p] as const;
      })
      .then((result) => {
        if (active && result) {
          const [d, h, p] = result;
          setDetail(d);
          setHistory(h.items);
          setHistoryMore(h.has_more);
          setProposals(p.items);
          setProposalsMore(p.has_more);
          setDetailError("");
        }
      })
      .catch((e) => {
        if (active) {
          setDetail(null);
          setHistory([]);
          setProposals([]);
          setHistoryMore(false);
          setProposalsMore(false);
          setNotice("");
          setDetailError(e.message);
        }
      });
    return () => {
      active = false;
    };
  }, [org, selected, refresh, historyOffset, proposalOffset]);
  async function command(path: string, body: unknown, message: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await recoveryRequest<{ id: string }>(org, path, body);
      if (path === "cases") setSelected(result.id);
      setNotice(message);
      setRefresh((r) => r + 1);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Recovery action failed safely.",
      );
    } finally {
      setBusy(false);
    }
  }
  if (!org) return <p>No authorized organization is available.</p>;
  return (
    <div className="stack">
      <label>
        Organization
        <select
          value={org}
          onChange={(e) => {
            setDetail(null);
            setCases({ items: [], has_more: false, offset: 0, limit: 20 });
            setDocuments([]);
            setInstruments([]);
            setAssessments([]);
            setHistory([]);
            setProposals([]);
            setReport(null);
            setNotice("");
            setError("");
            setListError("");
            setDetailError("");
            setOrg(e.target.value);
            setSelected("");
            setHistoryOffset(0);
            setProposalOffset(0);
            setOffset(0);
          }}
        >
          {user.organizations.map((o) => (
            <option value={o.id} key={o.id}>
              {o.name} · {o.role}
            </option>
          ))}
        </select>
      </label>
      <p>
        Internal evidence and pursuit record. Claims, vendor positions and
        issued credits are separate from realized recovery. No accounting
        posting or vendor delivery occurs here.
      </p>
      {error && <p role="alert">{error}</p>}
      {listError && <p role="alert">{listError}</p>}
      {detailError && <p role="alert">{detailError}</p>}
      {notice && <p role="status">{notice}</p>}
      {writable && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void command(
              "cases",
              { evaluation_id: evaluation },
              "Investigation case opened; no financial approval was granted.",
            );
          }}
        >
          <label>
            Positive financial finding
            <select
              required
              value={evaluation}
              onChange={(e) => setEvaluation(e.target.value)}
            >
              <option value="">Choose a finding</option>
              {assessments.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.scope_summary?.label ?? a.scope_key} ·{" "}
                  {show(a.potential, a.currency ?? "")} ·{" "}
                  {a.stale ? "stale investigation" : a.status}
                </option>
              ))}
            </select>
          </label>
          <button disabled={busy}>Open investigation</button>
        </form>
      )}
      <h2>Recovery cases</h2>
      <p>This is a case page. It is not an authoritative portfolio total.</p>
      <table>
        <thead>
          <tr>
            <th>Case / finding</th>
            <th>Lifecycle / readiness</th>
            <th>Recorded realization</th>
            <th>Coverage</th>
          </tr>
        </thead>
        <tbody>
          {cases.items.map((c) => (
            <tr key={c.id}>
              <td>
                <button
                  onClick={() => {
                    setDetail(null);
                    setHistory([]);
                    setProposals([]);
                    setSelected(c.id);
                    setHistoryOffset(0);
                    setProposalOffset(0);
                  }}
                >
                  {c.supplier} · {c.id.slice(0, 8)}
                </button>
              </td>
              <td>
                {c.lifecycle} / {c.readiness}
              </td>
              <td>{show(c.realized, c.currency)}</td>
              <td>
                {c.category} · {c.coverage}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div>
        <button
          disabled={offset === 0 || busy}
          onClick={() => setOffset((v) => Math.max(0, v - 20))}
        >
          Previous cases
        </button>
        <button
          disabled={!cases.has_more || busy}
          onClick={() => setOffset((v) => v + 20)}
        >
          Next cases
        </button>
      </div>
      {detail && !listError && !detailError && (
        <section className="stack">
          <h2>Case evidence and authority</h2>
          <p>
            {detail.lifecycle} · {detail.readiness} · finding{" "}
            {detail.finding_decision} · {detail.currentness} · evidence{" "}
            {detail.evidence} · realization {detail.realization_state}
          </p>
          {detail.readiness !== "READY" && (
            <p role="status">
              Positive authority is blocked until the approved readiness
              conditions are met.{" "}
              <Link href="/leakage-cases">
                Use the existing finding and proof review workflows separately.
              </Link>
            </p>
          )}
          <dl>
            {[
              ["Potential leakage P", detail.potential],
              ["Internally confirmed V", detail.validated],
              ["Commercial pursuit B", detail.pursuit],
              ["Actioned claim C", detail.claimed],
              ["Acknowledged principal S", detail.acknowledged],
              ["Explicit disputed principal D", detail.disputed],
              [
                "Gross verified realized recovery R — before separately evidenced costs",
                detail.realized,
              ],
              ["Actual net bank cash N", detail.net_cash],
              ["Pending credit stock", detail.pending_credit],
              ["Unrealized pursuit balance", detail.unrealized],
            ].map(([label, value]) => (
              <div key={label ?? ""}>
                <dt>{label}</dt>
                <dd>{show(value ?? null, detail.currency)}</dd>
              </div>
            ))}
          </dl>
          <p>
            Compatible gross recovery ratio:{" "}
            {detail.ratio === null
              ? "Unknown / ineligible"
              : `${detail.ratio}%`}
            . {detail.category} · {detail.coverage}
          </p>
          <p>
            Methods:{" "}
            {Object.entries(detail.methods)
              .map(([m, a]) => `${m}: ${show(a, detail.currency)}`)
              .join("; ") || "No approved realization"}
          </p>
          <p>
            Direct costs:{" "}
            {Object.entries(detail.costs)
              .map(([c, v]) => `${c} incurred ${v.incurred}; paid ${v.paid}`)
              .join("; ") || "Not recorded"}
            . Costs are not subtracted from R.
          </p>
          {writable && (
            <>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void command(
                    "instruments",
                    {
                      kind: instrumentKind,
                      namespace,
                      issuer,
                      reference,
                      currency,
                    },
                    "Economic identity recorded; no performance or recovery approved.",
                  );
                }}
                className="stack"
              >
                <h3>Record stable economic instrument</h3>
                <label>
                  Instrument type
                  <select
                    value={instrumentKind}
                    onChange={(e) => setInstrumentKind(e.target.value)}
                  >
                    {["CASH", "CREDIT", "LIABILITY", "COST", "SETTLEMENT"].map(
                      (k) => (
                        <option key={k}>{k}</option>
                      ),
                    )}
                  </select>
                </label>
                {[
                  ["Source reference namespace", namespace, setNamespace],
                  ["Issuer legal identity", issuer, setIssuer],
                  ["Economic reference", reference, setReference],
                  ["Original currency", currency, setCurrency],
                ].map(([label, value, setter]) => (
                  <label key={String(label)}>
                    {String(label)}
                    <input
                      required
                      maxLength={120}
                      value={String(value)}
                      onChange={(e) =>
                        (setter as (s: string) => void)(e.target.value)
                      }
                    />
                  </label>
                ))}
                <button disabled={busy}>Record instrument identity</button>
              </form>
              <RecoveryProposalForm
                key={`${org}:${detail.id}`}
                detail={detail}
                documents={documents}
                instruments={instruments}
                history={history}
                busy={busy}
                submit={(body) =>
                  command(
                    `cases/${detail.id}/proposals`,
                    body,
                    "Proposal saved; approved money is unchanged.",
                  )
                }
              />
              <label>
                Action / approval reason
                <textarea
                  maxLength={4000}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
              </label>
              <button
                disabled={busy || !reason}
                onClick={() =>
                  void command(
                    `cases/${detail.id}/inspect`,
                    { expected_head: detail.head_id, reason },
                    "Current authority observation preserved for as-known reporting.",
                  )
                }
              >
                Record current readiness inspection
              </button>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void command(
                    `cases/${detail.id}/notes`,
                    {
                      text: note,
                      expected_head: detail.head_id,
                      reason,
                      replaces_id: null,
                      retracted: false,
                    },
                    "Nonfinancial annotation recorded.",
                  );
                }}
              >
                <label>
                  Attributed internal note
                  <textarea
                    required
                    maxLength={4000}
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                  />
                </label>
                <button disabled={busy || !reason}>Append note</button>
              </form>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void command(
                    `cases/${detail.id}/workflow`,
                    {
                      assignee_id: assignee || null,
                      priority,
                      target_date: targetDate || null,
                      follow_up_date: followUp || null,
                      next_action: nextAction || null,
                      escalation,
                      expected_head: detail.head_id,
                      reason,
                    },
                    "Operational assignment updated; financial truth is unchanged.",
                  );
                }}
                className="stack"
              >
                <h3>Operational workflow</h3>
                <label>
                  Active tenant member assignment
                  <input
                    value={assignee}
                    onChange={(e) => setAssignee(e.target.value)}
                  />
                </label>
                <label>
                  Priority
                  <select
                    value={priority}
                    onChange={(e) => setPriority(e.target.value)}
                  >
                    {["LOW", "NORMAL", "HIGH", "URGENT"].map((v) => (
                      <option key={v}>{v}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Target date
                  <input
                    type="date"
                    value={targetDate}
                    onChange={(e) => setTargetDate(e.target.value)}
                  />
                </label>
                <label>
                  Follow-up date
                  <input
                    type="date"
                    value={followUp}
                    onChange={(e) => setFollowUp(e.target.value)}
                  />
                </label>
                <label>
                  Next internal action
                  <textarea
                    maxLength={4000}
                    value={nextAction}
                    onChange={(e) => setNextAction(e.target.value)}
                  />
                </label>
                <label>
                  Internal escalation
                  <select
                    value={escalation}
                    onChange={(e) => setEscalation(e.target.value)}
                  >
                    {["NONE", "REQUESTED", "REVIEWING"].map((v) => (
                      <option key={v}>{v}</option>
                    ))}
                  </select>
                </label>
                <button disabled={busy || !reason}>Update workflow</button>
              </form>
            </>
          )}
          {final && (
            <>
              <h3>Explicit lifecycle</h3>
              <label>
                Commercial closure reason
                <select
                  value={closureReason}
                  onChange={(e) => setClosureReason(e.target.value)}
                >
                  {[
                    "PARTIAL_SETTLEMENT",
                    "FULL_SETTLEMENT",
                    "ECONOMICS",
                    "RELATIONSHIP",
                    "IMMATERIALITY",
                    "INSUFFICIENT_EVIDENCE",
                    "LIMITATION_CONCERN",
                    "MANAGEMENT",
                    "OPERATIONAL",
                    "INVALID_BASIS",
                  ].map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              </label>
              {["OPEN", "SUSPENDED", "CLOSED"].map((state) => (
                <button
                  key={state}
                  disabled={busy || !reason || state === detail.lifecycle}
                  onClick={() =>
                    void command(
                      `cases/${detail.id}/lifecycle`,
                      {
                        state,
                        closure_reason:
                          state === "CLOSED" ? closureReason : null,
                        expected_head: detail.head_id,
                        reason,
                      },
                      "Explicit lifecycle action recorded; money and finding decision are unchanged.",
                    )
                  }
                >
                  {state === "OPEN"
                    ? "Reopen"
                    : state === "CLOSED"
                      ? "Close commercial pursuit"
                      : "Suspend"}
                </button>
              ))}
            </>
          )}
          <h3>Prepared proposals</h3>
          <p>
            Only the exact current proposal context can be approved. History
            pages never substitute for full monetary totals.
          </p>
          {proposals.map((p) => (
            <article key={p.id}>
              <h4>
                {p.kind} · {p.reason}
              </h4>
              <dl>
                {Object.entries(p.value)
                  .filter(([, v]) => typeof v === "string" || v === null)
                  .map(([k, v]) => (
                    <div key={k}>
                      <dt>{k.replaceAll("_", " ")}</dt>
                      <dd>
                        {v === null ? "Unknown / not applicable" : String(v)}
                      </dd>
                    </div>
                  ))}
              </dl>
              {(final || (writable && p.actor_id === user.id)) &&
                [
                  ...(final ? ["APPROVE", "REJECT"] : []),
                  ...(writable && p.actor_id === user.id ? ["WITHDRAW"] : []),
                ].map((decision) => (
                  <button
                    key={decision}
                    disabled={
                      busy ||
                      !reason ||
                      (decision === "APPROVE" &&
                        p.authority?.head !== detail.head_id)
                    }
                    onClick={() =>
                      void command(
                        `proposals/${p.id}/decision`,
                        { decision, reason, expected_head: detail.head_id },
                        decision === "APPROVE"
                          ? "Reviewed authority recorded; inspect current measures."
                          : decision === "WITHDRAW"
                            ? "Own proposal withdrawn; money unchanged."
                            : "Proposal rejected; money unchanged.",
                      )
                    }
                  >
                    {decision === "APPROVE"
                      ? "Approve exact proposal"
                      : decision === "WITHDRAW"
                        ? "Withdraw own proposal"
                        : "Reject proposal"}
                  </button>
                ))}
            </article>
          ))}
          <nav aria-label="Proposal history pages">
            <button
              disabled={proposalOffset === 0 || busy}
              onClick={() => setProposalOffset((v) => Math.max(0, v - 100))}
            >
              Previous proposals
            </button>
            <button
              disabled={!proposalsMore || busy}
              onClick={() => setProposalOffset((v) => v + 100)}
            >
              Next proposals
            </button>
          </nav>
          <h3>Immutable case history</h3>
          <p>
            History page starting at {historyOffset + 1}; complete monetary
            projections are shown separately.
          </p>
          {history.map((r) => (
            <article key={r.id}>
              <strong>
                {r.kind} #{r.number}
              </strong>
              <p>
                {r.reason} · actor {r.actor_id} · known{" "}
                {r.known_at ?? "unresolved commit provenance"} ·{" "}
                {r.amount === null || r.amount === undefined
                  ? "No realization allocation"
                  : show(r.amount, detail.currency)}
              </p>
              {r.kind === "note" &&
                (final || (writable && r.actor_id === user.id)) &&
                !r.value.retracted && (
                  <button
                    disabled={busy || !reason}
                    onClick={() =>
                      void command(
                        `cases/${selected}/notes`,
                        {
                          text: "Annotation retracted",
                          retracted: true,
                          replaces_id: r.id,
                          expected_head: detail.head_id,
                          reason,
                        },
                        "Attributed annotation retraction recorded; money unchanged.",
                      )
                    }
                  >
                    Retract annotation
                  </button>
                )}
            </article>
          ))}
          <nav aria-label="Case history pages">
            <button
              disabled={historyOffset === 0 || busy}
              onClick={() => setHistoryOffset((v) => Math.max(0, v - 100))}
            >
              Previous history
            </button>
            <button
              disabled={!historyMore || busy}
              onClick={() => setHistoryOffset((v) => v + 100)}
            >
              Next history
            </button>
          </nav>
        </section>
      )}
      <section className="stack">
        <h2>Compatible as-known report</h2>
        <p>
          Complete bounded population for one currency, customer and
          tax-exclusive basis. Economic periods use [start, end). No
          mixed-currency total or recovery export.
        </p>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              const result = await recoveryRequest<NonNullable<typeof report>>(
                org,
                "report",
                {
                  known_at: knownAt,
                  start: { precision: "DATE", day: periodStart },
                  end: { precision: "DATE", day: periodEnd },
                  currency,
                  customer,
                  tax_basis: "EXCLUSIVE",
                },
              );
              setReport(result);
            } catch (e) {
              setError(e instanceof Error ? e.message : "Report unavailable.");
            } finally {
              setBusy(false);
            }
          }}
          className="stack"
        >
          <label>
            Period start
            <input
              type="date"
              required
              value={periodStart}
              onChange={(e) => setPeriodStart(e.target.value)}
            />
          </label>
          <label>
            Period end (exclusive)
            <input
              type="date"
              required
              value={periodEnd}
              onChange={(e) => setPeriodEnd(e.target.value)}
            />
          </label>
          <label>
            Known-at cutoff with explicit timezone offset
            <input
              required
              placeholder="2026-10-03T20:00:00Z"
              value={knownAt}
              onChange={(e) => setKnownAt(e.target.value)}
            />
          </label>
          <label>
            Currency
            <input
              required
              maxLength={3}
              value={currency}
              onChange={(e) => setCurrency(e.target.value)}
            />
          </label>
          <label>
            Benefited customer legal identity
            <input
              required
              value={customer}
              onChange={(e) => setCustomer(e.target.value)}
            />
          </label>
          <button disabled={busy}>Inspect complete report</button>
        </form>
        {report && (
          <dl>
            <div>
              <dt>Economic-period signed realized flow</dt>
              <dd>{show(report.realized_flow, currency)}</dd>
            </div>
            <div>
              <dt>Active eligible recorded realization</dt>
              <dd>{show(report.active_eligible_realized, currency)}</dd>
            </div>
            <div>
              <dt>Matching confirmed population</dt>
              <dd>{show(report.matching_validated, currency)}</dd>
            </div>
            <div>
              <dt>Historical / exception realization</dt>
              <dd>{show(report.historical_exception_realized, currency)}</dd>
            </div>
            <div>
              <dt>Compatible ratio</dt>
              <dd>
                {report.ratio === null
                  ? "Unknown / ineligible"
                  : `${report.ratio}%`}
              </dd>
            </div>
            <div>
              <dt>Coverage / cutoff</dt>
              <dd>
                {report.context.coverage} · {report.context.known_at}
              </dd>
            </div>
          </dl>
        )}
      </section>
    </div>
  );
}
