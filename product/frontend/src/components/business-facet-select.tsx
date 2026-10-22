"use client";
import { cursorNeedsRestart } from "@/lib/cursor-recovery";
import { useEffect, useId, useState } from "react";
import type { WorkspaceGateway } from "@/lib/product-workspace";
import type { ExceptionQuery } from "@/lib/server-exceptions";
import {
  facetContext,
  type FacetKind,
  type FacetOption,
  type FacetPage,
} from "@/lib/business-facets";

/** Search text never becomes a filter until a returned option is explicitly selected. */
export function BusinessFacetSelect({
  gateway,
  org,
  filters,
  facet,
  selected,
  onSelect,
  demo,
  refresh,
}: {
  gateway: WorkspaceGateway;
  org: string;
  filters: ExceptionQuery;
  facet: FacetKind;
  selected: FacetOption | null;
  onSelect: (value: FacetOption | null) => void;
  demo: boolean;
  refresh: number;
}) {
  const id = useId(),
    label =
      facet === "supplier"
        ? "Supplier"
        : facet === "invoice"
          ? "Invoice"
          : "Approved contract";
  const plural =
    facet === "supplier"
      ? "suppliers"
      : facet === "invoice"
        ? "invoices"
        : "approved contracts";
  const [open, setOpen] = useState(false),
    [search, setSearch] = useState("");
  const [notice, setNotice] = useState<{
    context: string;
    message: string;
  } | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [navigation, setNavigation] = useState<{
    context: string;
    after: string | null;
    previous: (string | null)[];
  }>({ context: "", after: null, previous: [] });
  const context = JSON.stringify([
    org,
    facetContext(filters, facet),
    facet,
    search,
    refresh,
  ]);
  const after = navigation.context === context ? navigation.after : null;
  const previous = navigation.context === context ? navigation.previous : [];
  const key = JSON.stringify([context, after, attempt]);
  const [state, setState] = useState<{
    key: string;
    page?: FacetPage;
    error?: string;
  } | null>(null);
  const [active, setActive] = useState<{ key: string; index: number }>({
    key: "",
    index: 0,
  });
  const page = state?.key === key ? state.page : undefined;
  const error = state?.key === key ? state.error : undefined;
  const items = page?.items ?? [];
  const activeIndex =
    active.key === key
      ? Math.min(active.index, Math.max(0, items.length - 1))
      : 0;
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      void gateway.queryFacets!(
        org,
        filters,
        facet,
        search,
        demo ? 2 : 20,
        after,
        controller.signal,
      )
        .then((result) => {
          if (!controller.signal.aborted) setState({ key, page: result });
        })
        .catch((cause) => {
          if (!controller.signal.aborted) {
            if (after && cursorNeedsRestart(cause, true)) {
              setNavigation({ context: "", after: null, previous: [] });
              setAttempt((n) => n + 1);
              setNotice({
                context,
                message:
                  "Choices or cursor changed. Restarted the choices with the same criteria.",
              });
              return;
            }
            setState({
              key,
              error:
                cause instanceof Error ? cause.message : "Choices unavailable.",
            });
          }
        });
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [gateway, org, filters, facet, search, demo, after, key, open, context]);
  const choose = (option: FacetOption) => {
    onSelect(option);
    setOpen(false);
    setSearch("");
  };
  const restart = () => {
    setNavigation({ context: "", after: null, previous: [] });
    setAttempt((n) => n + 1);
  };
  return (
    <div
      className={`p-business-facet${facet === "invoice" ? " p-business-facet-invoice" : ""}`}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null))
          setOpen(false);
      }}
    >
      <label htmlFor={id}>{label}</label>
      <div className="p-facet-input">
        <input
          id={id}
          role="combobox"
          aria-label={
            facet === "supplier"
              ? "Search suppliers"
              : facet === "invoice"
                ? "Search invoices"
                : "Search approved contracts"
          }
          aria-expanded={open}
          aria-controls={`${id}-list`}
          aria-autocomplete="list"
          aria-activedescendant={
            open && items.length ? `${id}-option-${activeIndex}` : undefined
          }
          autoComplete="off"
          maxLength={120}
          value={open ? search : (selected?.label ?? "")}
          placeholder={
            selected
              ? selected.label
              : facet === "supplier"
                ? "Find a recorded supplier…"
                : facet === "invoice"
                  ? "Find an invoice document…"
                  : "Reference or document name…"
          }
          onFocus={() => {
            setSearch("");
            setOpen(true);
            setAttempt((n) => n + 1);
          }}
          onClick={() => {
            if (!open) {
              setSearch("");
              setOpen(true);
              setAttempt((n) => n + 1);
            }
          }}
          onChange={(event) => {
            setSearch(event.target.value);
            setOpen(true);
          }}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              setOpen(false);
              event.preventDefault();
            }
            if (event.key === "ArrowDown" || event.key === "ArrowUp") {
              event.preventDefault();
              setOpen(true);
              setActive({
                key,
                index: items.length
                  ? (activeIndex +
                      (event.key === "ArrowDown" ? 1 : -1) +
                      items.length) %
                    items.length
                  : 0,
              });
            }
            if (open && event.key === "Enter" && items[activeIndex]) {
              event.preventDefault();
              choose(items[activeIndex]);
            }
            if (
              open &&
              (event.key === "Home" || event.key === "End") &&
              items.length
            ) {
              event.preventDefault();
              setActive({
                key,
                index: event.key === "Home" ? 0 : items.length - 1,
              });
            }
          }}
        />
        {selected && (
          <button
            type="button"
            aria-label={`Clear ${label.toLowerCase()}`}
            onClick={() => {
              onSelect(null);
              setSearch("");
            }}
          >
            ×
          </button>
        )}
      </div>
      {selected && (
        <span className="p-facet-selected">
          Selected: {selected.label}
          {facet !== "supplier" && selected.description
            ? ` · ${selected.description}`
            : ""}
        </span>
      )}
      {open && (
        <div className="p-facet-popover">
          {notice?.context === context && <p role="status">{notice.message}</p>}
          {!page && !error && <p role="status">Searching {plural}…</p>}
          {error && (
            <div role="alert">
              <p>{error}</p>
              <button type="button" onClick={() => setAttempt((n) => n + 1)}>
                Retry choices
              </button>
              <button type="button" onClick={restart}>
                Restart choices
              </button>
            </div>
          )}
          <ul id={`${id}-list`} role="listbox" aria-label={`${label} choices`}>
            {items.map((option, index) => (
              <li
                key={option.value}
                id={`${id}-option-${index}`}
                role="option"
                aria-selected={selected?.value === option.value}
                className={index === activeIndex ? "p-facet-active" : ""}
                onMouseEnter={() => setActive({ key, index })}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => choose(option)}
              >
                <strong>{option.label}</strong>
                {option.description && <span>{option.description}</span>}
                {facet === "invoice" && option.date && (
                  <span>
                    {option.date_type === "reviewed_invoice_date"
                      ? "Reviewed invoice date"
                      : "Reviewed source created"}
                    : {option.date}
                  </span>
                )}
                {option.effective_from && (
                  <span>
                    Contract period: {option.effective_from} →{" "}
                    {option.effective_to ?? "end not returned"} (exclusive end)
                  </span>
                )}
              </li>
            ))}
          </ul>
          {page && !items.length && (
            <p>
              No matching {facet === "supplier" ? "supplier strings" : plural}{" "}
              for these criteria.
            </p>
          )}
          {page && (
            <div className="p-facet-navigation">
              <button
                type="button"
                disabled={!previous.length}
                onClick={() =>
                  setNavigation({
                    context,
                    after: previous.at(-1) ?? null,
                    previous: previous.slice(0, -1),
                  })
                }
              >
                Previous choices
              </button>
              <button
                type="button"
                disabled={!page.has_more || !page.next_cursor}
                onClick={() =>
                  setNavigation({
                    context,
                    after: page.next_cursor,
                    previous: [...previous, after],
                  })
                }
              >
                More choices
              </button>
            </div>
          )}
          <small>
            {facet === "supplier"
              ? "Exact snapshot strings, not verified legal identities. Case and spacing remain distinct."
              : facet === "invoice"
                ? "Reviewed invoice sources only. Filenames are document labels, not verified invoice numbers. Document constraints remain active."
                : "Only unique approved associations in matching evaluations. Stable source order; labels may change with newer snapshots."}{" "}
            Current/review criteria retain the 100-candidate limit.
          </small>
        </div>
      )}
    </div>
  );
}
