"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { CurrentUser, FinancialDocument } from "@/lib/documents";
import { money } from "@/lib/financial";
import type { Assessment } from "@/lib/financial";
import {
  activitySeries,
  assessmentLabel,
  documentFor,
  exposureShare,
  isReviewNeeded,
  linkedAssessments,
  liveWorkspaceGateway,
  ruleLabel,
  viewLabels,
} from "@/lib/product-workspace";
import type {
  ProductView,
  ProofDetail,
  WorkspaceData,
  WorkspaceGateway,
} from "@/lib/product-workspace";
import { FinancialDecisionPanel } from "@/components/financial-decision-panel";
import { FinancialDecisionAudit } from "@/components/financial-decision-audit";
import { ProductIcon } from "@/components/product-icons";
import {
  contractName,
  hasNextWindow,
  mergeRecords,
  queueRows,
} from "@/lib/exception-workbench";
import { ExceptionPortfolio } from "@/components/exception-portfolio";
import { ExceptionInvestigation } from "@/components/exception-investigation";
import type { ExceptionQuery } from "@/lib/server-exceptions";
import { ServerExceptionsQueue } from "@/components/server-exceptions-queue";

type Selection = { org: string; id: string } | null;
const date = (value: string) =>
  Number.isFinite(Date.parse(value))
    ? new Intl.DateTimeFormat("en", {
        month: "short",
        day: "numeric",
        year: "numeric",
        timeZone: "UTC",
      }).format(new Date(value))
    : "Date not recorded";
const shortId = (value: string) => `${value.slice(0, 8)}…${value.slice(-4)}`;

