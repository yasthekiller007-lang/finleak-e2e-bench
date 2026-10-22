"use client";
import { useState } from "react";
import type { FinancialDocument } from "@/lib/documents";
import type { Instrument, LedgerRecord, RecoveryCase } from "@/lib/recovery";
import { sourceFields } from "@/lib/recovery";

type Field = {
  name: string;
  label: string;
  options?: string[];
  optional?: boolean;
};
const field = (
  name: string,
  label: string,
  options?: string[],
  optional = false,
): Field => ({ name, label, options, optional });
const monetary = [
  field("principal", "Evidenced tax-exclusive principal", undefined, true),
  field("gross", "Gross performance / face amount", undefined, true),
  field("tax", "Explicit tax component", undefined, true),
  field("fees", "Bank/payment fees", undefined, true),
  field("withholding", "Withholding", undefined, true),
  field("net_cash", "Actual net bank cash", undefined, true),
  field("other", "Other economic consideration", undefined, true),
  field("tax_basis", "Source tax basis", ["EXCLUSIVE", "INCLUSIVE", "UNKNOWN"]),
  field("reconciliation", "Component reconciliation", [
    "COMPLETE",
    "UNRESOLVED",
  ]),
];
const parties = [
  field("payer", "Actual payer legal identity"),
  field("payee", "Actual payee legal identity"),
  field("beneficiary", "Benefited customer legal identity"),
];
const forms: Record<string, Field[]> = {
  party: [
    field(
      "previous_party_id",
      "Prior association for revision",
      undefined,
      true,
    ),
    field("supplier", "Invoice supplier legal identity"),
    field("customer", "Invoice customer legal identity"),
    ...parties,
    field("valid_from", "Relationship valid from (inclusive)"),
    field("valid_to", "Valid until (exclusive)", undefined, true),
    field("relationship", "Evidenced relationship", [
      "DIRECT",
      "AGENCY",
      "ASSIGNMENT",
      "CONTINUITY",
      "PROCESSOR",
      "INTERCOMPANY",
    ]),
    field("discharge", "Authority, obligation and beneficiary evidence"),
  ],
  party_revoked: [field("party_id", "Association to revoke")],
  readiness: [
    field("proof_id", "Existing COMPLETE monetary proof"),
    field("decision_id", "Actual confirmed finding decision"),
    field("party_id", "Approved party association"),
    field("pursuit", "Commercial pursuit ceiling B"),
    field("quantum", "Evidenced currency quantum"),
    field("currency", "Finding currency"),
    field("scope", "Exact finding scope"),
    field("reconciliation", "Pursuit coverage", ["COMPLETE", "UNRESOLVED"]),
  ],
  instrument: [
    field("instrument_id", "Economic instrument"),
    field(
      "previous_review_id",
      "Prior reviewed observation for correction",
      undefined,
      true,
    ),
    ...monetary,
    ...parties,
    field("scope", "Exact remedy scope"),
    field("origin", "Economic origin", [
      "POST_FINDING_REMEDY",
      "PREEXISTING",
      "UNRESOLVED",
    ]),
    field("status", "Observed performance state", [
      "SETTLED",
      "ISSUED",
      "POSTED",
      "INCURRED",
      "AGREED",
      "UNRESOLVED",
    ]),
  ],
  realization: [
    field("instrument_id", "Economic instrument"),
    field("instrument_review_id", "Approved instrument observation"),
    field("party_id", "Approved party association"),
    field("readiness_id", "Current readiness approval"),
    field("method", "Completed recovery method", [
      "CASH",
      "APPLIED_CREDIT",
      "LIABILITY_REDUCTION",
    ]),
    field("amount", "Explicit principal allocation"),
    ...monetary,
    field("currency", "Original currency"),
    field("quantum", "Evidenced source quantum"),
    field("event_reference", "Economic event / allocation reference"),
    field(
      "replaces_id",
      "Original allocation for explicit replacement",
      undefined,
      true,
    ),
    ...parties,
    field("scope", "Exact remedy scope"),
    field(
      "application_reference",
      "Actual AP application reference",
      undefined,
      true,
    ),
    field(
      "unpaid_original",
      "Original liability confirmed unpaid",
      ["UNKNOWN", "true", "false"],
      true,
    ),
    field("liability_before", "Posted liability before", undefined, true),
    field("liability_after", "Posted liability after", undefined, true),
    field(
      "discharge",
      "Completed performance and principal discharge evidence",
    ),
  ],
  reversal: [
    field("original_id", "Original approved allocation"),
    field("amount", "Explicit amount to reverse / de-recognize"),
    field("reversal_type", "Economic meaning", [
      "ECONOMIC_RETURN",
      "DE_RECOGNITION",
    ]),
    field("event_reference", "Return / correction reference"),
    field(
      "restored_credit",
      "Separately evidenced restored credit",
      undefined,
      true,
    ),
    field("cash_return", "Actual settled outgoing bank cash", undefined, true),
    field("discharge", "Return or corrected attribution evidence"),
  ],
  credit_state: [
    field("instrument_id", "Credit instrument"),
    field("state", "Credit state", [
      "CANCELLED",
      "EXPIRED",
      "RESTORED",
      "RECONCILED",
    ]),
    field("amount", "Explicit affected credit principal"),
    field(
      "original_id",
      "Approved application reversal for restoration",
      undefined,
      true,
    ),
    field("reconciliation", "Credit reconciliation", [
      "COMPLETE",
      "UNRESOLVED",
    ]),
  ],
  claim: [
    field("state", "Recorded human action", [
      "DRAFT",
      "RECORDED_ACTION",
      "WITHDRAWN",
      "REPLACED",
    ]),
    field("principal", "Actioned principal", undefined, true),
    field("currency", "Original currency"),
    field("tax_basis", "Claim basis", ["EXCLUSIVE", "UNKNOWN"]),
    field("scope", "Claim scope"),
    field("action_reference", "Outside-platform action reference"),
  ],
  vendor: [
    field("state", "Evidenced vendor position", [
      "ACKNOWLEDGED",
      "PARTLY_DISPUTED",
      "DISPUTED",
      "UNRESOLVED",
    ]),
    field("acknowledged", "Explicit acknowledged principal", undefined, true),
    field("disputed", "Explicit disputed principal", undefined, true),
    field("agreed_gross", "Raw agreed settlement", undefined, true),
    field("currency", "Original currency"),
    field("tax_basis", "Position basis", ["EXCLUSIVE", "UNKNOWN"]),
    field("party_id", "Approved responder association"),
    field("scope", "Response scope"),
    field("conditional", "Conditional position", ["true", "false"]),
  ],
  cost: [
    field("instrument_id", "Deduplicated direct-cost instrument"),
    field("state", "Cost economic state", ["INCURRED", "PAID", "REVERSED"]),
    field("event_reference", "Cost / payment reference"),
    field("principal", "Direct cost amount"),
    field("currency", "Cost currency"),
    field("original_id", "Original cost for reversal", undefined, true),
    field("scope", "Directly attributable case scope"),
  ],
  alias: [
    field("instrument_id", "Reviewed economic instrument"),
    field("alias_kind", "Instrument type", [
      "CASH",
      "CREDIT",
      "LIABILITY",
      "COST",
      "SETTLEMENT",
    ]),
    field("namespace", "Evidenced alternate namespace"),
    field("issuer", "Evidenced issuer legal identity"),
    field("reference", "Evidenced alternate economic reference"),
    field("currency", "Original currency"),
  ],
  retire: [
    field("successor_case_id", "Explicit same-scope successor case"),
    field(
      "proof_successor_id",
      "Existing authorized proof successor relationship",
    ),
  ],
};
const dated = new Set([
  "instrument",
  "realization",
  "reversal",
  "credit_state",
  "claim",
  "vendor",
  "cost",
]);
export function RecoveryProposalForm({
  detail,
  documents,
  instruments,
  history,
  busy,
  submit,
}: {
  detail: RecoveryCase;
  documents: FinancialDocument[];
  instruments: Instrument[];
  history: LedgerRecord[];
  busy: boolean;
  submit: (body: unknown) => Promise<void>;
}) {
  const [kind, setKind] = useState("party");
  const [values, setValues] = useState<Record<string, string>>({});
  const [document, setDocument] = useState("");
  const [locator, setLocator] = useState("");
  const [quote, setQuote] = useState("");
  const [reason, setReason] = useState("");
  const [reviewed, setReviewed] = useState(false);
  function control(f: Field) {
    const refKind =
      f.name === "party_id" || f.name === "previous_party_id"
        ? "party"
        : f.name === "instrument_review_id" || f.name === "previous_review_id"
          ? "instrument"
          : f.name === "readiness_id"
            ? "readiness"
            : f.name === "original_id" || f.name === "replaces_id"
              ? kind === "cost"
                ? "cost"
                : kind === "credit_state"
                  ? "reversal"
                  : "realization"
              : null;
    const refs = refKind ? history.filter((r) => r.kind === refKind) : [];
    const update = (value: string) =>
      setValues((v) => ({ ...v, [f.name]: value }));
    return (
      <label key={f.name}>
        {f.label}
        {f.options ? (
          <select
            required={!f.optional}
            value={values[f.name] ?? ""}
            onChange={(e) => update(e.target.value)}
          >
            <option value="">Choose</option>
            {f.options.map((o) => (
              <option key={o}>{o}</option>
            ))}
          </select>
        ) : f.name === "instrument_id" ? (
          <select
            required
            value={values[f.name] ?? ""}
            onChange={(e) => update(e.target.value)}
          >
            <option value="">Choose instrument</option>
            {instruments.map((i) => (
              <option value={i.id} key={i.id}>
                {i.kind} · {i.reference} · {i.currency}
              </option>
            ))}
          </select>
        ) : refs.length ? (
          <select
            required={!f.optional}
            value={values[f.name] ?? ""}
            onChange={(e) => update(e.target.value)}
          >
            <option value="">Choose reviewed record</option>
            {refs.map((r) => (
              <option value={r.id} key={r.id}>
                {r.kind} #{r.number} · {r.reason}
              </option>
            ))}
          </select>
        ) : (
          <input
            required={!f.optional}
            maxLength={4000}
            value={values[f.name] ?? ""}
            onChange={(e) => update(e.target.value)}
          />
        )}
      </label>
    );
  }
  async function prepare(e: React.FormEvent) {
    e.preventDefault();
    const value: Record<string, unknown> = { kind };
    for (const f of forms[kind]) {
      const raw = values[f.name] ?? "";
      value[f.name] =
        raw === "" || raw === "UNKNOWN"
          ? null
          : ["conditional", "unpaid_original"].includes(f.name)
            ? raw === "true"
            : raw;
    }
    if (["instrument", "realization"].includes(kind))
      value.tax_recoverability = "NOT_ASSESSED";
    if (kind === "readiness") value.tax_basis = "EXCLUSIVE";
    if (kind === "instrument") value.related_cases = [detail.id];
    if (kind === "realization") value.completed = true;
    if (kind === "cost") value.directly_attributable = true;
    if (kind === "alias") {
      value.identity = {
        kind: value.alias_kind,
        namespace: value.namespace,
        issuer: value.issuer,
        reference: value.reference,
        currency: value.currency,
      };
      for (const key of [
        "alias_kind",
        "namespace",
        "issuer",
        "reference",
        "currency",
      ])
        delete value[key];
    }
    if (dated.has(kind))
      value.economic = {
        precision: values.precision ?? "DATE",
        day: (values.precision ?? "DATE") === "DATE" ? values.economic : null,
        timestamp:
          values.precision && values.precision !== "DATE"
            ? values.economic
            : null,
        timezone: values.timezone || null,
      };
    const fields = sourceFields(value);
    await submit({
      value,
      expected_head: detail.head_id,
      reason,
      evidence: [
        {
          document_id: document,
          locator,
          quotation: quote,
          supports: Object.keys(fields),
          raw_fields: { source_quotation: quote },
          reviewed_fields: fields,
        },
      ],
    });
  }
  return (
    <form onSubmit={prepare} className="stack">
      <h3>Prepare reviewed proposal</h3>
      <p>
        Proposals do not recognize money. Cite protected original evidence for
        each reviewed meaning. Owner/admin approval remains separate.
      </p>
      <label>
        Proposal type
        <select
          value={kind}
          onChange={(e) => {
            setKind(e.target.value);
            setValues({});
            setReviewed(false);
          }}
        >
          {Object.keys(forms).map((k) => (
            <option key={k} value={k}>
              {k.replaceAll("_", " ")}
            </option>
          ))}
        </select>
      </label>
      {forms[kind].map(control)}
      {dated.has(kind) && (
        <>
          <label>
            Source date precision
            <select
              value={values.precision ?? "DATE"}
              onChange={(e) =>
                setValues((v) => ({ ...v, precision: e.target.value }))
              }
            >
              <option>DATE</option>
              <option>INSTANT</option>
              <option>LOCAL</option>
            </select>
          </label>
          <label>
            Original economic date / timestamp
            <input
              required
              value={values.economic ?? ""}
              onChange={(e) =>
                setValues((v) => ({ ...v, economic: e.target.value }))
              }
            />
          </label>
          <label>
            Evidenced source timezone (leave unknown blank)
            <input
              value={values.timezone ?? ""}
              onChange={(e) =>
                setValues((v) => ({ ...v, timezone: e.target.value }))
              }
            />
          </label>
        </>
      )}
      <label>
        Protected source document
        <select
          required
          value={document}
          onChange={(e) => setDocument(e.target.value)}
        >
          <option value="">Choose uploaded original</option>
          {documents.map((d) => (
            <option key={d.id} value={d.id}>
              {d.original_filename}
            </option>
          ))}
        </select>
      </label>
      <label>
        Source locator
        <input
          required
          maxLength={4000}
          value={locator}
          onChange={(e) => setLocator(e.target.value)}
        />
      </label>
      <label>
        Exact source quotation
        <textarea
          required
          maxLength={4000}
          value={quote}
          onChange={(e) => setQuote(e.target.value)}
        />
      </label>
      <label>
        Review reason
        <textarea
          required
          maxLength={4000}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      </label>
      <label>
        <input
          type="checkbox"
          required
          checked={reviewed}
          onChange={(e) => setReviewed(e.target.checked)}
        />
        I reviewed the source mapping for these fields. No tax recoverability,
        counterparty relationship or unknown amount has been inferred.
      </label>
      <button disabled={busy || !reviewed}>Save proposal for review</button>
    </form>
  );
}
