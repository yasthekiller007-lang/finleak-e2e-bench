"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import type { CurrentUser, FinancialDocument } from "@/lib/documents";
import { financialRequest, money } from "@/lib/financial";
import type {
  Assessment,
  ReviewRecord,
  Source,
  SourceDetail,
  Summary,
} from "@/lib/financial";
import { FinancialReviewForm } from "@/components/financial-review-form";
import { ProofWorkspace } from "@/components/proof-workspace";

type Page<T> = { items: T[]; total: number };
function Value({ value }: { value: unknown }) {
  if (value === null)
    return (
      <span className="muted">
        Unknown / explicitly not applicable — review meaning
      </span>
    );
  if (Array.isArray(value))
    return (
      <ul>
        {value.map((v, i) => (
          <li key={i}>
            <Value value={v} />
          </li>
        ))}
      </ul>
    );
  if (typeof value === "object")
    return (
      <dl>
        {Object.entries(value as Record<string, unknown>).map(([key, v]) => (
          <div key={key}>
            <dt>{key.replaceAll("_", " ")}</dt>
            <dd>
              <Value value={v} />
            </dd>
          </div>
        ))}
      </dl>
    );
  return <span>{String(value)}</span>;
}
export function FinancialWorkspace({
  user,
  overview = false,
}: {
  user: CurrentUser;
  overview?: boolean;
}) {
  const [organizationId, setOrganizationId] = useState(
    user.organizations[0]?.id ?? "",
  );
  const [refresh, setRefresh] = useState(0);
  const [sources, setSources] = useState<Source[]>([]);
  const [documents, setDocuments] = useState<FinancialDocument[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [assessments, setAssessments] = useState<Page<Assessment>>({
    items: [],
    total: 0,
  });
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState("");
  const [source, setSource] = useState<SourceDetail | null>(null);
  const [detail, setDetail] = useState<Assessment | null>(null);
  const [openProof, setOpenProof] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const organization = user.organizations.find((o) => o.id === organizationId);
  const finalAuthority =
    organization?.role === "owner" || organization?.role === "admin";
  const writable = organization?.role !== "viewer";
  useEffect(() => {
    if (!organizationId) return;
    let current = true;
    Promise.all([
      financialRequest<Page<Source>>(organizationId, "sources?limit=100"),
      financialRequest<Summary>(organizationId, "summary"),
      financialRequest<Page<Assessment>>(
        organizationId,
        `evaluations?limit=20&offset=${offset}`,
      ),
      fetch(`/api/organizations/${organizationId}/documents?limit=100`, {
        cache: "no-store",
      }).then(async (r) => {
        if (!r.ok) throw new Error("Unable to load source documents.");
        return r.json() as Promise<Page<FinancialDocument>>;
      }),
    ])
      .then(([sourcesPage, totals, findings, docs]) => {
        if (current) {
          setSources(sourcesPage.items);
          setSummary(totals);
          setAssessments(findings);
          setDocuments(docs.items);
          setError("");
        }
      })
      .catch((cause) => {
        if (current) {
          setSources([]);
          setSummary(null);
          setAssessments({ items: [], total: 0 });
          setDocuments([]);
          setDetail(null);
          setError(cause.message);
        }
      });
    return () => {
      current = false;
    };
  }, [organizationId, refresh, offset]);
  useEffect(() => {
    if (!selected || !organizationId) return;
    let current = true;
    financialRequest<SourceDetail>(organizationId, `sources/${selected}`)
      .then((result) => {
        if (current) setSource(result);
      })
      .catch((cause) => {
        if (current) {
          setSource(null);
          setError(cause.message);
        }
      });
    return () => {
      current = false;
    };
  }, [organizationId, selected, refresh]);
  async function action(
    work: () => Promise<unknown>,
    success = "Review action recorded. Reload current authority before continuing.",
    refreshData = true,
  ) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await work();
      if (refreshData) setRefresh((v) => v + 1);
      setNotice(success);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Unable to save review.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function saveReview(body: unknown) {
    await financialRequest(
      organizationId,
      `sources/${selected}/reviews`,
      body,
      crypto.randomUUID(),
    );
    setRefresh((v) => v + 1);
  }
  function reviewDecision(
    record: ReviewRecord,
    state: "approved" | "revoked",
    reason: string,
  ) {
    if (
      state === "revoked" &&
      !window.confirm(
        "Revoke this current authority? Historical evaluations remain unchanged; new positive authority may be blocked.",
      )
    )
      return;
    return action(() =>
      financialRequest(
        organizationId,
        `sources/${selected}/reviews`,
        {
          kind: record.kind,
          key: record.key,
          state,
          expected_revision: record.id,
          knowledge_cutoff: new Date().toISOString(),
          reason,
          uncertainty_resolution: record.payload.uncertainty_resolution,
          value: record.payload.value,
          evidence: record.payload.evidence,
        },
        crypto.randomUUID(),
      ),
    );
  }
  async function showDetail(row: Assessment, proof = false) {
    setDetail(null);
    setOpenProof(false);
    await action(
      async () => {
        const result = await financialRequest<Assessment>(
          organizationId,
          `evaluations/${row.id}`,
        );
        setDetail(result);
        setOpenProof(proof);
      },
      "Assessment loaded. No review or finding decision was changed.",
      false,
    );
  }
  if (!organization)
    return (
      <section className="card">
        <h2>No organization access</h2>
        <p>
          Ask your administrator to add your verified account to an
          organization.
        </p>
      </section>
    );
  const documentName = (id: string) =>
    documents.find((d) => d.id === id)?.original_filename ?? "Source document";
  return (
    <>
      <label>
        Organization
        <select
          aria-label="Organization"
          value={organizationId}
          disabled={busy}
          onChange={(e) => {
            setOrganizationId(e.target.value);
            setSelected("");
            setSource(null);
            setDetail(null);
            setSummary(null);
            setAssessments({ items: [], total: 0 });
            setOffset(0);
          }}
        >
          {user.organizations.map((o) => (
            <option key={o.id} value={o.id}>
              {o.name}
            </option>
          ))}
        </select>
      </label>
      {error && (
        <p className="notice" role="alert">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      <section className="card">
        <h2>Potential leakage for review</h2>
        {summary ? (
          <>
            <div className="metric-grid">
              {Object.entries(summary.potential_by_currency).map(
                ([currency, amount]) => (
                  <article className="metric-card" key={currency}>
                    <strong>{money(amount, currency)}</strong>
                    <p>Current potential discrepancy</p>
                  </article>
                ),
              )}
            </div>
            {Object.keys(summary.potential_by_currency).length === 0 && (
              <p>
                No current monetary findings. Blocked and unassessed scopes
                remain unknown.
              </p>
            )}
            <p>
              {summary.counts.findings} findings · {summary.counts.blocked}{" "}
              blocked assessments · {summary.counts.assessed} other assessed
              scopes · {summary.counts.stale} historical assessments requiring
              reassessment
            </p>
            <p className="muted">{summary.coverage}</p>
            {summary.limited && (
              <p>Summary covers the most recent 1,000 evaluations only.</p>
            )}
          </>
        ) : (
          <p>Loading assessment coverage…</p>
        )}
      </section>
      <section className="card">
        <h2>Assessments and review queue</h2>
        {assessments.items.length === 0 && (
          <p>
            No assessments recorded yet. Review contractual and billed facts,
            governing documents and the source relationship first.
          </p>
        )}
        {assessments.items.map((row) => (
          <article className="financial-result" key={row.id}>
            <div>
              <h3>
                {row.scope_summary?.label ?? row.scope_key}:{" "}
                {row.potential === null
                  ? "Not a monetary finding"
                  : money(row.potential, row.currency)}
              </h3>
              <p>{row.explanation}</p>
              <p>
                Contracted {money(row.expected, row.currency)} · Billed{" "}
                {money(row.actual, row.currency)}
              </p>
              {row.scope_summary?.quantity && (
                <p>
                  Contracted unit price{" "}
                  {money(row.scope_summary.contracted_rate, row.currency)} ·
                  Billed unit price{" "}
                  {money(row.scope_summary.billed_rate, row.currency)} · Billed
                  quantity {row.scope_summary.quantity} {row.scope_summary.unit}
                </p>
              )}
              <span className="badge">
                {row.stale
                  ? "Inputs changed — reassess"
                  : (row.status?.replaceAll("_", " ") ??
                    row.outcome.replaceAll("_", " ").toLowerCase())}
              </span>
            </div>
            <button
              className="button"
              disabled={busy}
              onClick={() => showDetail(row)}
            >
              Review evidence
            </button>
            <button disabled={busy} onClick={() => showDetail(row, true)}>
              View proof
            </button>
          </article>
        ))}
        <div>
          <button
            disabled={offset === 0 || busy}
            onClick={() => setOffset((v) => Math.max(0, v - 20))}
          >
            Previous assessments
          </button>{" "}
          <button
            disabled={offset + 20 >= assessments.total || busy}
            onClick={() => setOffset((v) => v + 20)}
          >
            Next assessments
          </button>
        </div>
      </section>
      {detail && (
        <section className="card">
          <h2>Assessment evidence</h2>
          <p>{detail.explanation}</p>
          <p>
            Expected {money(detail.expected, detail.currency)} · Actual{" "}
            {money(detail.actual, detail.currency)} · Potential{" "}
            {money(detail.potential, detail.currency)}
          </p>
          {detail.stale && (
            <p>
              Historical result: inputs changed. Its original monetary amount is
              preserved.
            </p>
          )}
          {detail.snapshot?.billing_scope && (
            <details open>
              <summary>Approved billed scope</summary>
              <Value value={detail.snapshot.billing_scope} />
            </details>
          )}
          {detail.snapshot?.calculation && (
            <>
              <p>{detail.snapshot.calculation.formula}</p>
              <details>
                <summary>Exact calculation and rounding</summary>
                <Value value={detail.snapshot.calculation} />
              </details>
            </>
          )}
          {detail.snapshot?.inputs.map((record) => (
            <details key={record.id}>
              <summary>
                {record.kind.replaceAll("_", " ")} · {record.key} ·{" "}
                {record.state}
              </summary>
              <Value value={record.payload.value} />
              <p>
                Reviewed by {record.actor_id} at {record.created_at}.{" "}
                {record.payload.reason}
              </p>
              {record.provenance.map((e, i) => (
                <div key={i}>
                  <Link href={`/documents/${organizationId}/${e.document_id}`}>
                    {documentName(e.document_id)}
                  </Link>
                  <p>
                    {e.location}: {e.quote}
                  </p>
                  <details>
                    <summary>Source lineage</summary>
                    <Value value={e} />
                  </details>
                </div>
              ))}
            </details>
          ))}
          <details>
            <summary>Audit identifiers and rule versions</summary>
            <p>
              {detail.id} · {detail.snapshot?.compiler} ·{" "}
              {detail.snapshot?.rules}
            </p>
          </details>
          <ProofWorkspace
            key={`${organizationId}:${detail.id}:${openProof}`}
            organizationId={organizationId}
            assessment={detail}
            role={organization.role}
            autoOpen={openProof}
          />
          {finalAuthority && detail.potential !== null && !detail.stale && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                if (
                  f.get("status") === "false_positive" &&
                  !window.confirm(
                    "Dismiss this finding? Historical calculations and recovery records remain preserved; new positive authority may be blocked.",
                  )
                )
                  return;
                void action(
                  () =>
                    financialRequest(
                      organizationId,
                      `evaluations/${detail.id}/decision`,
                      {
                        status: String(f.get("status")),
                        reason: String(f.get("reason")),
                        expected_decision: detail.decision_id,
                      },
                    ).then(() => setDetail(null)),
                  "Finding decision recorded. Historical calculated amounts are unchanged.",
                );
              }}
            >
              <label>
                Finding decision
                <select name="status">
                  <option value="confirmed">
                    Confirm supported discrepancy
                  </option>
                  <option value="false_positive">Dismiss finding</option>
                  <option value="needs_review">Further review required</option>
                </select>
              </label>
              <label>
                Decision reason
                <input name="reason" required />
              </label>
              <button className="button" disabled={busy}>
                Save finding review
              </button>
            </form>
          )}
        </section>
      )}
      {overview ? (
        <p>
          <Link href="/leakage-cases">Open contract and invoice review →</Link>
        </p>
      ) : (
        <section className="card">
          <h2>Contract and invoice authority</h2>
          <p>
            Extraction is candidate information. Analysts prepare reviews;
            owners and administrators approve or revoke authority.
          </p>
          {writable && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const form = new FormData(e.currentTarget);
                const doc = documents.find(
                  (d) => d.id === form.get("document"),
                );
                if (doc)
                  void action(
                    () =>
                      financialRequest<Source>(organizationId, "sources", {
                        document_id: doc.id,
                        kind: doc.document_type,
                      }).then((s) => setSelected(s.id)),
                    "Source review opened. No financial facts were approved.",
                  );
              }}
            >
              <label>
                Start stable source review
                <select name="document" required>
                  <option value="">Select source document</option>
                  {documents
                    .filter(
                      (d) =>
                        d.document_type === "contract" ||
                        d.document_type === "invoice",
                    )
                    .map((d) => (
                      <option value={d.id} key={d.id}>
                        {d.original_filename} · {d.document_type}
                      </option>
                    ))}
                </select>
              </label>
              <button className="button" disabled={busy}>
                Open reviewed source
              </button>
            </form>
          )}
          <p className="muted">
            Source selection lists the first 100 documents and reviewed sources.
            All assessments remain available through the paginated register.
          </p>
          <label>
            Reviewed source
            <select
              aria-label="Reviewed source"
              value={selected}
              disabled={busy}
              onChange={(e) => {
                setSelected(e.target.value);
                setSource(null);
              }}
            >
              <option value="">Select contract or invoice</option>
              {sources.map((s) => (
                <option key={s.id} value={s.id}>
                  {documentName(s.document_id)} · {s.kind}
                </option>
              ))}
            </select>
          </label>
          {source && source.id === selected && (
            <>
              <Link href={`/documents/${organizationId}/${source.document_id}`}>
                Open document and extraction candidates
              </Link>
              {source.reviews.map((record) => (
                <article key={record.id} className="financial-result">
                  <div>
                    <h3>
                      {record.kind.replaceAll("_", " ")} · {record.key}
                    </h3>
                    <span className="badge">{record.state}</span>
                    <details>
                      <summary>Reviewed values and supporting source</summary>
                      <Value value={record.payload.value} />
                      {record.provenance.map((e, i) => (
                        <div key={i}>
                          <p>
                            {e.location}: {e.quote}
                          </p>
                          <p>
                            Extracted:{" "}
                            {e.normalized_candidate ?? "Manual source review"} ·
                            Reviewed meaning above
                          </p>
                        </div>
                      ))}
                      <p>{record.payload.uncertainty_resolution}</p>
                    </details>
                  </div>
                  {finalAuthority && record.state !== "revoked" && (
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        const f = new FormData(e.currentTarget);
                        void reviewDecision(
                          record,
                          String(f.get("state")) as "approved" | "revoked",
                          String(f.get("reason")),
                        );
                      }}
                    >
                      <label>
                        Decision
                        <select name="state">
                          <option value="approved">
                            Approve reviewed meaning
                          </option>
                          {(record.state === "approved" ||
                            record.state === "prepared") && (
                            <option value="revoked">
                              Withdraw review / revoke financial approval
                            </option>
                          )}
                        </select>
                      </label>
                      <label>
                        Decision reason
                        <input name="reason" required />
                      </label>
                      <label>
                        <input type="checkbox" required /> I verified source,
                        scope, exceptions and resolved uncertainty.
                      </label>
                      <button className="button" disabled={busy}>
                        Record authority decision
                      </button>
                    </form>
                  )}
                </article>
              ))}
              {writable && (
                <FinancialReviewForm
                  key={source.id}
                  source={source}
                  sources={sources}
                  documents={documents}
                  onSave={saveReview}
                />
              )}
              {source.kind === "invoice" && finalAuthority && (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    const f = new FormData(e.currentTarget);
                    void action(
                      () =>
                        financialRequest(
                          organizationId,
                          `sources/${source.id}/evaluate`,
                          {
                            scope_key: String(f.get("scope")),
                            expected_revisions: source.revision_ids,
                          },
                        ),
                      "Assessment created or retrieved. Finding confirmation remains separate.",
                    );
                  }}
                >
                  <label>
                    Approved scope to assess
                    <select name="scope" required>
                      {source.approved_inputs
                        .filter(
                          (r) =>
                            r.kind === "billing_scope" &&
                            r.state === "approved",
                        )
                        .map((r) => (
                          <option key={r.id}>{r.key}</option>
                        ))}
                    </select>
                  </label>
                  <button className="button" disabled={busy}>
                    Assess approved inputs
                  </button>
                </form>
              )}
            </>
          )}
        </section>
      )}
    </>
  );
}
