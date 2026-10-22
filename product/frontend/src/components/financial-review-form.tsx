"use client";
import { useState } from "react";
import type { FinancialDocument } from "@/lib/documents";
import { evidencePaths } from "@/lib/financial";
import type { SourceDetail, Source } from "@/lib/financial";

function field(name: string, label: string, required = false, type = "text") {
  return (
    <label key={name}>
      {label}
      <input name={name} required={required} type={type} />
    </label>
  );
}
function check(name: string, label: string) {
  return (
    <label key={name}>
      <input name={name} type="checkbox" /> {label}
    </label>
  );
}
function list(value: string) {
  return value
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);
}

export function FinancialReviewForm({
  source,
  sources,
  documents,
  onSave,
}: {
  source: SourceDetail;
  sources: Source[];
  documents: FinancialDocument[];
  onSave: (body: unknown) => Promise<void>;
}) {
  const [kind, setKind] = useState(
    source.kind === "contract" ? "term" : "billing_scope",
  );
  const [family, setFamily] = useState("unit_price");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const text = (name: string) => String(data.get(name) ?? "").trim();
    const nullable = (name: string) => text(name) || null;
    const checked = (name: string) => data.get(name) === "on";
    let value: Record<string, unknown>;
    const key =
      kind === "term" || kind === "billing_scope" ? text("key") : kind;
    if (kind === "term")
      value = {
        key,
        supplier_party: nullable("supplier_party"),
        customer_party: nullable("customer_party"),
        scope: text("scope"),
        family,
        pricing_type:
          family === "unit_price"
            ? "fixed_unit"
            : family === "fixed_fee"
              ? text("fee_basis")
              : "unconditional_percentage",
        currency: nullable("currency"),
        unit: nullable("unit"),
        rate: nullable("rate"),
        percentage: nullable("percentage"),
        discount_base: family === "percentage_discount" ? "line" : null,
        unconditional:
          family === "percentage_discount" ? checked("unconditional") : null,
        eligible_members: [],
        effective_from: nullable("effective_from"),
        effective_to: nullable("effective_to"),
        open_ended: checked("open_ended"),
        date_basis: text("date_basis"),
        invoice_date_fallback: checked("invoice_date_fallback"),
        full_cycle: nullable("cycle"),
        supersedes: list(text("supersedes")),
        retroactive: checked("retroactive"),
        retroactive_applicability_approved: checked("retroactive_approved"),
        tax_basis: text("tax_basis"),
        rounding: nullable("quantum")
          ? {
              quantum: text("quantum"),
              modes: [text("rounding_mode")],
              stage: "scope",
              alternatives_complete: checked("rounding_complete"),
              justification: text("rounding_reason"),
              metadata_version: text("rounding_version"),
            }
          : null,
        unresolved: list(text("unresolved")),
      };
    else if (kind === "billing_scope")
      value = {
        key,
        supplier_party: nullable("supplier_party"),
        customer_party: nullable("customer_party"),
        label: text("label"),
        members: list(text("members")),
        scope: text("scope"),
        currency: nullable("currency"),
        unit: nullable("unit"),
        quantity: nullable("quantity"),
        billed_rate: nullable("billed_rate"),
        billed_gross: nullable("billed_gross"),
        posted_amount: nullable("posted_amount"),
        billed_discount: nullable("billed_discount"),
        tax_basis: text("tax_basis"),
        service_from: nullable("service_from"),
        service_to: nullable("service_to"),
        invoice_date: nullable("invoice_date"),
        event_date: nullable("event_date"),
        cycle: nullable("cycle"),
        complete_cycle: checked("complete_cycle"),
        base_components: nullable("contractual_base")
          ? [
              {
                key: text("members"),
                contractual_gross: text("contractual_base"),
                billed_gross: null,
                billed_discount: null,
                posted_amount: null,
                eligible: true,
              },
            ]
          : [],
        base_complete: checked("base_complete"),
        credits: nullable("credit_amount")
          ? [
              {
                key: text("credit_key"),
                scope: key,
                amount: text("credit_amount"),
                classification: "credit",
                within_invoice: checked("within_invoice"),
              },
            ]
          : [],
        contract_references: list(text("contract_references")),
        po_references: list(text("po_references")),
        date_conflict: checked("date_conflict"),
        unresolved: list(text("unresolved")),
        allocation_parent: nullable("allocation_parent"),
      };
    else if (kind === "packet")
      value = {
        documents: [
          { document_id: source.document_id, role: "master" },
          ...documents
            .filter(
              (d) => d.id !== source.document_id && checked(`include_${d.id}`),
            )
            .map((d) => ({ document_id: d.id, role: text(`role_${d.id}`) })),
        ],
        scopes: list(text("scopes")),
        effective_from: nullable("effective_from"),
        effective_to: nullable("effective_to"),
        open_ended: checked("open_ended"),
        known_missing: list(text("known_missing")),
        complete: checked("complete"),
        attestation: text("attestation"),
        unresolved: list(text("unresolved")),
      };
    else if (kind === "association")
      value = {
        contract_source_id: text("contract_source_id"),
        method: text("method"),
        identifier: nullable("identifier"),
        rationale: text("rationale"),
      };
    else
      value = {
        contract_reference: nullable("contract_reference"),
        po_reference: nullable("po_reference"),
      };
    const previous = source.reviews.find(
      (r) => r.kind === kind && r.key === key,
    );
    setBusy(true);
    setError("");
    try {
      await onSave({
        kind,
        key,
        state: "prepared",
        expected_revision: previous?.id ?? null,
        reason: text("reason"),
        uncertainty_resolution: text("resolution"),
        knowledge_cutoff: new Date().toISOString(),
        value,
        evidence: [
          ...(kind === "billing_scope" && nullable("contractual_base")
            ? [
                {
                  document_id: text("base_document"),
                  location: text("base_location"),
                  quote: text("base_quote"),
                  field_id: null,
                  manual: true,
                  supports: evidencePaths(value).filter((p) =>
                    p.startsWith("/base_components/"),
                  ),
                },
              ]
            : []),
          {
            document_id: text("evidence_document") || source.document_id,
            location: text("location"),
            quote: text("quote"),
            field_id: null,
            manual: true,
            supports: evidencePaths(value).filter(
              (p) =>
                !(kind === "billing_scope" && nullable("contractual_base")) ||
                !p.startsWith("/base_components/"),
            ),
          },
        ],
      });
      form.reset();
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Review could not be saved.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit} className="financial-form">
      <h3>Prepare source review</h3>
      <p className="muted">
        Record only source-supported meanings. Blank amounts remain unknown.
        Preparation does not approve financial truth.
      </p>
      <label>
        Review type
        <select value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value={source.kind === "contract" ? "term" : "billing_scope"}>
            {source.kind === "contract" ? "Contractual term" : "Billed scope"}
          </option>
          <option value="reference">Contract / purchase order reference</option>
          {source.kind === "contract" ? (
            <option value="packet">Governing documents</option>
          ) : (
            <option value="association">Governing contract association</option>
          )}
        </select>
      </label>
      {(kind === "term" || kind === "billing_scope") && (
        <>
          {field("key", "Source term / billing line identifier", true)}
          {field("scope", "Contractual subject / SKU", true)}
          {field("supplier_party", "Reviewed supplier identity")}
          {field("customer_party", "Reviewed customer identity")}
          {field("currency", "Explicit currency code")}
          {field("unit", "Explicit unit")}
        </>
      )}
      {kind === "term" && (
        <>
          <label>
            Pricing family
            <select value={family} onChange={(e) => setFamily(e.target.value)}>
              <option value="unit_price">Fixed unit price</option>
              <option value="fixed_fee">Fixed full-cycle fee</option>
              <option value="percentage_discount">
                Unconditional percentage discount
              </option>
            </select>
          </label>
          {family === "percentage_discount" ? (
            <>
              {field("percentage", "Discount percentage")}
              {check(
                "unconditional",
                "Source establishes an unconditional percentage on this line",
              )}
            </>
          ) : (
            field("rate", "Contracted price / fee")
          )}
          {field("cycle", "Contractual cycle / event identifier (fixed fee)")}
          {family === "fixed_fee" && (
            <label>
              Fixed fee basis
              <select name="fee_basis">
                <option value="fixed_cycle">One full contractual cycle</option>
                <option value="fixed_event">
                  One explicit contractual event
                </option>
              </select>
            </label>
          )}
          {field(
            "supersedes",
            "Explicitly replaced term keys, separated by commas",
          )}
          {check("retroactive", "Amendment is explicitly retroactive")}
          {check(
            "retroactive_approved",
            "Retroactive applicability has been established for review",
          )}
          <label>
            Contractual pricing date
            <select name="date_basis">
              <option value="service">Service date</option>
              <option value="invoice">Explicit contractual invoice date</option>
              <option value="event">Contractual event date</option>
            </select>
          </label>
          {check(
            "invoice_date_fallback",
            "Source expressly permits invoice date fallback",
          )}
          {field("quantum", "Monetary rounding quantum (for example 0.01)")}
          <label>
            Source rounding mode
            <select name="rounding_mode">
              <option value="ROUND_HALF_UP">Half up</option>
              <option value="ROUND_HALF_EVEN">Half even</option>
              <option value="ROUND_DOWN">Toward zero</option>
              <option value="ROUND_UP">Away from zero</option>
            </select>
          </label>
          {field("rounding_reason", "Source supporting rounding")}
          {field(
            "rounding_version",
            "Reviewed currency / rounding profile version",
          )}
          {check(
            "rounding_complete",
            "The rounding mode, quantum and scope stage are established",
          )}
        </>
      )}
      {(kind === "term" || kind === "packet") && (
        <>
          {field("effective_from", "Explicit effective start", false, "date")}
          {field("effective_to", "Exclusive effective end", false, "date")}
          {check(
            "open_ended",
            "Reviewed wording establishes an open-ended period",
          )}
        </>
      )}
      {(kind === "term" || kind === "billing_scope") && (
        <label>
          Reviewed pre-tax basis
          <select name="tax_basis">
            <option value="unknown">Unknown</option>
            <option value="exclusive">Explicit tax-exclusive amount</option>
            <option value="separable">Explicit separated pre-tax amount</option>
          </select>
        </label>
      )}
      {kind === "billing_scope" && (
        <>
          {field("label", "Scope description", true)}
          {field(
            "members",
            "Exact covered line identifiers, separated by commas",
            true,
          )}
          {field("quantity", "Billed quantity")}
          {field("billed_rate", "Billed unit price")}
          {field("billed_gross", "Evidenced billed gross (before discount)")}
          {field(
            "posted_amount",
            "Posted pre-tax amount (after discount, before credit)",
          )}
          {field(
            "billed_discount",
            "Explicit billed discount amount, including evidenced zero",
          )}
          {field(
            "service_from",
            "Service date / interval start",
            false,
            "date",
          )}
          {field("service_to", "Exclusive interval end", false, "date")}
          {field("invoice_date", "Invoice date", false, "date")}
          {field("event_date", "Contractual event date", false, "date")}
          {field("cycle", "Contractual cycle identifier")}
          {check(
            "complete_cycle",
            "Source establishes one complete contractual cycle",
          )}
          {field(
            "contractual_base",
            "Approved contractual gross for a one-line discount base",
          )}
          {check(
            "base_complete",
            "Eligible base is complete and source-supported",
          )}
          <label>
            Contractual base supporting document
            <select name="base_document">
              <option value="">Select governing evidence</option>
              {documents
                .filter((d) => d.document_type === "contract")
                .map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.original_filename}
                  </option>
                ))}
            </select>
          </label>
          {field("base_location", "Contractual base source location")}
          <label>
            Contractual base quotation
            <textarea name="base_quote" />
          </label>
          {field("credit_key", "Unique credit identifier")}
          {field("credit_amount", "Signed allocated credit amount")}
          {check(
            "within_invoice",
            "Credit explicitly belongs to this scope on this invoice",
          )}
          {field(
            "contract_references",
            "Explicit contract references, separated by commas",
          )}
          {field(
            "po_references",
            "Explicit purchase order references, separated by commas",
          )}
          {field(
            "allocation_parent",
            "Explicit parent allocation identifier, if split",
          )}
          {check("date_conflict", "Economic dates are conflicting")}
        </>
      )}
      {kind === "packet" && (
        <>
          {field(
            "scopes",
            "Covered contractual subjects / SKUs, separated by commas",
            true,
          )}
          {field(
            "known_missing",
            "Known relevant missing documents, separated by commas",
          )}
          {field("attestation", "Bounded coverage attestation", true)}
          {documents
            .filter((d) => d.id !== source.document_id)
            .map((d) => (
              <div key={d.id}>
                {check(`include_${d.id}`, d.original_filename)}
                <label>
                  Document role
                  <select name={`role_${d.id}`}>
                    <option value="amendment">Amendment</option>
                    <option value="schedule">Schedule</option>
                    <option value="exhibit">Exhibit</option>
                    <option value="exception">Authorized exception</option>
                  </select>
                </label>
              </div>
            ))}
          {check(
            "complete",
            "I reviewed the governing packet for this scope and period",
          )}
        </>
      )}
      {kind === "association" && (
        <>
          <label>
            One governing master
            <select name="contract_source_id" required>
              <option value="">Select reviewed contract</option>
              {sources
                .filter((s) => s.kind === "contract")
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {documents.find((d) => d.id === s.document_id)
                      ?.original_filename ?? s.id}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Source relationship
            <select name="method">
              <option value="manual">Source-backed reviewed association</option>
              <option value="exact_reference">
                Exact approved contract reference
              </option>
              <option value="approved_po">Approved purchase order link</option>
            </select>
          </label>
          {field("identifier", "Exact reference / purchase order identifier")}
          {field("rationale", "Source supporting this association", true)}
        </>
      )}
      {kind === "reference" && (
        <>
          {field("contract_reference", "Exact source contract reference")}
          {field("po_reference", "Exact source purchase order reference")}
        </>
      )}
      {(kind === "term" || kind === "packet" || kind === "billing_scope") &&
        field(
          "unresolved",
          "Unresolved material uncertainties, separated by commas",
        )}
      <label>
        Supporting document
        <select name="evidence_document" defaultValue={source.document_id}>
          {documents.map((d) => (
            <option key={d.id} value={d.id}>
              {d.original_filename}
            </option>
          ))}
        </select>
      </label>
      {field("location", "Source page / sheet / cell / row", true)}
      <label>
        Source quotation
        <textarea name="quote" required />
      </label>
      {field("reason", "Review / correction reason", true)}
      {field(
        "resolution",
        "How ambiguity and semantic meaning were resolved",
        true,
      )}
      <label>
        <input type="checkbox" required /> I reviewed the source supporting
        every entered value, scope and semantic assertion.
      </label>
      {error && <p role="alert">{error}</p>}
      <button className="button" disabled={busy}>
        Save prepared review
      </button>
    </form>
  );
}
