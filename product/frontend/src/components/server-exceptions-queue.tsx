"use client";
import { PersonalSavedViews } from "@/components/personal-saved-views";
import { savedDefinition, type SavedDefinition } from "@/lib/saved-views";
import { readViewSearch, viewPath } from "@/lib/exception-view-url";
import {
  withoutCriterion,
  criterionAction,
  type RemovableCriterion,
  type CriteriaTransition,
} from "@/lib/criteria-removal";
import {
  AppliedCriteriaSummary,
  type AppliedCriteria,
} from "@/components/applied-criteria-summary";
import { SourceFacetSelect } from "@/components/source-facet-select";
import { cursorNeedsRestart } from "@/lib/cursor-recovery";
import { BusinessFacetSelect } from "@/components/business-facet-select";
import type { FacetOption } from "@/lib/business-facets";
import { useCallback, useEffect, useRef, useState } from "react";
import type { WorkspaceGateway } from "@/lib/product-workspace";
import { assessmentLabel } from "@/lib/product-workspace";
import { money } from "@/lib/financial";
import type { ExceptionPage, ExceptionQuery } from "@/lib/server-exceptions";

export function ServerExceptionsQueue({
  gateway,
  org,
  reviewOnly,
  invoice,
  onOpen,
  demo,
  refresh,
  initialFilters,
  initialLimit,
  onApplied,
  makeViewLink,
  organization,
  criteriaAuthorized = false,
  owner,
}: {
  gateway: WorkspaceGateway;
  org: string;
  reviewOnly: boolean;
  invoice: string;
  onOpen: (id: string) => void;
  demo: boolean;
  refresh: number;
  initialFilters?: ExceptionQuery;
  initialLimit?: number;
  onApplied?: (filters: ExceptionQuery, limit: number) => void;
  makeViewLink?: (filters: ExceptionQuery, limit: number) => string;
  organization?: string;
  criteriaAuthorized?: boolean;
  owner?: string;
}) {
  const editPending = useRef(false);
  const criteriaVersionRef = useRef(0);
  const [criteriaVersion, setCriteriaVersion] = useState(0);
  const criteriaEdited = () => {
    editPending.current = true;
    criteriaVersionRef.current += 1;
    setCriteriaVersion(criteriaVersionRef.current);
  };
  const [transition, setTransition] = useState<CriteriaTransition | null>(null);
  const [applied, setApplied] = useState<
    (AppliedCriteria & { criteriaVersion: number }) | null
  >(null);
  const sourceLabels = useRef<{
    org: string;
    invoice: FacetOption | null;
    contract: FacetOption | null;
  }>({ org, invoice: null, contract: null });
  const recordLabel = useCallback(
    (kind: "invoice" | "contract", id: string, option: FacetOption | null) => {
      if (sourceLabels.current.org !== org)
        sourceLabels.current = { org, invoice: null, contract: null };
      sourceLabels.current[kind] = option;
      setApplied((a) => {
        if (
          !a ||
          a.org !== org ||
          a.filters[
            kind === "invoice" ? "invoice_source_id" : "contract_source_id"
          ] !== id
        )
          return a;
        return {
          ...a,
          labels: {
            ...a.labels,
            [kind]: option?.label,
            ...(kind === "invoice"
              ? {
                  document:
                    option?.document_id === a.filters.invoice_document_id
                      ? option?.label
                      : undefined,
                }
              : {}),
          },
        };
      });
    },
    [org],
  );
  const invoiceLabel = useCallback(
    (id: string, option: FacetOption | null) =>
      recordLabel("invoice", id, option),
    [recordLabel],
  );
  const contractLabel = useCallback(
    (id: string, option: FacetOption | null) =>
      recordLabel("contract", id, option),
    [recordLabel],
  );
  const [filters, setFilters] = useState<ExceptionQuery>(
    initialFilters ?? {
      sort: "newest",
      needs_review: reviewOnly,
      invoice_source_id: invoice || undefined,
    },
  );
  const [invoiceChoice, setInvoiceChoice] = useState<FacetOption | null>(null);
  const [contractChoice, setContractChoice] = useState<FacetOption | null>(
    null,
  );
  const [limit, setLimit] = useState(initialLimit ?? (demo ? 2 : 20)),
    [attempt, setAttempt] = useState(0);
  const [navigation, setNavigation] = useState<{
    criteria: string;
    after: string | null;
    history: (string | null)[];
  }>({ criteria: "", after: null, history: [] });
  const [state, setState] = useState<{
    key: string;
    page: ExceptionPage;
  } | null>(null);
  const [error, setError] = useState<{ key: string; message: string } | null>(
    null,
  );
  const [copy, setCopy] = useState<{
    key: string;
    status: "pending" | "copied" | "error";
    message?: string;
  } | null>(null);
  const [recovery, setRecovery] = useState<{
    criteria: string;
    message: string;
  } | null>(null);
  const criteria = JSON.stringify([org, filters, limit, refresh]);
  const after = navigation.criteria === criteria ? navigation.after : null;
  const history = navigation.criteria === criteria ? navigation.history : [];
  const key = JSON.stringify([criteria, after, attempt]);
  const page = state?.key === key ? state.page : null;
  const failure = error?.key === key ? error.message : null;
  const loading = !page && !failure;
  useEffect(() => {
    const controller = new AbortController();
    const resultKey = key;
    const timer = setTimeout(() => {
      void gateway.queryExceptions!(
        org,
        filters,
        limit,
        after,
        controller.signal,
      )
        .then((result) => {
          if (!controller.signal.aborted) {
            setState({ key: resultKey, page: result });
            const invoiceLabel =
              sourceLabels.current.org === org &&
              sourceLabels.current.invoice?.value === filters.invoice_source_id
                ? sourceLabels.current.invoice
                : null;
            const contractLabel =
              sourceLabels.current.org === org &&
              sourceLabels.current.contract?.value ===
                filters.contract_source_id
                ? sourceLabels.current.contract
                : null;
            setApplied({
              org,
              criteriaVersion,
              filters: { ...filters },
              limit,
              labels: {
                invoice: invoiceLabel?.label,
                contract: contractLabel?.label,
                document:
                  invoiceLabel?.document_id === filters.invoice_document_id
                    ? invoiceLabel?.label
                    : undefined,
              },
            });
            editPending.current = false;
            setTransition((t) =>
              t?.org === org &&
              t.criteria === criteria &&
              t.status !== "succeeded"
                ? { ...t, status: "succeeded" }
                : t,
            );
            setError(null);
            try {
              onApplied?.(filters, limit);
            } catch {
              setRecovery({
                criteria,
                message:
                  "Criteria could not be stored in the URL. Reload will restore the last valid link.",
              });
            }
          }
        })
        .catch((cause) => {
          if (!controller.signal.aborted) {
            if (after && cursorNeedsRestart(cause)) {
              setNavigation({ criteria: "", after: null, history: [] });
              setAttempt((n) => n + 1);
              setRecovery({
                criteria,
                message:
                  "Results or cursor changed. Restarted at the first page with the same criteria.",
              });
              return;
            }
            editPending.current = false;
            setTransition((t) =>
              t?.org === org &&
              t.criteria === criteria &&
              t.status === "pending"
                ? { ...t, status: "failed" }
                : t,
            );
            setError({
              key: resultKey,
              message:
                cause instanceof Error
                  ? cause.message
                  : "Exception query unavailable.",
            });
          }
        });
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [
    gateway,
    org,
    key,
    after,
    filters,
    limit,
    onApplied,
    criteria,
    criteriaVersion,
  ]);
  const change = (patch: ExceptionQuery, replace = false) => {
    criteriaEdited();
    setTransition(null);
    setFilters((f) => (replace ? { ...patch } : { ...f, ...patch }));
    setNavigation({ criteria: "", after: null, history: [] });
  };
  const removeCriterion = (field: RemovableCriterion) => {
    if (
      !criteriaAuthorized ||
      editPending.current ||
      !page ||
      !applied ||
      applied.org !== org
    )
      return false;
    try {
      const view = reviewOnly ? "review" : "anomalies";
      const action = criterionAction(applied.filters, field, view);
      if (!action) return false;
      const next = withoutCriterion(applied.filters, field, view);
      const patch: ExceptionQuery = { [field]: next[field] };
      const requested = { ...filters, ...patch };
      change(patch);
      if (field === "invoice_source_id") setInvoiceChoice(null);
      if (field === "contract_source_id") setContractChoice(null);
      setTransition({
        org,
        criteria: JSON.stringify([org, requested, limit, refresh]),
        status: "pending",
        label: action.label,
        result: action.result,
      });
      return true;
    } catch {
      return false;
    }
  };
  const restoreApplied = () => {
    if (!criteriaAuthorized || !failure || !applied || applied.org !== org)
      return;
    change(applied.filters, true);
    setLimit(applied.limit);
    setInvoiceChoice(null);
    setContractChoice(null);
    setAttempt((n) => n + 1);
  };
  const confirmedSavedDefinition = (): SavedDefinition | null => {
    if (
      !criteriaAuthorized ||
      !owner ||
      !page ||
      failure ||
      !applied ||
      applied.org !== org ||
      applied.criteriaVersion !== criteriaVersion ||
      !makeViewLink
    )
      return null;
    try {
      const view = reviewOnly ? "review" : "anomalies";
      const path = viewPath(org, applied.filters, applied.limit, view, demo);
      const restored = readViewSearch(window.location.search, view, demo);
      if (
        window.location.pathname !== `${demo ? "/demo" : ""}/${view}` ||
        viewPath(
          restored.org || org,
          restored.filters,
          restored.limit,
          view,
          demo,
        ) !== path ||
        makeViewLink(applied.filters, applied.limit) !==
          window.location.origin + path
      )
        return null;
      return savedDefinition(
        {
          view_type: view,
          format_version: 1,
          criteria: Object.fromEntries(
            Object.entries(applied.filters).filter(
              ([, v]) => v !== undefined && v !== "",
            ),
          ),
          page_size: applied.limit,
        },
        demo,
      );
    } catch {
      return null;
    }
  };
  const currentSavedDefinition = () =>
    editPending.current ? null : confirmedSavedDefinition();
  const openSavedDefinition = (definition: SavedDefinition) => {
    if (!criteriaAuthorized || !owner) return false;
    try {
      const view = reviewOnly ? "review" : "anomalies";
      const d = savedDefinition(definition, demo);
      if (d.view_type !== view) return false;
      // Use the same V1.7 decoder and queue transition as URL restoration.
      const path = viewPath(org, d.criteria, d.page_size, view, demo);
      const restored = readViewSearch(
        path.slice(path.indexOf("?")),
        view,
        demo,
      );
      change(restored.filters, true);
      setLimit(restored.limit);
      setInvoiceChoice(null);
      setContractChoice(null);
      sourceLabels.current = { org, invoice: null, contract: null };
      setAttempt((n) => n + 1);
      return true;
    } catch {
      return false;
    }
  };
  const restart = () => {
    setNavigation({ criteria: "", after: null, history: [] });
    setAttempt((n) => n + 1);
  };
  return (
    <section
      className="p-card p-register p-server-queue"
      aria-label="Server exceptions workbench"
    >
      <div className="p-queue-heading">
        <div>
          <p className="p-eyebrow">
            {demo ? "SYNTHETIC QUERY EXERCISE" : "SERVER QUERY"}
          </p>
          <h2>
            {reviewOnly ? "Human review queue" : "Financial exceptions queue"}
          </h2>
          <p>
            {demo
              ? "Explicit in-memory query fixture; no PostgreSQL or live API."
              : "Filter the recorded dataset before counting and pagination."}
          </p>
        </div>
        <span className="p-subtle-tag">
          {demo ? "Demo only" : "Organization-scoped"}
        </span>
      </div>
      {makeViewLink && (
        <div className="p-view-sharing">
          <button
            disabled={
              !page || (copy?.key === criteria && copy.status === "pending")
            }
            onClick={async () => {
              const appliedKey = criteria;
              setCopy({ key: appliedKey, status: "pending" });
              try {
                let link: string;
                try {
                  link = makeViewLink(filters, limit);
                } catch {
                  setCopy({
                    key: appliedKey,
                    status: "error",
                    message:
                      "This view link could not be created. Check the criteria or URL length.",
                  });
                  return;
                }
                if (!navigator.clipboard?.writeText) throw Error();
                await navigator.clipboard.writeText(link);
                setCopy({ key: appliedKey, status: "copied" });
              } catch {
                setCopy({ key: appliedKey, status: "error" });
              }
            }}
          >
            Copy view link
          </button>
          {copy?.key === criteria && copy.status === "copied" && (
            <span role="status">
              View link copied. Permissions are unchanged.
            </span>
          )}
          {copy?.key === criteria && copy.status === "error" && (
            <span role="alert">
              {copy.message ??
                "The link was not copied. Clipboard access was refused or unavailable; retry Copy view link."}
            </span>
          )}
          <p>
            Links expose filter values in browser history and sharing logs. They
            grant no access and contain no saved results.
          </p>
        </div>
      )}
      {makeViewLink && organization && (
        <AppliedCriteriaSummary
          applied={applied}
          org={org}
          organization={organization}
          view={reviewOnly ? "review" : "anomalies"}
          demo={demo}
          coherent={Boolean(page)}
          failed={Boolean(failure)}
          makeViewLink={makeViewLink}
          onRemove={removeCriterion}
          canRemove={
            criteriaAuthorized &&
            !(copy?.key === criteria && copy.status === "pending")
          }
          transition={
            transition?.org === org && transition.criteria === criteria
              ? transition
              : null
          }
          onRestore={restoreApplied}
        />
      )}
      {gateway.savedViews && owner && criteriaAuthorized && (
        <PersonalSavedViews
          key={`${org}:${owner}:${reviewOnly}`}
          gateway={gateway.savedViews}
          org={org}
          owner={owner}
          view={reviewOnly ? "review" : "anomalies"}
          demo={demo}
          authorized={criteriaAuthorized}
          canSave={Boolean(confirmedSavedDefinition())}
          getCurrent={currentSavedDefinition}
          onOpen={openSavedDefinition}
          criteriaVersion={criteriaVersion}
          getCriteriaVersion={() => criteriaVersionRef.current}
          sourceLabels={{
            organization_id: org,
            user_id: owner,
            values:
              applied?.org === org
                ? Object.fromEntries(
                    [
                      [
                        "invoice_source_id",
                        applied.filters.invoice_source_id,
                        applied.labels?.invoice,
                      ],
                      [
                        "contract_source_id",
                        applied.filters.contract_source_id,
                        applied.labels?.contract,
                      ],
                      [
                        "invoice_document_id",
                        applied.filters.invoice_document_id,
                        applied.labels?.document,
                      ],
                    ]
                      .filter(([, id, label]) => id && label)
                      .map(([field, id, label]) => [
                        `${field}:${id}`,
                        label as string,
                      ]),
                  )
                : {},
          }}
        />
      )}
      {recovery?.criteria === criteria && (
        <p className="p-view-notice" role="status">
          {recovery.message}
        </p>
      )}
      <div className="p-server-filters">
        <label className="p-server-search">
          Search recorded values
          <input
            aria-label="Search server records"
            maxLength={160}
            value={filters.q ?? ""}
            placeholder="Scope, explanation, supplier or contract reference…"
            onChange={(e) => change({ q: e.target.value })}
          />
        </label>
        <label>
          Outcome
          <select
            aria-label="Server outcome"
            value={filters.outcome ?? ""}
            onChange={(e) => change({ outcome: e.target.value })}
          >
            <option value="">All outcomes</option>
            {[
              "POTENTIAL_LEAKAGE",
              "NEEDS_REVIEW",
              "NO_OVERCHARGE",
              "UNDERCHARGE",
            ].map((value) => (
              <option key={value}>{value}</option>
            ))}
          </select>
        </label>
        <label>
          Last recorded decision
          <select
            aria-label="Recorded decision filter"
            value={filters.decision_status ?? ""}
            onChange={(e) => change({ decision_status: e.target.value })}
          >
            <option value="">All decisions</option>
            <option value="confirmed">Confirmed</option>
            <option value="false_positive">Dismissed</option>
            <option value="needs_review">Further review requested</option>
            <option value="unrecorded">No recorded decision</option>
          </select>
        </label>
        <label>
          Order
          <select
            aria-label="Server sort"
            value={filters.sort}
            onChange={(e) => change({ sort: e.target.value })}
          >
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="amount_high">
              Potential high–low within currency
            </option>
            <option value="amount_low">
              Potential low–high within currency
            </option>
            <option value="outcome">Outcome A–Z</option>
          </select>
        </label>
        <label>
          Currency (ISO)
          <input
            aria-label="Server currency"
            placeholder="e.g. USD"
            maxLength={3}
            value={filters.currency ?? ""}
            onChange={(e) => change({ currency: e.target.value.toUpperCase() })}
          />
        </label>
        {gateway.queryFacets ? (
          <BusinessFacetSelect
            key={`${org}-supplier`}
            gateway={gateway}
            org={org}
            filters={filters}
            facet="supplier"
            selected={
              filters.supplier
                ? { value: filters.supplier, label: filters.supplier }
                : null
            }
            onSelect={(option) => {
              change({
                supplier: option?.value,
                contract_source_id: undefined,
              });
              setContractChoice(null);
            }}
            demo={demo}
            refresh={refresh}
          />
        ) : (
          <label>
            Supplier party
            <input
              aria-label="Server supplier"
              maxLength={120}
              value={filters.supplier ?? ""}
              onChange={(e) => change({ supplier: e.target.value })}
            />
          </label>
        )}
        {gateway.queryFacets ? (
          <SourceFacetSelect
            key={`${org}-invoice`}
            id={filters.invoice_source_id}
            onLabel={invoiceLabel}
            gateway={gateway}
            org={org}
            filters={filters}
            facet="invoice"
            selected={
              filters.invoice_source_id
                ? (invoiceChoice ??
                  (page?.items.find(
                    (row) =>
                      row.invoice_source_id === filters.invoice_source_id,
                  )?.invoice_filename
                    ? {
                        value: filters.invoice_source_id,
                        document_id:
                          page.items.find(
                            (row) =>
                              row.invoice_source_id ===
                              filters.invoice_source_id,
                          )?.invoice_document_id ?? undefined,
                        label: page.items.find(
                          (row) =>
                            row.invoice_source_id === filters.invoice_source_id,
                        )!.invoice_filename!,
                      }
                    : null))
                : null
            }
            onSelect={(option) => {
              setInvoiceChoice(option);
              change({ invoice_source_id: option?.value });
            }}
            demo={demo}
            refresh={refresh}
          />
        ) : (
          <label>
            Invoice source ID
            <input
              aria-label="Server invoice source"
              maxLength={36}
              value={filters.invoice_source_id ?? ""}
              onChange={(e) => change({ invoice_source_id: e.target.value })}
            />
          </label>
        )}
        {gateway.queryFacets ? (
          <SourceFacetSelect
            key={`${org}-contract`}
            id={filters.contract_source_id}
            onLabel={contractLabel}
            gateway={gateway}
            org={org}
            filters={filters}
            facet="contract"
            selected={filters.contract_source_id ? contractChoice : null}
            onSelect={(option) => {
              setContractChoice(option);
              change({
                contract_source_id: option?.value,
                missing_contract: option ? false : filters.missing_contract,
              });
            }}
            demo={demo}
            refresh={refresh}
          />
        ) : (
          <label>
            Approved contract source ID
            <input
              aria-label="Server contract source"
              maxLength={36}
              value={filters.contract_source_id ?? ""}
              onChange={(e) =>
                change({
                  contract_source_id: e.target.value,
                  missing_contract: false,
                })
              }
            />
          </label>
        )}
        <label>
          Created on/after (UTC)
          <input
            aria-label="Created on or after"
            type="date"
            value={filters.created_from?.slice(0, 10) ?? ""}
            onChange={(e) =>
              change({
                created_from: e.target.value
                  ? `${e.target.value}T00:00:00Z`
                  : undefined,
              })
            }
          />
        </label>
        <label>
          Created before (UTC)
          <input
            aria-label="Created before"
            type="date"
            value={filters.created_to?.slice(0, 10) ?? ""}
            onChange={(e) =>
              change({
                created_to: e.target.value
                  ? `${e.target.value}T00:00:00Z`
                  : undefined,
              })
            }
          />
        </label>
        <label>
          Page size
          <select
            aria-label="Server page size"
            value={limit}
            onChange={(e) => {
              criteriaEdited();
              setLimit(Number(e.target.value));
              setNavigation({ criteria: "", after: null, history: [] });
            }}
          >
            {(demo ? [2, 20, 50, 100] : [20, 50, 100]).map((n) => (
              <option key={n}>{n}</option>
            ))}
          </select>
        </label>
        <button
          onClick={() => {
            criteriaEdited();
            setInvoiceChoice(null);
            setContractChoice(null);
            setFilters({
              sort: "newest",
              needs_review: reviewOnly,
              invoice_source_id: invoice || undefined,
            });
            restart();
          }}
        >
          Reset criteria
        </button>
        <div className="p-server-flags">
          <label>
            <input
              type="checkbox"
              checked={filters.current ?? false}
              onChange={(e) => change({ current: e.target.checked })}
            />
            Current assessments only
          </label>
          <label>
            <input
              type="checkbox"
              checked={filters.needs_review ?? false}
              onChange={(e) => change({ needs_review: e.target.checked })}
            />
            Needs human review
          </label>
          <label>
            <input
              type="checkbox"
              checked={filters.missing_contract ?? false}
              onChange={(e) =>
                change({
                  missing_contract: e.target.checked,
                  contract_source_id: undefined,
                })
              }
            />
            No unique association returned
          </label>
        </div>
        {filters.invoice_document_id && (
          <p className="p-server-scope">
            Invoice document constraint:{" "}
            {page?.items.find(
              (row) => row.invoice_document_id === filters.invoice_document_id,
            )?.invoice_filename ?? "label unavailable under current criteria"}
            .{" "}
            <button onClick={() => change({ invoice_document_id: undefined })}>
              Clear invoice document constraint
            </button>
          </p>
        )}
        {(filters.created_from || filters.created_to) && (
          <p className="p-server-scope">
            UTC period criteria: {filters.created_from ?? "unbounded start"} →{" "}
            {filters.created_to ?? "unbounded end"} (exclusive end).
          </p>
        )}
        <p className="p-server-scope">
          Supplier changes clear the contract selection; choosing a contract
          does not approve an association. Recorded decision filters describe
          history, not currentness. Currentness/review filters require at most
          100 SQL candidates; narrow other criteria first. Amounts remain
          grouped by currency, with unknown amounts last.
        </p>
      </div>
      {loading ? (
        <div className="p-loading" role="status">
          Loading filtered exceptions…
        </div>
      ) : failure ? (
        <div className="p-error" role="alert">
          <div>
            <strong>Exception query unavailable</strong>
            <p>{failure}</p>
          </div>
          <button onClick={() => setAttempt((n) => n + 1)}>
            Retry this page
          </button>
          <button onClick={restart}>Restart query</button>
        </div>
      ) : (
        page && (
          <>
            <div className="p-query-counts" role="status">
              <strong>
                {page.total_exact
                  ? `${page.total} matching assessments`
                  : "Exact total unavailable"}
              </strong>
              <span>
                {page.items.length} loaded on this page ·{" "}
                {page.items.length
                  ? `${page.offset + 1}–${page.offset + page.items.length}`
                  : "0"}
                {page.total_exact ? ` of ${page.total}` : ""} ·{" "}
                {page.has_more ? "More results available" : "End of results"}
              </span>
            </div>
            {page.items.length ? (
              <div className="p-table-scroll">
                <table className="p-table">
                  <thead>
                    <tr>
                      <th>Invoice & scope</th>
                      <th>Supplier & contract</th>
                      <th>Recorded potential</th>
                      <th>Review state</th>
                      <th>Created</th>
                      <th>Evidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {page.items.map((row) => (
                      <tr key={row.id}>
                        <td>
                          <button
                            className="p-row-link"
                            onClick={() => onOpen(row.id)}
                          >
                            {row.invoice_filename ??
                              `Invoice source ${row.invoice_source_id}`}
                          </button>
                          <span className="p-cell-note">
                            {row.scope_summary?.label ?? row.scope_key}
                          </span>
                        </td>
                        <td className="p-reference-cell">
                          <strong>
                            {row.queue_context?.supplier_party ??
                              "Supplier not returned"}
                          </strong>
                          <span className="p-cell-note">
                            {row.contract_filename ??
                              row.queue_context?.contract_source_id ??
                              "No unique association returned"}
                          </span>
                        </td>
                        <td className="p-money">
                          {money(row.potential, row.currency)}
                          {row.stale && (
                            <span className="p-cell-note">
                              Historical amount
                            </span>
                          )}
                        </td>
                        <td>
                          <span className="p-status">
                            {assessmentLabel(row)}
                          </span>
                          <span className="p-cell-note">{row.outcome}</span>
                        </td>
                        <td>
                          <time dateTime={row.created_at}>
                            {row.created_at.slice(0, 10)}
                          </time>
                        </td>
                        <td>
                          <button
                            className="p-evidence-link"
                            aria-label={`Investigate ${row.id}`}
                            onClick={() => onOpen(row.id)}
                          >
                            Investigate →
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-empty">
                <h3>No matching exceptions</h3>
                <p>
                  Change the criteria. An empty query does not prove the
                  organization has no financial leakage.
                </p>
              </div>
            )}
            <nav className="p-queue-pagination" aria-label="Server pagination">
              <button
                disabled={!history.length}
                onClick={() =>
                  setNavigation({
                    criteria,
                    after: history.at(-1) ?? null,
                    history: history.slice(0, -1),
                  })
                }
              >
                Previous page
              </button>
              <button
                disabled={!page.has_more || !page.next_cursor}
                onClick={() => {
                  setNavigation({
                    criteria,
                    after: page.next_cursor,
                    history: [...history, after],
                  });
                }}
              >
                Next page
              </button>
              <button onClick={restart}>Restart query</button>
            </nav>
            <p className="p-server-scope">
              {page.consistency} {page.coverage} No financial totals are
              recalculated from this page.
            </p>
          </>
        )
      )}
    </section>
  );
}
