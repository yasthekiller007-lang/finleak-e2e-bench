"use client";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ComponentProps,
} from "react";
import { SavedViewCriteriaDiff } from "@/components/saved-view-criteria-diff";
import { SavedViewReconciliation } from "@/components/saved-view-reconciliation";
import {
  replacementAttempt,
  renameAttempt,
  isRenameAttempt,
  reconcileSavedRename,
  viewDefinition,
  reconcileSavedReplacement,
  unavailableReconciliation,
  type SavedViewAttempt,
  type ReplacementIssue,
  type ReconciliationResult,
} from "@/lib/saved-view-reconciliation";
import {
  compareSavedCriteria,
  definitionKey,
  type CriteriaComparison,
  type SourceLabels,
} from "@/lib/saved-view-diff";
import { criteriaLines } from "@/lib/applied-criteria-summary";
import type { ExceptionView } from "@/lib/exception-view-url";
import {
  parseSavedView,
  savedDefinition,
  savedName,
  type SavedDefinition,
  type SavedPage,
  type SavedView,
  type SavedViewsGateway,
} from "@/lib/saved-views";

function ScopedSavedViews({
  gateway,
  org,
  owner,
  view,
  demo,
  authorized,
  canSave,
  getCurrent,
  onOpen,
  criteriaVersion = 0,
  getCriteriaVersion,
  sourceLabels,
}: {
  gateway: SavedViewsGateway;
  org: string;
  owner: string;
  view: ExceptionView;
  demo: boolean;
  authorized: boolean;
  canSave: boolean;
  getCurrent: () => SavedDefinition | null;
  onOpen: (definition: SavedDefinition) => boolean;
  criteriaVersion?: number;
  getCriteriaVersion?: () => number;
  sourceLabels?: SourceLabels;
}) {
  const [search, setSearch] = useState(""),
    [after, setAfter] = useState<string | null>(null),
    [refresh, setRefresh] = useState(0);
  const [list, setList] = useState<{ key: string; page: SavedPage } | null>(
      null,
    ),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [selected, setSelected] = useState<SavedView | null>(null),
    [draft, setDraft] = useState(""),
    [createName, setCreateName] = useState("");
  const [creating, setCreating] = useState(false),
    [confirm, setConfirm] = useState<"update" | "delete" | null>(null);
  const [busy, setBusy] = useState(false),
    [blocked, setBlocked] = useState(false),
    [listError, setListError] = useState("");
  const [review, setReview] = useState<{
    org: string;
    owner: string;
    saved: SavedView;
    comparison: CriteriaComparison;
    epoch: number;
    invalid?: string;
    versionChanged?: number;
    labels?: SourceLabels;
  } | null>(null);
  const updateTrigger = useRef<HTMLButtonElement>(null);
  const active = useRef<AbortController | null>(null),
    writing = useRef(false),
    heading = useRef<HTMLHeadingElement>(null);
  const [attempt, setAttempt] = useState<SavedViewAttempt | null>(null),
    [reconciliation, setReconciliation] = useState<ReconciliationResult | null>(
      null,
    ),
    [summaryOpen, setSummaryOpen] = useState(false),
    [checkingState, setCheckingState] = useState(false),
    [accessDenied, setAccessDenied] = useState(false);
  const [renameReview, setRenameReview] = useState<{
    saved: SavedView;
    name: string;
  } | null>(null);
  const renameHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (renameReview && !busy) renameHeading.current?.focus();
  }, [renameReview, busy]);
  const denied = useRef(false),
    readSequence = useRef(0),
    attemptSequence = useRef(0),
    checking = useRef(false),
    reconciliationRead = useRef<AbortController | null>(null),
    readTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const allowed = authorized && !accessDenied;
  const cancelRead = useCallback(() => {
    readSequence.current++;
    reconciliationRead.current?.abort();
    if (readTimer.current) clearTimeout(readTimer.current);
    checking.current = false;
    setCheckingState(false);
  }, []);
  const revokeAccess = useCallback(() => {
    denied.current = true;
    setAccessDenied(true);
    cancelRead();
    active.current?.abort();
    writing.current = false;
    setBusy(false);
    setSelected(null);
    setList(null);
    setReview(null);
    setRenameReview(null);
    setAttempt(null);
    setReconciliation(null);
    setSummaryOpen(false);
    setConfirm(null);
    setDraft("");
    setCreateName("");
    setCreating(false);
    setSearch("");
    setNotice("");
    setListError("");
    setBlocked(true);
    setError(
      "Organization access is unavailable. Reconciliation was stopped and private view context cleared.",
    );
  }, [cancelRead, setRenameReview]);
  const version = () => getCriteriaVersion?.() ?? criteriaVersion;
  const listKey = JSON.stringify([
    org,
    owner,
    view,
    search,
    after,
    refresh,
    authorized,
  ]);
  const page = allowed && list?.key === listKey ? list.page : null;
  useEffect(
    () => () => {
      active.current?.abort();
      reconciliationRead.current?.abort();
      if (readTimer.current) clearTimeout(readTimer.current);
    },
    [],
  );
  useEffect(() => {
    const controller = new AbortController();
    if (!allowed) return () => controller.abort();
    const timer = setTimeout(() => {
      void gateway
        .list(org, owner, view, search, after, controller.signal)
        .then((value) => {
          if (controller.signal.aborted || denied.current) return;
          const items = value.items.map((i) =>
            parseSavedView(i, org, owner, demo),
          );
          if (items.some((i) => i.view_type !== view))
            throw Error("Personal views returned an incompatible type.");
          setList({ key: listKey, page: { ...value, items } });
          setListError("");
        })
        .catch((e) => {
          if (
            !controller.signal.aborted &&
            (e?.status === 401 || e?.status === 403)
          ) {
            revokeAccess();
            return;
          }
          if (!controller.signal.aborted)
            setListError(
              "Personal views could not be loaded. Retry this read.",
            );
        });
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [
    gateway,
    org,
    owner,
    view,
    search,
    after,
    refresh,
    authorized,
    allowed,
    revokeAccess,
    listKey,
    demo,
  ]);
  const checked = (row: SavedView, id?: string) => {
    const value = parseSavedView(row, org, owner, demo);
    if (value.view_type !== view || (id && value.id !== id))
      throw Error("Personal view unavailable. No search was started.");
    return value;
  };
  const run = async (
    task: (signal: AbortSignal) => Promise<void>,
    write = false,
  ) => {
    if (!authorized || denied.current || writing.current) return;
    writing.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    const controller = new AbortController();
    active.current?.abort();
    active.current = controller;
    try {
      await task(controller.signal);
    } catch (e) {
      if (!controller.signal.aborted) {
        const status =
          typeof e === "object" && e && "status" in e ? Number(e.status) : null;
        if (status === 401 || status === 403) {
          revokeAccess();
          return;
        }
        const message =
          e instanceof Error ? e.message : "Personal view request failed.";
        setError(
          status === 409
            ? `${message} Your draft is retained. Re-read the selected view before another write.`
            : message,
        );
        if (write) {
          setBlocked(true);
          setReview((r) =>
            r
              ? {
                  ...r,
                  invalid:
                    status === 409
                      ? "Version conflict. This comparison is outdated. Re-read and review again; your proposed criteria are retained."
                      : "The replacement outcome is unconfirmed. Re-read the view before another review; no write is replayed.",
                }
              : r,
          );
        }
      }
    } finally {
      if (!controller.signal.aborted) {
        writing.current = false;
        setBusy(false);
      }
    }
  };
  const reload = () => {
    cancelRead();
    setRenameReview(null);
    setReconciliation(null);
    void run(async (signal) => {
      setReview((r) =>
        r
          ? {
              ...r,
              invalid:
                "The saved view was re-read. Build a new comparison before replacement.",
            }
          : r,
      );
      if (selected) {
        try {
          const row = checked(
            await gateway.get(org, owner, selected.id, signal),
            selected.id,
          );
          if (signal.aborted) return;
          setSelected(row);
        } catch (e) {
          if (signal.aborted) return;
          if (typeof e === "object" && e && "status" in e && e.status === 404)
            setSelected(null);
          else throw e;
        }
      }
      const result = await gateway.list(org, owner, view, search, null, signal);
      if (signal.aborted) return;
      const items = result.items.map((i) => checked(i));
      setAfter(null);
      setRefresh((n) => n + 1);
      setList(null);
      setBlocked(false);
      setListError("");
      setNotice(
        `Personal views re-read (${items.length} on the first page). Your name draft is retained; review before writing.`,
      );
    });
  };
  const choose = (row: SavedView, open: boolean) => {
    cancelRead();
    setRenameReview(null);
    setAttempt(null);
    setReconciliation(null);
    setSummaryOpen(false);
    void run(async (signal) => {
      const fresh = checked(
        await gateway.get(org, owner, row.id, signal),
        row.id,
      );
      if (signal.aborted) return;
      setSelected(fresh);
      setDraft(fresh.name);
      setConfirm(null);
      setReview(null);
      setBlocked(false);
      if (open) {
        const definition = savedDefinition(
          {
            view_type: fresh.view_type,
            format_version: fresh.format_version,
            criteria: fresh.criteria,
            page_size: fresh.page_size,
          },
          demo,
        );
        if (!onOpen(definition))
          throw Error(
            "View could not be opened in the current authorized context.",
          );
        setNotice(
          "Saved criteria requested. Consult the queue for the fresh search result; saved financial results are never restored.",
        );
        heading.current?.focus();
      }
    });
  };
  const beginReview = () => {
    if (!selected || !allowed || !canSave || busy) return;
    if (reconciliation?.kind === "RECONCILIATION_UNAVAILABLE") return;
    const proposed = getCurrent();
    if (!proposed) return;
    const picked = checked(selected),
      epoch = version();
    const target = savedDefinition(proposed, demo);
    setRenameReview(null);
    cancelRead();
    setSummaryOpen(false);
    setConfirm("update");
    setReview(null);
    void run(async (signal) => {
      const fresh = checked(
        await gateway.get(org, owner, picked.id, signal),
        picked.id,
      );
      if (signal.aborted) return;
      setSelected(fresh);
      const comparison = compareSavedCriteria(
        {
          view_type: fresh.view_type,
          format_version: fresh.format_version,
          criteria: fresh.criteria,
          page_size: fresh.page_size,
        },
        target,
        demo,
      );
      const now = getCurrent();
      const invalid =
        version() !== epoch ||
        !now ||
        definitionKey(now, demo) !== definitionKey(target, demo)
          ? "The applied criteria changed while the saved view was being read. Review the latest criteria again."
          : undefined;
      const labels =
        sourceLabels?.organization_id === org && sourceLabels.user_id === owner
          ? { ...sourceLabels, values: { ...sourceLabels.values } }
          : undefined;
      setReview({
        org,
        owner,
        saved: fresh,
        comparison,
        epoch,
        invalid,
        versionChanged:
          fresh.revision !== picked.revision ? picked.revision : undefined,
        labels,
      });
      setBlocked(false);
    });
  };
  const reviewValid = Boolean(
    review &&
    !review.invalid &&
    !blocked &&
    authorized &&
    canSave &&
    review.org === org &&
    review.owner === owner &&
    review.epoch === criteriaVersion &&
    selected?.id === review.saved.id &&
    selected?.revision === review.saved.revision,
  );
  const confirmReplacement = () => {
    if (!review || !reviewValid || !review.comparison.hasChanges) return;
    const current = getCurrent();
    if (
      !current ||
      version() !== review.epoch ||
      definitionKey(current, demo) !==
        definitionKey(review.comparison.current, demo)
    ) {
      setReview({
        ...review,
        invalid:
          "The applied criteria no longer match the displayed replacement. Review again.",
      });
      return;
    }
    void run(async (signal) => {
      const context = replacementAttempt(
        review.saved,
        review.comparison.current,
        org,
        owner,
        `local-${++attemptSequence.current}`,
        demo,
      );
      setAttempt(context);
      setReconciliation(null);
      setSummaryOpen(false);
      let responseReceived = false;
      try {
        const raw = await gateway.update(
          org,
          owner,
          review.saved.id,
          review.saved.revision,
          { definition: context.proposed },
          signal,
        );
        responseReceived = true;
        const row = checked(raw, review.saved.id);
        if (signal.aborted) return;
        const result = {
          view_type: row.view_type,
          format_version: row.format_version,
          criteria: row.criteria,
          page_size: row.page_size,
        };
        if (
          row.revision !== review.saved.revision + 1 ||
          definitionKey(result, demo) !==
            definitionKey(review.comparison.current, demo)
        )
          throw Error(
            "The response did not confirm the displayed replacement. Re-read the view; the outcome is unconfirmed.",
          );
        setSelected(row);
        setAttempt(null);
        setReconciliation(null);
        setSummaryOpen(false);
        setReview(null);
        setConfirm(null);
        setRefresh((n) => n + 1);
        setNotice(
          demo
            ? "Synthetic criteria updated in memory only."
            : "Saved criteria updated by the backend.",
        );
        heading.current?.focus();
      } catch (e) {
        if (!signal.aborted && !denied.current) {
          const status =
            typeof e === "object" && e && "status" in e
              ? Number(e.status)
              : null;
          const issue: ReplacementIssue =
            status === 409
              ? "CONFLICT"
              : status
                ? "HTTP_ERROR"
                : responseReceived
                  ? "RESPONSE_UNVERIFIED"
                  : e instanceof Error && e.name === "TimeoutError"
                    ? "TIMEOUT"
                    : "NETWORK_ERROR";
          setAttempt({ ...context, issue });
          setSummaryOpen(true);
        }
        throw e;
      }
    }, true);
  };
  const checkSavedState = () => {
    if (
      !allowed ||
      denied.current ||
      !attempt ||
      writing.current ||
      checking.current
    )
      return;
    const controller = new AbortController(),
      sequence = ++readSequence.current;
    reconciliationRead.current?.abort();
    reconciliationRead.current = controller;
    checking.current = true;
    setCheckingState(true);
    setSummaryOpen(true);
    setReconciliation(null);
    setBlocked(true);
    setError("");
    setNotice("");
    readTimer.current = setTimeout(() => {
      if (sequence !== readSequence.current || denied.current) return;
      controller.abort();
      readSequence.current++;
      checking.current = false;
      setCheckingState(false);
      setReconciliation(unavailableReconciliation("TIMEOUT"));
    }, 30000);
    void gateway
      .get(org, owner, attempt.before.id, controller.signal)
      .then((raw) => {
        if (
          controller.signal.aborted ||
          denied.current ||
          sequence !== readSequence.current
        )
          return;
        const result = isRenameAttempt(attempt)
          ? reconcileSavedRename(
              attempt.before,
              attempt.proposed_name,
              raw,
              org,
              owner,
              demo,
            )
          : reconcileSavedReplacement(
              attempt.before,
              attempt.proposed,
              raw,
              org,
              owner,
              demo,
            );
        setReconciliation(result);
        if (result.kind !== "RECONCILIATION_UNAVAILABLE")
          setSelected(checked(raw, attempt.before.id));
      })
      .catch((e) => {
        if (
          controller.signal.aborted ||
          denied.current ||
          sequence !== readSequence.current
        )
          return;
        if (e?.status === 401 || e?.status === 403) {
          revokeAccess();
          return;
        }
        setReconciliation(
          unavailableReconciliation(
            e?.status === 404 ? "NOT_FOUND" : "READ_FAILED",
          ),
        );
      })
      .finally(() => {
        if (sequence !== readSequence.current) return;
        if (readTimer.current) clearTimeout(readTimer.current);
        checking.current = false;
        setCheckingState(false);
      });
  };
  const closeSummary = () => {
    if (checking.current)
      setReconciliation(unavailableReconciliation("CANCELLED"));
    cancelRead();
    setSummaryOpen(false);
    heading.current?.focus();
  };
  const beginRenameReview = () => {
    if (
      !allowed ||
      !selected ||
      busy ||
      reconciliation?.kind === "RECONCILIATION_UNAVAILABLE"
    )
      return;
    let name: string;
    try {
      name = savedName(draft);
    } catch (e) {
      setError((e as Error).message);
      return;
    }
    cancelRead();
    setSummaryOpen(false);
    setRenameReview(null);
    setConfirm(null);
    setReview(null);
    const id = selected.id;
    void run(async (signal) => {
      const fresh = checked(await gateway.get(org, owner, id, signal), id);
      if (signal.aborted) return;
      setSelected(fresh);
      setBlocked(false);
      setRenameReview({ saved: fresh, name });
    });
  };
  const submitRename = (before: SavedView, proposed: string) => {
    if (!allowed || busy || blocked || denied.current) return;
    let name: string;
    try {
      name = savedName(proposed);
    } catch (e) {
      setError((e as Error).message);
      return;
    }
    if (name === before.name) {
      setNotice("No name changes to save");
      setError("");
      return;
    }
    void run(async (signal) => {
      const context = renameAttempt(
        checked(before),
        name,
        org,
        owner,
        `local-${++attemptSequence.current}`,
        demo,
      );
      setAttempt(context);
      setReconciliation(null);
      setSummaryOpen(false);
      let received = false;
      try {
        const raw = await gateway.update(
          org,
          owner,
          context.before.id,
          context.before.revision,
          { name: context.proposed_name },
          signal,
        );
        received = true;
        const row = checked(raw, context.before.id);
        if (signal.aborted) return;
        if (
          row.revision !== context.before.revision + 1 ||
          row.name !== context.proposed_name ||
          definitionKey(viewDefinition(row), demo) !==
            definitionKey(viewDefinition(context.before), demo)
        )
          throw Error(
            "The response did not confirm the name-only rename. Re-read the view; the outcome is unconfirmed.",
          );
        setSelected(row);
        setDraft(row.name);
        setAttempt(null);
        setRenameReview(null);
        setReconciliation(null);
        setSummaryOpen(false);
        setRefresh((n) => n + 1);
        setNotice(
          demo
            ? "Synthetic view renamed in memory only."
            : "Personal view renamed by the backend.",
        );
        heading.current?.focus();
      } catch (e) {
        if (!signal.aborted && !denied.current) {
          const status =
            typeof e === "object" && e && "status" in e
              ? Number(e.status)
              : null;
          const issue: ReplacementIssue =
            status === 409
              ? "CONFLICT"
              : status
                ? "HTTP_ERROR"
                : received
                  ? "RESPONSE_UNVERIFIED"
                  : e instanceof Error && e.name === "TimeoutError"
                    ? "TIMEOUT"
                    : "NETWORK_ERROR";
          setAttempt({ ...context, issue });
          setRenameReview(null);
          setSummaryOpen(true);
        }
        throw e;
      }
    }, true);
  };
  const confirmRename = () => {
    if (!renameReview || !selected || blocked || busy || !allowed) return;
    let currentName: string;
    try {
      currentName = savedName(draft);
    } catch {
      return;
    }
    if (
      renameReview.saved.id !== selected.id ||
      renameReview.saved.revision !== selected.revision ||
      currentName !== renameReview.name ||
      definitionKey(viewDefinition(selected), demo) !==
        definitionKey(viewDefinition(renameReview.saved), demo)
    ) {
      setRenameReview(null);
      setBlocked(true);
      setError(
        "The rename review is outdated. Re-read and review the rename again.",
      );
      return;
    }
    submitRename(renameReview.saved, renameReview.name);
  };
  const cancelReview = () => {
    setConfirm(null);
    setReview(null);
    // A pending financial read can disable the original trigger during review.
    if (updateTrigger.current && !updateTrigger.current.disabled)
      updateTrigger.current.focus();
    else heading.current?.focus();
  };
  const summary = (row: SavedView) =>
    criteriaLines(
      row.criteria,
      row.page_size,
      row.view_type,
      { organization: "Current organization" },
      demo,
    )
      .filter((l) => l.name !== "Organization")
      .map((l) => `${l.name}: ${l.value}`)
      .join(" · ");
  return (
    <section className="p-saved-views" aria-label="My saved views">
      <div className="p-saved-heading">
        <div>
          <h3 ref={heading} tabIndex={-1}>
            My saved views
          </h3>
          <p>
            {demo
              ? "Synthetic personal views in memory only. No database persistence; reset when this demo is recreated."
              : "Private to your account in this organization. Criteria only, never financial results."}
          </p>
        </div>
        <button
          disabled={!allowed || !canSave || busy || blocked}
          onClick={() => {
            if (getCurrent()) {
              setCreating(true);
              setError("");
              setNotice("");
            }
          }}
        >
          Save current view
        </button>
      </div>
      <p className="p-saved-caveat">
        {view === "review" ? "Human review" : "Anomalies"} views · Maximum 50
        per user and organization across both types. Opening a view reads
        current data and restarts at page one. Sources are never substituted.
      </p>
      <p className="p-saved-caveat">
        Attempt context is kept in memory only. After a page reload, attribution
        of a prior operation is unavailable.
      </p>
      {creating && (
        <form
          aria-label="Name personal view"
          onSubmit={(e) => {
            e.preventDefault();
            const definition = getCurrent();
            if (!definition || blocked) return;
            let name: string;
            try {
              name = savedName(createName);
            } catch (err) {
              setError((err as Error).message);
              return;
            }
            void run(async (signal) => {
              const row = checked(
                await gateway.create(org, owner, name, definition, signal),
              );
              if (signal.aborted) return;
              setSelected(row);
              setDraft(row.name);
              setCreating(false);
              setCreateName("");
              setAfter(null);
              setRefresh((n) => n + 1);
              setNotice(
                demo
                  ? "Synthetic view saved in this demo only. No PostgreSQL persistence."
                  : "Personal view saved by the backend. Financial results were not stored.",
              );
            }, true);
          }}
        >
          <label>
            View name
            <input
              aria-label="New saved view name"
              value={createName}
              maxLength={160}
              onChange={(e) => setCreateName(e.target.value)}
              autoFocus
            />
          </label>
          <button disabled={!allowed || !canSave || busy || blocked}>
            Save named view
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => setCreating(false)}
          >
            Cancel save
          </button>
        </form>
      )}
      <div className="p-saved-tools">
        <label>
          Find personal views
          <input
            aria-label="Find personal views"
            maxLength={80}
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setAfter(null);
              setListError("");
            }}
          />
        </label>
        <button disabled={!allowed || busy || checkingState} onClick={reload}>
          Reload personal views
        </button>
      </div>
      {!allowed ? (
        <p role="alert">
          Organization access is unavailable. Personal views cannot be read or
          changed.
        </p>
      ) : !page && !listError ? (
        <p role="status">Loading personal views…</p>
      ) : null}
      {listError && (
        <p role="alert">
          {listError}{" "}
          <button
            disabled={busy}
            onClick={() => {
              setListError("");
              setRefresh((n) => n + 1);
            }}
          >
            Retry personal views
          </button>
        </p>
      )}
      {page && (
        <>
          <ul className="p-saved-list">
            {page.items.map((row) => (
              <li key={row.id}>
                <div>
                  <strong>{row.name}</strong>
                  <span>
                    {row.view_type === "review" ? "Human review" : "Anomalies"}{" "}
                    · version {row.revision}
                  </span>
                  <p>{summary(row)}</p>
                </div>
                <div>
                  <button
                    disabled={!authorized || busy}
                    onClick={() => choose(row, true)}
                    aria-label={`Open saved view ${row.name}`}
                  >
                    Open view
                  </button>
                  <button
                    disabled={!authorized || busy}
                    onClick={() => choose(row, false)}
                    aria-label={`Manage saved view ${row.name}`}
                  >
                    Manage
                  </button>
                </div>
              </li>
            ))}
          </ul>
          {!page.items.length && (
            <p>
              No personal views match this search. Save an applied search to
              begin.
            </p>
          )}
          <div className="p-saved-paging">
            <button
              disabled={!after || busy}
              onClick={() => {
                setAfter(null);
                setListError("");
              }}
            >
              First saved views page
            </button>
            <button
              disabled={!page.has_more || busy}
              onClick={() => {
                setAfter(page.next_after);
                setListError("");
              }}
            >
              More saved views
            </button>
          </div>
        </>
      )}
      {allowed && selected && (
        <fieldset
          className="p-saved-manage"
          disabled={!allowed || busy || checkingState}
        >
          <legend>Manage personal view: {selected.name}</legend>
          <p>
            Server version {selected.revision}. A rename keeps the saved
            criteria. Updating criteria is a separate action.
          </p>
          <label>
            New name
            <input
              aria-label="Rename personal view"
              maxLength={160}
              value={draft}
              onChange={(e) => {
                setDraft(e.target.value);
                setRenameReview(null);
              }}
            />
          </label>
          <button
            disabled={blocked || Boolean(renameReview)}
            onClick={() =>
              isRenameAttempt(attempt)
                ? beginRenameReview()
                : submitRename(selected, draft)
            }
          >
            Rename view
          </button>
          {isRenameAttempt(attempt) && !renameReview && !summaryOpen && (
            <button
              disabled={reconciliation?.kind === "RECONCILIATION_UNAVAILABLE"}
              onClick={beginRenameReview}
            >
              Review rename again
            </button>
          )}
          {renameReview && (
            <section
              className="p-saved-confirm"
              aria-label="Review saved view rename"
            >
              <h4 ref={renameHeading} tabIndex={-1}>
                Review saved view rename
              </h4>
              <p>
                Current saved name: <strong>{renameReview.saved.name}</strong>
              </p>
              <p>
                Proposed new name: <strong>{renameReview.name}</strong>
              </p>
              <p>
                Re-read version {renameReview.saved.revision}. This name-only
                request preserves the criteria read at this version. A later
                change will require another review.
              </p>
              {renameReview.saved.name === renameReview.name && (
                <p role="status">No name changes to save</p>
              )}
              <button
                disabled={
                  blocked || renameReview.saved.name === renameReview.name
                }
                onClick={confirmRename}
              >
                Confirm rename
              </button>
              <button
                onClick={() => {
                  setRenameReview(null);
                  heading.current?.focus();
                }}
              >
                Cancel rename review
              </button>
            </section>
          )}
          <button
            ref={updateTrigger}
            disabled={!canSave || blocked}
            onClick={beginReview}
          >
            Update saved criteria
          </button>
          <button
            disabled={blocked}
            onClick={() => {
              setRenameReview(null);
              setReview(null);
              setConfirm("delete");
            }}
          >
            Delete personal view
          </button>
          {confirm === "update" &&
            (review ? (
              <SavedViewCriteriaDiff
                name={review.saved.name}
                revision={review.saved.revision}
                comparison={review.comparison}
                valid={reviewValid}
                busy={busy}
                reason={review.invalid}
                versionChanged={review.versionChanged}
                labels={review.labels}
                demo={demo}
                onConfirm={confirmReplacement}
                onCancel={cancelReview}
                onReview={beginReview}
                reviewAvailable={
                  reconciliation?.kind !== "RECONCILIATION_UNAVAILABLE"
                }
              />
            ) : (
              <div className="p-saved-confirm" role="status">
                <h4>Review saved view changes</h4>
                <p>
                  {busy
                    ? "Reading the current saved view before comparison…"
                    : "Comparison unavailable. Re-read the view to review changes."}
                </p>
                {!busy && (
                  <button onClick={beginReview} disabled={!canSave}>
                    Review changes again
                  </button>
                )}
                <button disabled={busy} onClick={cancelReview}>
                  Cancel
                </button>
              </div>
            ))}
          {confirm === "delete" && (
            <div
              className="p-saved-confirm"
              role="group"
              aria-label="Confirm personal view deletion"
            >
              <p>
                Delete only this personal view? Invoices, contracts, evidence
                and financial decisions are preserved.
              </p>
              <button
                disabled={blocked}
                onClick={() =>
                  void run(async (signal) => {
                    await gateway.remove(
                      org,
                      owner,
                      selected.id,
                      selected.revision,
                      signal,
                    );
                    if (signal.aborted) return;
                    setSelected(null);
                    setConfirm(null);
                    setReview(null);
                    setRefresh((n) => n + 1);
                    setNotice(
                      demo
                        ? "Synthetic personal view removed from memory only."
                        : "Personal view deleted by the backend.",
                    );
                  }, true)
                }
              >
                Confirm delete personal view
              </button>
              <button onClick={() => setConfirm(null)}>Cancel change</button>
            </div>
          )}
        </fieldset>
      )}
      {allowed &&
        attempt &&
        attempt.issue !== "RESPONSE_PENDING" &&
        (summaryOpen ? (
          <SavedViewReconciliation
            attempt={attempt}
            result={reconciliation}
            checking={checkingState}
            canReview={
              (isRenameAttempt(attempt) || canSave) &&
              !busy &&
              Boolean(selected) &&
              reconciliation?.kind !== "RECONCILIATION_UNAVAILABLE"
            }
            onCheck={checkSavedState}
            onReview={
              isRenameAttempt(attempt) ? beginRenameReview : beginReview
            }
            onClose={closeSummary}
          />
        ) : (
          <p className="p-view-notice">
            {isRenameAttempt(attempt)
              ? "The last rename response remains unconfirmed."
              : "The last replacement response remains unconfirmed."}{" "}
            <button disabled={busy} onClick={checkSavedState}>
              {isRenameAttempt(attempt)
                ? "Check rename state"
                : "Check saved view state"}
            </button>
          </p>
        ))}
      {error && (
        <p className="p-error" role="alert">
          {error}
          {blocked &&
            " No automatic write retry. Reload personal views before another write."}
        </p>
      )}
      {notice && (
        <p className="p-view-notice" role="status">
          {notice}
        </p>
      )}
    </section>
  );
}

export function PersonalSavedViews(
  props: ComponentProps<typeof ScopedSavedViews>,
) {
  return (
    <ScopedSavedViews
      key={`${props.org}:${props.owner}:${props.view}:${props.authorized}`}
      {...props}
    />
  );
}
