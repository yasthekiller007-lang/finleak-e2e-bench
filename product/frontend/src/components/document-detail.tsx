"use client";

import Link from "next/link";
import { SourceAvailability } from "@/components/source-availability";
import { useCallback, useEffect, useRef, useState } from "react";
import type { FinancialDocument, MembershipRole } from "@/lib/documents";
import { fieldLabel, statusLabels, warningLabel } from "@/lib/intelligence";
import type { ExtractionRun } from "@/lib/intelligence";

async function readResponse<T>(response: Response): Promise<T> {
  const body = await response.json();
  if (!response.ok)
    throw new Error(body.error?.message ?? "Unable to load this document.");
  return body as T;
}
function showValue(value: string | boolean | null) {
  return value === null
    ? "Unknown"
    : typeof value === "boolean"
      ? value
        ? "Yes"
        : "No"
      : value;
}
export function DocumentDetail({
  organizationId,
  documentId,
  role,
}: {
  organizationId: string;
  documentId: string;
  role: MembershipRole;
}) {
  const base = `/api/organizations/${organizationId}/documents/${documentId}`;
  const [document, setDocument] = useState<FinancialDocument | null>(null);
  const [loadedBase, setLoadedBase] = useState("");
  const [run, setRun] = useState<ExtractionRun | null>(null);
  const [history, setHistory] = useState<ExtractionRun[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [availability, setAvailability] = useState<{
    base: string;
    released: boolean;
  } | null>(null);
  const available = availability?.base === base && availability.released;
  const reportAvailability = useCallback(
    (released: boolean) => setAvailability({ base, released }),
    [base],
  );
  const key = useRef<string | null>(null);
  const load = useCallback(
    async (signal?: AbortSignal) => {
      const [metadata, extraction, runs] = await Promise.all([
        fetch(base, { cache: "no-store", signal }).then(
          readResponse<FinancialDocument>,
        ),
        fetch(`${base}/extraction`, { cache: "no-store", signal }).then(
          readResponse<{ run: ExtractionRun | null }>,
        ),
        fetch(`${base}/extraction-runs?limit=100`, {
          cache: "no-store",
          signal,
        }).then(readResponse<{ items: ExtractionRun[] }>),
      ]);
      if (!signal?.aborted) {
        setDocument(metadata);
        setLoadedBase(base);
        setRun(extraction.run);
        setHistory(runs.items);
        setError("");
      }
    },
    [base],
  );
  useEffect(() => {
    const controller = new AbortController();
    Promise.resolve()
      .then(() => load(controller.signal))
      .catch((cause) => {
        if (!controller.signal.aborted)
          setError(
            cause instanceof Error ? cause.message : "Unable to load document.",
          );
      });
    return () => controller.abort();
  }, [load]);
  async function process() {
    if (busy || !available) return;
    setBusy(true);
    setError("");
    key.current ??= crypto.randomUUID();
    try {
      const response = await fetch(
        `${base}/${history.length ? "reprocess" : "process"}`,
        {
          method: "POST",
          headers: { "Idempotency-Key": key.current },
        },
      );
      await readResponse<{ run: ExtractionRun }>(response);
      key.current = null;
      await load();
    } catch (cause) {
      reportAvailability(false);
      setError(cause instanceof Error ? cause.message : "Processing failed.");
    } finally {
      setBusy(false);
    }
  }
  async function selectRun(id: string) {
    setBusy(true);
    try {
      const result = await fetch(`${base}/extraction-runs/${id}`, {
        cache: "no-store",
      }).then(readResponse<{ run: ExtractionRun }>);
      setRun(result.run);
      setError("");
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Unable to load version.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Link className="text-link" href="/documents">
        Back to documents
      </Link>
      {error && (
        <div role="alert" className="error-notice">
          {error}
        </div>
      )}
      {!document || loadedBase !== base ? (
        <p role="status">
          {error ? "Document unavailable." : "Loading document…"}
        </p>
      ) : (
        <>
          <SourceAvailability
            key={base}
            base={base}
            role={role}
            onAvailability={reportAvailability}
          />
          <section className="card settings-card">
            <h1>{document.original_filename}</h1>
            <p className="muted">
              {document.document_type.replaceAll("_", " ")} · Uploaded{" "}
              {new Date(document.uploaded_at).toLocaleDateString()}
            </p>
            <p role="status">
              {busy ? "Working…" : statusLabels[document.processing_status]}
            </p>
            <p>
              Extracted values are proposals for review. Unknown values need
              source clarification.
            </p>
            <div className="document-actions">
              {role !== "viewer" && (
                <button
                  className="button"
                  disabled={busy || !available}
                  onClick={process}
                >
                  {history.length ? "Process again" : "Process document"}
                </button>
              )}
              <button
                disabled={busy}
                onClick={() => {
                  setBusy(true);
                  load()
                    .catch((cause) =>
                      setError(
                        cause instanceof Error
                          ? cause.message
                          : "Refresh failed.",
                      ),
                    )
                    .finally(() => setBusy(false));
                }}
              >
                Refresh
              </button>
              <a
                className="text-link"
                aria-disabled={!available}
                href={available ? `${base}/content` : undefined}
              >
                Download original
              </a>
            </div>
          </section>
          {run && (
            <>
              <section className="card settings-card">
                <h2>Review extracted data</h2>
                <p>
                  Version {run.version_number} · {statusLabels[run.status]}
                </p>
                {run.error_message && <p role="alert">{run.error_message}</p>}
                {run.status === "needs_ocr" && (
                  <p>
                    Text recognition is needed. No values were invented for
                    image-only content.
                  </p>
                )}
                {run.warnings.length > 0 && (
                  <details open>
                    <summary>Review notes ({run.warnings.length})</summary>
                    <ul>
                      {run.warnings.map((warning) => (
                        <li key={warning}>{warningLabel(warning)}</li>
                      ))}
                    </ul>
                  </details>
                )}
                {Object.entries(run.structured).map(([section, content]) => (
                  <details
                    key={section}
                    className="extraction-section"
                    open={section === "identity" || section === "totals"}
                  >
                    <summary>{fieldLabel(section)}</summary>
                    {(Array.isArray(content) ? content : [content]).map(
                      (values, index) => (
                        <div key={index}>
                          {Array.isArray(content) && (
                            <h3>
                              {section === "lines" ? "Line" : "Pricing entry"}{" "}
                              {index + 1}
                            </h3>
                          )}
                          <dl className="candidate-summary">
                            {Object.entries(values).map(([name, value]) => (
                              <div key={name}>
                                <dt>{fieldLabel(name)}</dt>
                                <dd>{showValue(value)}</dd>
                              </div>
                            ))}
                          </dl>
                        </div>
                      ),
                    )}
                    {Array.isArray(content) && content.length === 0 && (
                      <p className="muted">No entries extracted.</p>
                    )}
                  </details>
                ))}
              </section>
              <section className="card settings-card">
                <h2>Source evidence</h2>
                {run.fields.length === 0 ? (
                  <p>No supported facts have source evidence yet.</p>
                ) : (
                  run.fields.map((field) => (
                    <details key={field.id} className="extraction-section">
                      <summary>
                        {fieldLabel(field.path)}:{" "}
                        {showValue(field.normalized_value)} ·{" "}
                        {field.confidence === "low"
                          ? "Needs review"
                          : "Explicit source"}
                      </summary>
                      <p>
                        <strong>Raw value:</strong> {field.raw_value}
                      </p>
                      <p>
                        <strong>Normalized value:</strong>{" "}
                        {showValue(field.normalized_value)}
                      </p>
                      <p>
                        {field.source.page
                          ? `Page ${field.source.page} · `
                          : ""}
                        {field.source.sheet
                          ? `Sheet ${field.source.sheet} · `
                          : ""}
                        {field.source.cell
                          ? `Cell ${field.source.cell} · `
                          : ""}
                        {field.source.row
                          ? `Row ${field.source.row} · Column ${field.source.header ?? field.source.column}`
                          : ""}
                        {field.source.line ? `Line ${field.source.line}` : ""}
                      </p>
                      {field.source.text && (
                        <blockquote>{field.source.text}</blockquote>
                      )}
                      <p className="muted">
                        {field.reason === "conflicting_sources"
                          ? "Sources disagree; no value was selected."
                          : field.normalized_value === null
                            ? "The source value could not be normalized safely."
                            : "An explicit label identifies this value."}
                      </p>
                      <a
                        className="text-link"
                        aria-disabled={!available}
                        href={available ? `${base}/content` : undefined}
                      >
                        Open original source
                      </a>
                    </details>
                  ))
                )}
              </section>
            </>
          )}
          <section className="card settings-card">
            <h2>Processing history</h2>
            {history.length === 0 ? (
              <p>This document has not been processed yet.</p>
            ) : (
              <ul>
                {history.map((item) => (
                  <li key={item.id}>
                    <button
                      className="history-button"
                      disabled={busy}
                      onClick={() => selectRun(item.id)}
                    >
                      Version {item.version_number}
                    </button>{" "}
                    · {statusLabels[item.status]} ·{" "}
                    {new Date(item.created_at).toLocaleString()}
                    {item.id === run?.id && " · Viewing"}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </>
  );
}