function Status({ assessment }: { assessment: Assessment }) {
  const tone = assessment.stale
    ? "neutral"
    : assessment.status === "confirmed"
      ? "success"
      : assessment.status === "false_positive"
        ? "neutral"
        : assessment.outcome === "NEEDS_REVIEW"
          ? "warning"
          : assessment.potential !== null
            ? "blue"
            : "success";
  return (
    <span className={`p-status ${tone}`}>
      <span />
      {assessmentLabel(assessment)}
    </span>
  );
}
function Empty({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="p-empty">
      <div className="p-empty-symbol">
        <ProductIcon name="search" size={26} />
      </div>
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
function ErrorNotice({
  message,
  retry,
}: {
  message: string;
  retry?: () => void;
}) {
  return (
    <div className="p-error" role="alert">
      <ProductIcon name="anomaly" />
      <div>
        <strong>We couldn’t complete this request</strong>
        <p>{message}</p>
      </div>
      {retry && <button onClick={retry}>Try again</button>}
    </div>
  );
}

export function ProductConsole({
  user,
  view,
  gateway = liveWorkspaceGateway,
  demo = false,
  initialOrg = "",
  initialInvoice = "",
  initialAssessment = "",
  initialExceptionFilters,
  initialExceptionLimit,
  onExceptionApplied,
  makeViewLink,
  onOrganizationChange,
}: {
  user: CurrentUser;
  view: ProductView;
  gateway?: WorkspaceGateway;
  demo?: boolean;
  initialOrg?: string;
  initialInvoice?: string;
  initialAssessment?: string;
  initialExceptionFilters?: ExceptionQuery;
  initialExceptionLimit?: number;
  onExceptionApplied?: (filters: ExceptionQuery, limit: number) => void;
  makeViewLink?: (filters: ExceptionQuery, limit: number) => string;
  onOrganizationChange?: (org: string) => void;
}) {
  const [orgId, setOrgId] = useState(
    user.organizations.some((o) => o.id === initialOrg)
      ? initialOrg
      : (user.organizations[0]?.id ?? ""),
  );
  const [state, setState] = useState<{
    org: string;
    data: WorkspaceData;
  } | null>(null);
  const [refresh, setRefresh] = useState(0),
    [error, setError] = useState(""),
    [search, setSearch] = useState(""),
    [filter, setFilter] = useState("all"),
    [sort, setSort] = useState("newest"),
    [currency, setCurrency] = useState("all"),
    [supplier, setSupplier] = useState("all"),
    [contract, setContract] = useState("all");
  const [queuePosition, setQueuePosition] = useState({ key: "", page: 1 });
  const [selected, setSelected] = useState<Selection>(
    initialAssessment ? { org: orgId, id: initialAssessment } : null,
  );
  const [selection, setSelection] = useState<{
      org: string;
      detail: Assessment;
    } | null>(null),
    [detailError, setDetailError] = useState("");
  const [loadingMore, setLoadingMore] = useState(false),
    [moreError, setMoreError] = useState("");
  const loadController = useRef<AbortController | null>(null),
    moreController = useRef<AbortController | null>(null);
  const org = user.organizations.find((o) => o.id === orgId);
  const data = state?.org === orgId ? state.data : null;
  const detail =
    selection?.org === orgId &&
    selected?.org === orgId &&
    selection.detail.id === selected.id
      ? selection.detail
      : null;
  const route = (target: ProductView, query: Record<string, string> = {}) =>
    `${demo ? "/demo" : ""}/${target}?${new URLSearchParams({ org: orgId, ...query })}`;
  useEffect(() => {
    if (!orgId) return;
    const controller = new AbortController();
    loadController.current = controller;
    const loader =
      (view === "anomalies" || view === "review") &&
      gateway.queryExceptions &&
      gateway.loadContext
        ? gateway.loadContext
        : gateway.load;
    void loader(orgId, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setState({ org: orgId, data: result });
          setError("");
        }
      })
      .catch((cause) => {
        if (!controller.signal.aborted) {
          setState(null);
          setError(
            cause instanceof Error ? cause.message : "Workspace unavailable.",
          );
        }
      });
    return () => {
      controller.abort();
      moreController.current?.abort();
    };
  }, [gateway, orgId, refresh, view]);
  useEffect(() => {
    if (!selected || selected.org !== orgId) return;
    const controller = new AbortController();
    void gateway
      .assessment(orgId, selected.id, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setSelection({ org: orgId, detail: result });
          setDetailError("");
        }
      })
      .catch((cause) => {
        if (!controller.signal.aborted)
          setDetailError(
            cause instanceof Error ? cause.message : "Assessment unavailable.",
          );
      });
    return () => controller.abort();
  }, [gateway, orgId, selected, refresh]);
  function reload() {
    loadController.current?.abort();
    moreController.current?.abort();
    setState(null);
    setSelection(null);
    setDetailError("");
    setLoadingMore(false);
    setMoreError("");
    setError("");
    setRefresh((n) => n + 1);
  }
  function choose(id: string) {
    setSelection(null);
    setDetailError("");
    setSelected({ org: orgId, id });
  }
  async function loadMore(kind: "documents" | "assessments" | "sources") {
    if (!data || loadingMore || !gateway[kind]) return;
    const controller = new AbortController();
    moreController.current = controller;
    setLoadingMore(true);
    setMoreError("");
    try {
      const page = await gateway[kind]!(
        orgId,
        data[kind].offset + data[kind].limit,
        controller.signal,
      );
      if (!controller.signal.aborted)
        setState((current) => {
          if (current?.org !== orgId) return current;
          if (kind === "documents") {
            const docs = page as WorkspaceData["documents"];
            return {
              org: orgId,
              data: {
                ...current.data,
                documents: {
                  ...docs,
                  items: mergeRecords(current.data.documents.items, docs.items),
                },
              },
            };
          }
          if (kind === "sources") {
            const sources = page as WorkspaceData["sources"];
            return {
              org: orgId,
              data: {
                ...current.data,
                sources: {
                  ...sources,
                  items: mergeRecords(
                    current.data.sources.items,
                    sources.items,
                  ),
                },
              },
            };
          }
          const rows = page as WorkspaceData["assessments"];
          return {
            org: orgId,
            data: {
              ...current.data,
              assessments: {
                ...rows,
                items: mergeRecords(current.data.assessments.items, rows.items),
              },
            },
          };
        });
    } catch (cause) {
      if (!controller.signal.aborted)
        setMoreError(
          cause instanceof Error
            ? cause.message
            : "Unable to load more records.",
        );
    } finally {
      if (!controller.signal.aborted) setLoadingMore(false);
    }
  }
  if (!org)
    return (
      <section className="p-card">
        <Empty title="Your workspace is waiting">
          Ask your administrator to add your verified account to an
          organization.
        </Empty>
      </section>
    );
  const page = viewLabels[view];
  const open = selected?.org === orgId;
  const reviews = data?.assessments.items.filter(isReviewNeeded) ?? [];
  const confirmed =
    data?.assessments.items.filter(
      (a) => !a.stale && a.status === "confirmed",
    ) ?? [];
  const invoiceDocs =
    data?.documents.items.filter((d) => d.document_type === "invoice") ?? [];
  const contractDocs =
    data?.documents.items.filter((d) => d.document_type === "contract") ?? [];
  const q = search.trim().toLowerCase();
  const financialView = view === "anomalies" || view === "review";
  const findings = data
    ? queueRows(data, {
        search,
        status: filter,
        currency,
        supplier,
        contract,
        sort,
        invoice: initialInvoice,
        reviewOnly: view === "review",
      })
    : [];
  const positionKey = JSON.stringify([
    orgId,
    search,
    filter,
    currency,
    supplier,
    contract,
    sort,
    initialInvoice,
    view,
  ]);
  const queuePages = Math.max(1, Math.ceil(findings.length / 10));
  const queuePage = Math.min(
    queuePosition.key === positionKey ? queuePosition.page : 1,
    queuePages,
  );
  const queueVisible = findings.slice((queuePage - 1) * 10, queuePage * 10);
  const currencyOptions = [
    ...new Set(
      data?.assessments.items.map((a) => a.currency ?? "unknown") ?? [],
    ),
  ].sort();
  const supplierOptions = [
    ...new Set(
      data?.assessments.items.map((a) =>
        JSON.stringify(a.queue_context?.supplier_party ?? null),
      ) ?? [],
    ),
  ].sort();
  const contractOptions = [
    ...new Set(
      data?.assessments.items.map((a) =>
        JSON.stringify(a.queue_context?.contract_source_id ?? null),
      ) ?? [],
    ),
  ].sort();
  const documents = (view === "contracts" ? contractDocs : invoiceDocs)
    .filter(
      (d) =>
        d.original_filename.toLowerCase().includes(q) &&
        (filter === "all" || d.processing_status === filter),
    )
    .sort((a, b) =>
      sort === "name"
        ? a.original_filename.localeCompare(b.original_filename)
        : b.uploaded_at.localeCompare(a.uploaded_at),
    );
  return (
    <div className="product-console">
      {demo && (
        <div className="p-demo-banner" role="note">
          <span className="p-demo-chip">DEMO</span>
          <strong>Synthetic workspace</strong>
          <span>
            All records, amounts and fingerprints are examples. No live API
            requests. Decisions reset when you leave this page.
          </span>
          <Link href="/login">
            Go to sign in <ProductIcon name="arrow" size={15} />
          </Link>
        </div>
      )}
      <div className="p-context">
        <div className="p-org-mark">{org.name.slice(0, 1)}</div>
        <label>
          <span className="sr-only">Active organization</span>
          <select
            aria-label="Active organization"
            value={orgId}
            onChange={(e) => {
              if (onOrganizationChange) {
                onOrganizationChange(e.target.value);
                return;
              }
              moreController.current?.abort();
              setOrgId(e.target.value);
              setState(null);
              setSelection(null);
              setSelected(null);
              setError("");
              setDetailError("");
              setSearch("");
              setFilter("all");
              setCurrency("all");
              setSupplier("all");
              setContract("all");
              setSort("newest");
              setMoreError("");
              setLoadingMore(false);
            }}
          >
            {user.organizations.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </select>
        </label>
        <span className="p-context-divider" />
        <span className="p-role">{org.role}</span>
        <span className="p-context-private">
          <ProductIcon name="shield" size={14} />
          Organization-restricted access
        </span>
      </div>
      <div className="p-page-heading">
        <div>
          <p className="p-eyebrow">
            {open ? "EVIDENCE WORKSPACE" : "FINANCIAL INTELLIGENCE"}
          </p>
          <h1>{open ? "Every finding has a story." : page.title}</h1>
          <p>
            {open
              ? "Follow the calculation back to its approved source evidence."
              : page.description}
          </p>
        </div>
        <div className="p-heading-actions">
          {open && selected && (
            <Link
              className="p-text-link"
              href={route(view, { assessment: selected.id })}
            >
              Direct case link <ProductIcon name="external" size={14} />
            </Link>
          )}
          <button
            className="p-icon-button"
            aria-label="Refresh workspace"
            onClick={reload}
          >
            <ProductIcon name="refresh" />
          </button>
          {!demo && (
            <Link className="p-button" href="/documents">
              <ProductIcon name="upload" size={16} />
              Import documents
            </Link>
          )}
          {demo && (
            <Link className="p-button" href={route("invoices")}>
              <ProductIcon name="invoice" size={16} />
              Explore invoices
            </Link>
          )}
        </div>
      </div>
      {data && financialView && gateway.queryExceptions && (
        <div hidden={open || Boolean(error)}>
          <ServerExceptionsQueue
            key={`${user.id}:${orgId}:${view}:${initialInvoice}`}
            gateway={gateway}
            org={orgId}
            reviewOnly={view === "review"}
            invoice={initialInvoice}
            onOpen={choose}
            demo={demo}
            refresh={refresh}
            initialFilters={initialExceptionFilters}
            initialLimit={initialExceptionLimit}
            organization={
              org?.name ?? "Authorized organization label unavailable"
            }
            criteriaAuthorized={Boolean(org)}
            owner={user.id}
            onApplied={onExceptionApplied}
            makeViewLink={makeViewLink}
          />
        </div>
      )}
      {error ? (
        <ErrorNotice message={error} retry={reload} />
      ) : !data ? (
        <div className="p-loading" role="status">
          <span className="p-spinner" />
          Loading your organization’s financial workspace…
        </div>
      ) : open ? (
        <>
          <button
            className="p-back"
            onClick={() => {
              setSelected(null);
              setSelection(null);
              setDetailError("");
            }}
          >
            ← Back to {page.title.toLowerCase()}
          </button>
          {detailError ? (
            <ErrorNotice
              message={detailError}
              retry={() => {
                setDetailError("");
                setRefresh((n) => n + 1);
              }}
            />
          ) : !detail ? (
            <div className="p-loading" role="status">
              Loading assessment and source lineage…
            </div>
          ) : (
            <AssessmentDetail
              key={`${orgId}:${detail.id}`}
              detail={detail}
              data={data}
              orgId={orgId}
              role={org.role}
              gateway={gateway}
              demo={demo}
              onDecision={(updated) => {
                setSelection({ org: orgId, detail: updated });
                setRefresh((n) => n + 1);
              }}
            />
          )}
        </>
      ) : financialView && gateway.queryExceptions ? null : view ===
        "dashboard" ? (
        <>
          <div className="p-metrics">
            <Metric
              label="Current findings"
              value={data.summary.counts.findings ?? "—"}
              note="Current, undismissed assessed scopes"
              icon="anomaly"
              accent="blue"
            />
            <Metric
              label="Awaiting human review"
              value={reviews.length}
              note={`In ${data.assessments.items.length} loaded assessments`}
              icon="review"
              accent="amber"
            />
            <Metric
              label="Confirmed anomalies"
              value={confirmed.length}
              note="In the loaded assessment window"
              icon="check"
              accent="teal"
            />
            <Metric
              label="Invoices processed"
              value={`${invoiceDocs.filter((d) => d.processing_status === "processed").length} / ${invoiceDocs.length}`}
              note={`${contractDocs.filter((d) => d.processing_status === "processed").length} processed contracts in loaded documents`}
              icon="invoice"
              accent="violet"
            />
          </div>
          <div className="p-overview-grid">
            <section className="p-exposure">
              <div className="p-exposure-heading">
                <span className="p-live-dot" />
                POTENTIAL DISCREPANCY
                <ProductIcon name="shield" size={18} />
              </div>
              <div className="p-exposure-amounts">
                {Object.entries(data.summary.potential_by_currency).length ? (
                  Object.entries(data.summary.potential_by_currency).map(
                    ([currency, amount]) => (
                      <div key={currency}>
                        <strong>{money(amount, null)}</strong>
                        <span>{currency}</span>
                      </div>
                    ),
                  )
                ) : (
                  <strong className="p-no-amount">
                    No current monetary findings
                  </strong>
                )}
              </div>
              <p>
                Evidence-led opportunity.
                <br />
                Not recovered cash or guaranteed savings.
              </p>
              <div className="p-exposure-bottom">
                <span>
                  Recovered amount <strong>Not reported here</strong>
                </span>
                <Link href={route("anomalies")}>
                  Explore findings <ProductIcon name="arrow" size={17} />
                </Link>
              </div>
            </section>
            <section className="p-card p-rule-card">
              <div className="p-section-heading">
                <div>
                  <p className="p-eyebrow">WHERE TO FOCUS</p>
                  <h2>Exposure by financial rule</h2>
                </div>
                <span className="p-subtle-tag">Separate currencies</span>
              </div>
              <div className="p-rules">
                {Object.entries(data.summary.potential_by_rule ?? {}).length ? (
                  Object.entries(data.summary.potential_by_rule ?? {}).map(
                    ([rule, currencies], index) => (
                      <div className="p-rule" key={rule}>
                        <span className={`p-rule-icon tone-${index % 3}`}>
                          <ProductIcon
                            name={
                              index % 3 === 0
                                ? "invoice"
                                : index % 3 === 1
                                  ? "contract"
                                  : "anomaly"
                            }
                            size={17}
                          />
                        </span>
                        <div>
                          <strong>{ruleLabel(rule)}</strong>
                          {Object.entries(currencies).map(
                            ([currency, amount]) => (
                              <div className="p-rule-amount" key={currency}>
                                <div className="p-meter">
                                  <span
                                    style={{
                                      width: `${exposureShare(amount, data.summary.potential_by_currency[currency] ?? "0")}%`,
                                    }}
                                  />
                                </div>
                                <span>{money(amount, currency)}</span>
                              </div>
                            ),
                          )}
                        </div>
                      </div>
                    ),
                  )
                ) : (
                  <Empty title="No rule breakdown available">
                    The financial service has not returned a category breakdown.
                  </Empty>
                )}
              </div>
            </section>
          </div>
          <ExceptionPortfolio data={data} />
          <section className="p-card p-register">
            <div className="p-section-heading">
              <div>
                <p className="p-eyebrow">YOUR NEXT DECISION</p>
                <h2>Findings that deserve a closer look</h2>
              </div>
              <Link className="p-text-link" href={route("review")}>
                Open review queue <ProductIcon name="arrow" size={16} />
              </Link>
            </div>
            <AssessmentTable
              rows={data.assessments.items.filter(isReviewNeeded).slice(0, 4)}
              data={data}
              open={choose}
            />
          </section>
          <div className="p-lower-grid">
            <section className="p-card">
              <div className="p-section-heading">
                <div>
                  <p className="p-eyebrow">ACTIVITY</p>
                  <h2>Assessments over time</h2>
                </div>
                <span className="p-subtle-tag">Loaded records only</span>
              </div>
              <Activity assessments={data.assessments.items} />
            </section>
            <section className="p-card p-coverage">
              <span className="p-coverage-icon">
                <ProductIcon name="shield" size={24} />
              </span>
              <h2>Confidence starts with coverage.</h2>
              <p>{data.summary.coverage}</p>
              <div>
                <span>
                  {data.summary.counts.blocked ?? "—"}
                  <small>Evidence needed</small>
                </span>
                <span>
                  {data.summary.counts.stale ?? "—"}
                  <small>Reassessment needed</small>
                </span>
              </div>
              <Link className="p-text-link" href={route("invoices")}>
                Follow the document trail <ProductIcon name="arrow" size={16} />
              </Link>
            </section>
          </div>
          <Coverage data={data} />
        </>
      ) : (
        <>
          <div className="p-view-intro">
            <div>
              <span className="p-small-label">
                {view === "invoices" || view === "contracts"
                  ? "DOCUMENT WORKSPACE"
                  : "ASSESSMENT REGISTER"}
              </span>
              <p>
                {view === "review"
                  ? "A financial finding and a proof review are separate decisions."
                  : "Traceable records. Explicit uncertainty. No automatic approvals."}
              </p>
            </div>
            <Link className="p-text-link" href={route("dashboard")}>
              Back to overview <ProductIcon name="arrow" size={16} />
            </Link>
          </div>
          <section className="p-card p-register">
            {financialView && (
              <div className="p-queue-heading">
                <div>
                  <p className="p-eyebrow">EXCEPTIONS WORKBENCH</p>
                  <h2>
                    {view === "review"
                      ? "Human review queue"
                      : "Financial exceptions queue"}
                  </h2>
                  <p>
                    Investigate recorded findings. Every decision stays human.
                  </p>
                </div>
                <span className="p-subtle-tag">
                  {findings.length} matching · {data.assessments.items.length}{" "}
                  loaded
                </span>
              </div>
            )}
            <div className="p-register-toolbar">
              <label className="p-search">
                <ProductIcon name="search" size={18} />
                <span className="sr-only">Search loaded records</span>
                <input
                  aria-label="Search loaded records"
                  placeholder={
                    view === "invoices" || view === "contracts"
                      ? "Search filenames…"
                      : "Search invoices, scopes or findings…"
                  }
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </label>
              <label>
                <span className="sr-only">Status filter</span>
                <select
                  aria-label="Status filter"
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                >
                  <option value="all">All statuses</option>
                  {view === "invoices" || view === "contracts"
                    ? [
                        "processed",
                        "needs_review",
                        "pending",
                        "failed",
                        "needs_ocr",
                        "processing",
                        "queued",
                      ].map((s) => (
                        <option key={s} value={s}>
                          {s.replaceAll("_", " ")}
                        </option>
                      ))
                    : [
                        "Needs review",
                        "Confirmed",
                        "Dismissed",
                        "Evidence needed",
                        "Reassessment needed",
                        "No overcharge",
                      ].map((s) => <option key={s}>{s}</option>)}
                </select>
              </label>
              <label>
                <span className="sr-only">Sort records</span>
                <select
                  aria-label="Sort records"
                  value={sort}
                  onChange={(e) => setSort(e.target.value)}
                >
                  <option value="newest">Newest first</option>
                  <option
                    value={
                      view === "invoices" || view === "contracts"
                        ? "name"
                        : "oldest"
                    }
                  >
                    {view === "invoices" || view === "contracts"
                      ? "Filename A–Z"
                      : "Oldest first"}
                  </option>
                  {financialView && (
                    <>
                      <option value="amount_high">
                        Potential: high to low, within currency
                      </option>
                      <option value="amount_low">
                        Potential: low to high, within currency
                      </option>
                      <option value="status">Review status A–Z</option>
                    </>
                  )}
                </select>
              </label>
            </div>
            {financialView && (
              <div className="p-exception-filters">
                <label>
                  Currency
                  <select
                    aria-label="Currency filter"
                    value={currency}
                    onChange={(e) => setCurrency(e.target.value)}
                  >
                    <option value="all">All currencies</option>
                    {currencyOptions.map((value) => (
                      <option key={value} value={value}>
                        {value === "unknown" ? "Currency not returned" : value}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Supplier party
                  <select
                    aria-label="Supplier filter"
                    value={supplier}
                    onChange={(e) => setSupplier(e.target.value)}
                  >
                    <option value="all">All suppliers</option>
                    {supplierOptions.map((value) => (
                      <option key={value} value={value}>
                        {JSON.parse(value) ?? "Reference unavailable"}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Contract
                  <select
                    aria-label="Contract filter"
                    value={contract}
                    onChange={(e) => setContract(e.target.value)}
                  >
                    <option value="all">All contracts</option>
                    {contractOptions.map((value) => (
                      <option key={value} value={value}>
                        {JSON.parse(value)
                          ? contractName(data, JSON.parse(value))
                          : "Reference unavailable"}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  className="p-clear-filters"
                  onClick={() => {
                    setSearch("");
                    setFilter("all");
                    setCurrency("all");
                    setSupplier("all");
                    setContract("all");
                    setSort("newest");
                  }}
                >
                  Reset filters
                </button>
                <p>
                  Filters and sorting cover loaded assessments only. Potential
                  amounts are grouped by currency; no conversion or
                  cross-currency ranking.
                </p>
              </div>
            )}
            {view === "invoices" || view === "contracts" ? (
              <DocumentTable
                rows={documents}
                data={data}
                open={choose}
                org={orgId}
                demo={demo}
                route={route}
              />
            ) : (
              <>
                <AssessmentTable
                  rows={queueVisible}
                  data={data}
                  open={choose}
                />
                {queuePages > 1 && (
                  <nav
                    className="p-queue-pagination"
                    aria-label="Exception queue pagination"
                  >
                    <span>
                      Page {queuePage} of {queuePages} · 10 records per page
                    </span>
                    <button
                      disabled={queuePage === 1}
                      onClick={() =>
                        setQueuePosition({
                          key: positionKey,
                          page: queuePage - 1,
                        })
                      }
                    >
                      Previous page
                    </button>
                    <button
                      disabled={queuePage === queuePages}
                      onClick={() =>
                        setQueuePosition({
                          key: positionKey,
                          page: queuePage + 1,
                        })
                      }
                    >
                      Next page
                    </button>
                  </nav>
                )}
              </>
            )}
            <div className="p-register-footer">
              <span>
                {view === "invoices" || view === "contracts"
                  ? `${documents.length} matching ${view} · ${data.documents.items.length} / ${data.documents.total} source documents loaded`
                  : `${findings.length} matching assessments · ${data.assessments.items.length} / ${data.assessments.total} loaded`}
              </span>
              {hasNextWindow(
                view === "invoices" || view === "contracts"
                  ? data.documents
                  : data.assessments,
              ) && (
                <button
                  disabled={loadingMore}
                  onClick={() =>
                    void loadMore(
                      view === "invoices" || view === "contracts"
                        ? "documents"
                        : "assessments",
                    )
                  }
                >
                  {loadingMore ? "Loading…" : "Load more records"}
                </button>
              )}
            </div>
          </section>
          {moreError && <ErrorNotice message={moreError} />}
          <p className="p-window-note">
            Search, filters, counts and activity apply to loaded records. Source
            relationships use loaded financial sources and documents; an
            unlinked document is not a clean bill of health.
            {initialInvoice && (
              <>
                {" "}
                <Link href={route("anomalies")}>Clear invoice filter</Link>
              </>
            )}
          </p>
          {financialView && (
            <div className="p-reference-coverage">
              <span>
                References loaded: {data.sources.items.length} /{" "}
                {data.sources.total} financial sources ·{" "}
                {data.documents.items.length} / {data.documents.total}{" "}
                documents. Missing names never mean no contract exists.
              </span>
              {gateway.sources && hasNextWindow(data.sources) && (
                <button
                  disabled={loadingMore}
                  onClick={() => void loadMore("sources")}
                >
                  {loadingMore ? "Loading…" : "Load more financial sources"}
                </button>
              )}
              {hasNextWindow(data.documents) && (
                <button
                  disabled={loadingMore}
                  onClick={() => void loadMore("documents")}
                >
                  Load more reference documents
                </button>
              )}
            </div>
          )}
          {!demo && (
            <div className="p-next-step">
              <ProductIcon name="review" />
              <div>
                <strong>Need to approve extracted financial facts?</strong>
                <p>
                  Use the existing financial fact review workspace. Analysts
                  prepare; owners and administrators approve.
                </p>
              </div>
              <Link href="/leakage-cases">
                Open fact review <ProductIcon name="arrow" size={16} />
              </Link>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  note,
  icon,
  accent,
}: {
  label: string;
  value: string | number;
  note: string;
  icon: React.ComponentProps<typeof ProductIcon>["name"];
  accent: string;
}) {
  return (
    <section className="p-card p-metric">
      <div>
        <span>{label}</span>
        <span className={`p-metric-icon ${accent}`}>
          <ProductIcon name={icon} size={18} />
        </span>
      </div>
      <strong>{value}</strong>
      <p>{note}</p>
    </section>
  );
}
function Coverage({ data }: { data: WorkspaceData }) {
  return (
    <p className="p-window-note">
      <ProductIcon name="shield" size={14} />
      {data.summary.limited
        ? "Financial summary is limited to the latest 1,000 evaluations."
        : "Financial totals follow the backend’s current assessed-scope coverage."}{" "}
      Queue counts, documents and activity reflect loaded records only. No
      currency conversion or recovery calculation is applied.
    </p>
  );
}
function Activity({ assessments }: { assessments: Assessment[] }) {
  const series = activitySeries(assessments),
    max = Math.max(1, ...series.map(([, count]) => count));
  if (series.length < 2)
    return (
      <Empty title="More history, a clearer picture">
        At least two dated assessment days are needed to show activity. No trend
        is inferred.
      </Empty>
    );
  return (
    <div className="p-activity" aria-label="Assessment counts by day">
      {series.map(([day, count]) => (
        <div key={day}>
          <span>{count}</span>
          <div className="p-activity-track">
            <span style={{ height: `${(count / max) * 100}%` }} />
          </div>
          <time dateTime={day}>
            {new Intl.DateTimeFormat("en", {
              month: "short",
              day: "numeric",
              timeZone: "UTC",
            }).format(new Date(day))}
          </time>
        </div>
      ))}
    </div>
  );
}
function AssessmentTable({
  rows,
  data,
  open,
}: {
  rows: Assessment[];
  data: WorkspaceData;
  open: (id: string) => void;
}) {
  if (!rows.length)
    return (
      <Empty title="No matching assessments">
        Review your filters or prepare approved financial facts to start an
        assessment. Missing assessments do not mean there are no anomalies.
      </Empty>
    );
  return (
    <div className="p-table-scroll">
      <table className="p-table">
        <thead>
          <tr>
            <th>Invoice & scope</th>
            <th>Supplier & contract</th>
            <th>Potential discrepancy</th>
            <th>Status</th>
            <th>Assessed</th>
            <th>
              <span className="sr-only">Evidence</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((a) => (
            <tr key={a.id}>
              <td>
                <button className="p-row-link" onClick={() => open(a.id)}>
                  {documentFor(data, a)?.original_filename ??
                    `Invoice source ${shortId(a.invoice_source_id)}`}
                </button>
                <span className="p-cell-note">
                  {a.scope_summary?.label ?? a.scope_key}
                </span>
              </td>
              <td className="p-reference-cell">
                <strong>
                  {a.queue_context?.supplier_party ?? "Supplier not returned"}
                </strong>
                <span className="p-cell-note">
                  {a.queue_context?.contract_source_id
                    ? contractName(data, a.queue_context.contract_source_id)
                    : "Contract association not returned"}
                </span>
                {a.queue_context?.contract_references.map((ref) => (
                  <span className="p-cell-note" key={ref}>
                    {ref}
                  </span>
                ))}
              </td>
              <td className="p-money">
                {a.potential === null ? (
                  <span className="p-unknown">Not assessed</span>
                ) : (
                  money(a.potential, a.currency)
                )}
                {a.stale && (
                  <span className="p-cell-note">Historical amount</span>
                )}
              </td>
              <td>
                <Status assessment={a} />
              </td>
              <td className="p-date">{date(a.created_at)}</td>
              <td>
                <button
                  className="p-evidence-link"
                  aria-label={`Review evidence for ${a.scope_summary?.label ?? a.scope_key}`}
                  onClick={() => open(a.id)}
                >
                  Review evidence <ProductIcon name="arrow" size={16} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function DocumentTable({
  rows,
  data,
  open,
  org,
  demo,
  route,
}: {
  rows: FinancialDocument[];
  data: WorkspaceData;
  open: (id: string) => void;
  org: string;
  demo: boolean;
  route: (target: ProductView, query?: Record<string, string>) => string;
}) {
  if (!rows.length)
    return (
      <Empty title="No matching documents">
        Try another filename or status. Import supported files from the document
        workspace.
      </Empty>
    );
  return (
    <div className="p-table-scroll">
      <table className="p-table">
        <thead>
          <tr>
            <th>Document</th>
            <th>Processing</th>
            <th>Financial assessment</th>
            <th>Uploaded</th>
            <th>
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((d) => {
            const matches = linkedAssessments(data, d.id),
              source = data.sources.items.find((s) => s.document_id === d.id);
            return (
              <tr key={d.id}>
                <td>
                  <div className="p-document-name">
                    <span className="p-file-icon">
                      <ProductIcon
                        name={
                          d.document_type === "contract"
                            ? "contract"
                            : "invoice"
                        }
                      />
                    </span>
                    <span>
                      <strong>{d.original_filename}</strong>
                      <span className="p-cell-note">
                        {d.mime_type.split("/").pop()?.toUpperCase()} ·{" "}
                        {Math.max(1, Math.round(d.file_size / 1024))} KB
                      </span>
                    </span>
                  </div>
                </td>
                <td>
                  <span
                    className={`p-status ${d.processing_status === "processed" ? "success" : "warning"}`}
                  >
                    <span />
                    {d.processing_status === "processed"
                      ? "Processed"
                      : d.processing_status.replaceAll("_", " ")}
                  </span>
                </td>
                <td>
                  {matches.length ? (
                    <span>
                      {matches.length} recorded{" "}
                      {matches.length === 1 ? "assessment" : "assessments"}
                    </span>
                  ) : (
                    <span className="p-unknown">
                      {d.document_type === "contract"
                        ? "Contractual source"
                        : "No assessment linked"}
                    </span>
                  )}
                </td>
                <td className="p-date">{date(d.uploaded_at)}</td>
                <td>
                  {matches[0] ? (
                    <button
                      className="p-evidence-link"
                      onClick={() => open(matches[0].id)}
                    >
                      View finding <ProductIcon name="arrow" size={16} />
                    </button>
                  ) : !demo ? (
                    <Link
                      className="p-text-link"
                      href={`/documents/${org}/${d.id}`}
                    >
                      Review source <ProductIcon name="external" size={14} />
                    </Link>
                  ) : source?.kind === "invoice" ? (
                    <Link
                      className="p-text-link"
                      href={route("anomalies", { invoice: source.id })}
                    >
                      View assessments
                    </Link>
                  ) : (
                    <span className="p-cell-note">Synthetic source</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function AssessmentDetail({
  detail,
  data,
  orgId,
  role,
  gateway,
  demo,
  onDecision,
}: {
  detail: Assessment;
  data: WorkspaceData;
  orgId: string;
  role: string;
  gateway: WorkspaceGateway;
  demo: boolean;
  onDecision: (updated: Assessment) => void;
}) {
  const [proof, setProof] = useState<ProofDetail | null>(null),
    [proofError, setProofError] = useState("");
  const [tab, setTab] = useState<"evidence" | "history">("evidence");
  const controller = useRef<AbortController | null>(null),
    heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    const current = new AbortController();
    controller.current = current;
    heading.current?.focus();
    void gateway
      .proof(orgId, detail.id, current.signal)
      .then((result) => {
        if (!current.signal.aborted) {
          setProof(result);
          setProofError("");
        }
      })
      .catch((cause) => {
        if (!current.signal.aborted)
          setProofError(
            cause instanceof Error ? cause.message : "Proof unavailable.",
          );
      });
    return () => current.abort();
  }, [gateway, orgId, detail.id]);
  const invoice = documentFor(data, detail);
  const inputs = detail.snapshot?.inputs ?? [];
  return (
    <div className="p-detail">
      <div className="p-detail-main">
        <section className="p-card p-assessment-header">
          <div className="p-assessment-top">
            <span className="p-file-icon">
              <ProductIcon name="invoice" size={24} />
            </span>
            <div>
              <p className="p-eyebrow">ASSESSMENT · {shortId(detail.id)}</p>
              <h2 ref={heading} tabIndex={-1}>
                {detail.scope_summary?.label ?? detail.scope_key}
              </h2>
              <p>
                {invoice?.original_filename ??
                  `Invoice source ${shortId(detail.invoice_source_id)}`}
              </p>
            </div>
            <Status assessment={detail} />
          </div>
          <p className="p-explanation">{detail.explanation}</p>
          <div className="p-amount-strip">
            <div>
              <span>Contractual expectation</span>
              <strong>{money(detail.expected, detail.currency)}</strong>
            </div>
            <div>
              <span>Actual billed amount</span>
              <strong>{money(detail.actual, detail.currency)}</strong>
            </div>
            <div className="p-discrepancy">
              <span>Potential discrepancy</span>
              <strong>{money(detail.potential, detail.currency)}</strong>
            </div>
          </div>
          {detail.stale && (
            <p className="p-warning">
              The inputs changed. This is a historical assessment; obtain a new
              assessment before deciding.
            </p>
          )}
        </section>
        <ExceptionInvestigation detail={detail} data={data} demo={demo} />
        <div
          className="p-detail-tabs"
          role="tablist"
          aria-label="Assessment information"
        >
          <button
            id="evidence-tab"
            role="tab"
            aria-selected={tab === "evidence"}
            aria-controls="evidence-panel"
            onClick={() => setTab("evidence")}
          >
            Evidence & calculation
          </button>
          <button
            id="history-tab"
            role="tab"
            aria-selected={tab === "history"}
            aria-controls="history-panel"
            onClick={() => setTab("history")}
          >
            Review & audit history
          </button>
        </div>
        {tab === "evidence" ? (
          <div
            role="tabpanel"
            id="evidence-panel"
            aria-labelledby="evidence-tab"
          >
            <section className="p-card p-detail-section">
              <div className="p-section-heading">
                <h3>
                  <ProductIcon name="contract" size={18} />
                  The financial rationale
                </h3>
                <span className="p-subtle-tag">Recorded, not recalculated</span>
              </div>
              {detail.snapshot?.calculation ? (
                <div className="p-calculation">
                  <p>
                    {detail.snapshot.calculation.rules
                      .map(ruleLabel)
                      .join(" · ")}
                  </p>
                  <strong>{detail.snapshot.calculation.formula}</strong>
                  {detail.scope_summary?.quantity && (
                    <div className="p-calculation-values">
                      <span>
                        Quantity{" "}
                        <b>
                          {detail.scope_summary.quantity}{" "}
                          {detail.scope_summary.unit}
                        </b>
                      </span>
                      <span>
                        Contract rate{" "}
                        <b>
                          {money(
                            detail.scope_summary.contracted_rate,
                            detail.currency,
                          )}
                        </b>
                      </span>
                      <span>
                        Billed rate{" "}
                        <b>
                          {money(
                            detail.scope_summary.billed_rate,
                            detail.currency,
                          )}
                        </b>
                      </span>
                    </div>
                  )}
                  <details>
                    <summary>
                      Exact recorded calculation and rounding alternatives
                    </summary>
                    <pre>
                      {JSON.stringify(detail.snapshot.calculation, null, 2)}
                    </pre>
                  </details>
                </div>
              ) : (
                <div className="p-blank-copy">
                  A supported calculation is not available. Missing or uncertain
                  facts must be reviewed; an unknown amount is not zero.
                </div>
              )}
            </section>
            <section className="p-card p-detail-section">
              <div className="p-section-heading">
                <h3>
                  <ProductIcon name="shield" size={18} />
                  Source evidence & review state
                </h3>
                <span className="p-subtle-tag">
                  {inputs.length} recorded inputs
                </span>
              </div>
              {inputs.length ? (
                inputs.map((record) => (
                  <article className="p-citation" key={record.id}>
                    <div>
                      <span className="p-small-label">
                        {record.kind.replaceAll("_", " ")}
                      </span>
                      <span className="p-subtle-tag">{record.state}</span>
                    </div>
                    {record.provenance.map((e, i) => (
                      <div
                        className="p-citation-body"
                        key={`${record.id}:${i}`}
                      >
                        <strong>
                          {data.documents.items.find(
                            (d) => d.id === e.document_id,
                          )?.original_filename ??
                            `Source ${shortId(e.document_id)}`}
                        </strong>
                        <p className="p-cell-note">{e.location}</p>
                        <blockquote>{e.quote}</blockquote>
                        <dl className="p-source-values">
                          <div>
                            <dt>Raw source value</dt>
                            <dd>{e.raw_value ?? "Not recorded"}</dd>
                          </div>
                          <div>
                            <dt>Normalized candidate</dt>
                            <dd>{e.normalized_candidate ?? "Not recorded"}</dd>
                          </div>
                        </dl>
                        {e.manual && (
                          <p className="p-citation-note">
                            Reviewer-supplied citation. The quotation is not
                            machine-verified.
                          </p>
                        )}
                        {!demo && (
                          <Link
                            className="p-text-link"
                            href={`/documents/${orgId}/${e.document_id}`}
                          >
                            Inspect document & extraction{" "}
                            <ProductIcon name="external" size={14} />
                          </Link>
                        )}
                        <details>
                          <summary>Document fingerprint and lineage</summary>
                          <pre>{JSON.stringify(e, null, 2)}</pre>
                        </details>
                      </div>
                    ))}
                    <p className="p-citation-note">
                      Reviewed input {shortId(record.id)} · actor{" "}
                      {shortId(record.actor_id)} · {date(record.created_at)}
                    </p>
                    <details>
                      <summary>
                        Recorded values & uncertainty resolution
                      </summary>
                      <pre>{JSON.stringify(record.payload, null, 2)}</pre>
                    </details>
                  </article>
                ))
              ) : (
                <div className="p-blank-copy">
                  No input evidence is recorded in this assessment.
                </div>
              )}
            </section>
            <section className="p-card p-detail-section">
              <div className="p-section-heading">
                <h3>
                  <ProductIcon name="shield" size={18} />
                  Immutable proof package
                </h3>
              </div>
              {proofError ? (
                <div className="p-blank-copy">
                  <ErrorNotice message={proofError} />
                </div>
              ) : !proof ? (
                <p className="p-blank-copy" role="status">
                  Loading issued proof…
                </p>
              ) : !proof.proof ? (
                <div className="p-blank-copy">
                  No proof has been issued for this assessment. The source
                  evidence above remains available.
                  {!demo && (
                    <p>
                      <Link className="p-text-link" href="/leakage-cases">
                        Open existing proof tools to prepare a package →
                      </Link>
                    </p>
                  )}
                </div>
              ) : (
                <div className="p-proof-summary">
                  <div>
                    <span>Completeness at issue</span>
                    <strong>{proof.proof.issued_completeness}</strong>
                  </div>
                  <div>
                    <span>Financial currentness</span>
                    <strong>
                      {proof.proof.overlays.financial_currentness}
                    </strong>
                  </div>
                  <div>
                    <span>Human proof review</span>
                    <strong>{proof.proof.overlays.human_review}</strong>
                  </div>
                  <p>
                    Proof review and the financial finding decision are
                    separate. A complete proof is not a confirmed finding or
                    recovered cash.
                  </p>
                  {proof.proof.core?.limitations.map((text) => (
                    <p className="p-citation-note" key={text}>
                      {text}
                    </p>
                  ))}
                  <details>
                    <summary>
                      Read canonical proof & recorded fingerprint
                    </summary>
                    <p className="p-fingerprint">{proof.proof.fingerprint}</p>
                    <pre>{JSON.stringify(proof.proof.core, null, 2)}</pre>
                  </details>
                  {proof.hasMorePackages && (
                    <p>
                      Older packages are available in the existing proof
                      workspace.
                    </p>
                  )}
                </div>
              )}
            </section>
          </div>
        ) : (
          <section
            className="p-card p-detail-section"
            role="tabpanel"
            id="history-panel"
            aria-labelledby="history-tab"
          >
            <div className="p-section-heading">
              <h3>Attributed review history</h3>
              <span className="p-subtle-tag">Append-only evidence</span>
            </div>
            <div className="p-audit-list">
              <FinancialDecisionAudit
                gateway={gateway}
                orgId={orgId}
                detail={detail}
                demo={demo}
              />
              {inputs.map((record) => (
                <article key={record.id}>
                  <span className="p-audit-dot" />
                  <div>
                    <strong>
                      {record.kind.replaceAll("_", " ")} · {record.state}
                    </strong>
                    <p>{record.payload.reason}</p>
                    <small>
                      {date(record.created_at)} · actor{" "}
                      {shortId(record.actor_id)} · input {shortId(record.id)}
                    </small>
                  </div>
                </article>
              ))}
              {proof?.history?.items.map((event) => (
                <article key={event.id}>
                  <span className="p-audit-dot" />
                  <div>
                    <strong>{event.kind.replaceAll(".", " · ")}</strong>
                    <p>
                      {event.detail.text ??
                        event.detail.status ??
                        "Recorded proof event"}
                    </p>
                    <small>
                      {date(event.created_at)} · actor {shortId(event.actor_id)}{" "}
                      · audit {shortId(event.audit_id)}
                    </small>
                  </div>
                </article>
              ))}
              {proof?.history?.has_more && (
                <p>
                  Showing the latest 100 proof events. Open the existing proof
                  workspace for earlier history.
                </p>
              )}
              {detail.decision_id && (
                <p className="p-window-note">
                  Current finding decision ID: {detail.decision_id}. The
                  assessment endpoint supplies its status, not the decision’s
                  actor or reason; those details are not invented here.
                </p>
              )}
              {!inputs.length && !proof?.history?.items.length && (
                <p>
                  No attributed history is available in the loaded evidence.
                </p>
              )}
              {proofError && <ErrorNotice message={proofError} />}
            </div>
            <details className="p-audit-identifiers">
              <summary>Assessment fingerprint & behavior versions</summary>
              <pre>
                {JSON.stringify(
                  {
                    evaluation_id: detail.id,
                    fingerprint: detail.fingerprint,
                    compiler: detail.snapshot?.compiler,
                    rules: detail.snapshot?.rules,
                    reason_code: detail.reason_code,
                  },
                  null,
                  2,
                )}
              </pre>
            </details>
          </section>
        )}
      </div>
      <aside className="p-review-rail">
        <FinancialDecisionPanel
          detail={detail}
          orgId={orgId}
          role={role}
          gateway={gateway}
          demo={demo}
          status={<Status assessment={detail} />}
          onDecision={onDecision}
        />
        <div className="p-review-note">
          <ProductIcon name="shield" size={18} />
          <p>
            Original calculations remain immutable. Review changes the decision
            overlay, never the historical amount.
          </p>
        </div>
      </aside>
    </div>
  );
}
