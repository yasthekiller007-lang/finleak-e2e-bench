# Phase 3 — Document Intelligence

Phase 3 extracts reviewable, versioned candidates from contracts and invoices. It does not interpret legal precedence, calculate leakage, or create authoritative Contract/ContractVersion/Invoice/InvoiceLineItem records. All candidates retain evidence; missing or ambiguous values remain null.

## Architecture

`parsing.py` reads inert document data into source records. `extraction.py` maps explicit labels to schema paths through the `ExtractionProvider` protocol. Providers propose only a path and source ID; normalization and evidence validation run independently before persistence. `normalization.py` uses exact Decimal strings and conservative date/currency parsing. `schema.py` defines supported fields, limits, versions, errors, and typed results. `execution.py` verifies the stored checksum/size and runs `worker.py` in a disposable subprocess. `service.py` serializes processing claims, persists candidate snapshots, and serves tenant-scoped history. No live AI provider or paid calls are required.

The provider interface is an extension point, not a deployed LLM integration. A future provider must remain untrusted: proposals cannot introduce facts without source records. The execution adapter is synchronous; a future queue can invoke the same service. Linux CPU, memory, output-size, and wall-clock limits bound the parser process. This is resource containment, not an OS/container security sandbox. The worker receives no application credentials or inherited environment secrets. It uses no document-directed tools or network calls.

## Supported source layouts

| Format | First supported layout | Evidence |
| --- | --- | --- |
| PDF | Direct text with `Label: value`, numbered `Line 1 quantity` / `Pricing 1 unit price`, or pipe-separated tables with headers | 1-based page, line, character span in extracted text where available, original line; table row/column |
| CSV | UTF-8 / UTF-8 BOM; `field,value` / `label,value` tables, or explicit column headers | 1-based row, column, header, raw cell |
| XLSX | Header tables / field-value sheets; shared/inline strings and exact numeric XML values | Sheet name, 1-based row/column, cell reference, raw cell |

Schema paths such as `identity.invoice_number`, `totals.total`, and `lines.1.unit_price` are supported labels. Table line columns include description, sku, quantity, unit, unit price, discount, tax, fees, total, service start/end, purchase order, and contract reference. Pricing columns include product, sku, description, unit, quantity, unit price, discount percentage/amount, threshold quantity, tier, effective date, and end date. Unsupported/free-form content is retained as a review warning rather than interpreted autonomously.

PDF coordinates and visual table reconstruction are not available in this version. Character positions refer to extracted page text, not original file byte offsets. Raster images, including images nested in Form XObjects, are recognized; image pages with insufficient text require OCR. Images on text-rich pages still produce a review warning. OCR has not been implemented. Empty PDFs fail with a safe error; password-protected and malformed PDFs fail safely. Detection is a conservative heuristic: vector-only scans, inline images, deceptive text layers, and unusual PDF layouts require further work.

XLSX formulas and cached formula results are ignored, with a warning. Macros, duplicate ZIP members, archive traversal paths, unsafe XML entities, and external workbook relationships are rejected. Spreadsheet links are never fetched. Date serials/locale-formatted amounts remain unknown when the source cannot establish their meaning. No spreadsheet code is executed.

## Candidate schemas

All scalar paths are nullable. Line/pricing arrays contain only evidenced entries; numbering gaps are rejected rather than filled with invented rows.

| Contract section | Supported fields |
| --- | --- |
| Identity | contract number, title, parties, supplier, customer, legal entities, account/vendor/customer IDs, document kind, parent contract reference, amendment number, changed terms, referenced section |
| Dates | signature, effective, end, renewal, notice deadline, termination |
| Currency | explicit supported ISO-style code |
| Commercial | fixed, recurring, one-time fees; minimum/maximum commitments |
| Pricing entries | product/service, sku, description, unit, quantity, unit price, discount percentage/amount, threshold quantity, tier, effective/end dates |
| Discounts | percentage, amount, volume terms, effective date |
| Rebates | percentage, amount, credit conditions, service credits, SLA credits |
| Payment | terms, due terms, early payment discount, late payment terms |
| Price changes | escalation clause, maximum increase, index-linked increase, effective date |
| Renewal | auto renewal, period, notice requirements |
| References | purchase order, schedules, amendments |

Document-kind candidates support original, master agreement, amendment, addendum, schedule, and pricing appendix. Explicit amendment references and changed terms are extracted without resolving conflicts or supersession. Later effective-date interpretation must use a separately specified review/approval model.

| Invoice section | Supported fields |
| --- | --- |
| Identity | invoice number, supplier, customer, supplier/customer IDs, billing entity |
| Dates | invoice date, due date, service start/end |
| References | contract, purchase order, account, customer/vendor references |
| Currency | explicit supported ISO-style code |
| Totals | subtotal, discount, tax, fees, credits, total, amount due |
| Lines | description, sku, quantity, unit, unit price, discount, tax, fees, total, service start/end, purchase order, contract reference |

Secondary upload types (purchase orders, credit notes, other) remain accepted. Their structured extraction is deferred and ends in needs_review. The upload document type remains a user selection.

## Normalization and certainty

Money, quantity, percentages, and commitments use Python Decimal with PostgreSQL NUMERIC(20,6). Values exceeding 14 integral or 6 fractional digits remain null instead of being rounded. JSON transports decimal strings. No inferred arithmetic totals or foreign-exchange conversion occurs. `USD 1,250.00` normalizes to `1250.00`; ambiguous separators and bare dollar symbols remain unknown. Currency codes use an explicitly documented allowlist in `normalization.py`; unsupported codes remain reviewable raw data.

Dates accept valid ISO date-only values and explicit English month names. Numeric locale dates such as `03/04/2026` remain null. Timestamps are never invented for date-only fields. Percentages remain percentage values (8 means 8 percent). Explicit boolean yes/no/true/false values are supported. Payment terms only normalize explicit Net N, due upon receipt, or payable upon receipt expressions; missing referenced schedules stay unknown.

Every field keeps raw value, normalized value, type, confidence, normalization reason, and source. High confidence means an explicit label and exact supported normalization, not a calibrated probability or legal confirmation. Conflicting sources null the chosen value while retaining all candidate evidence. Missing required fields, incomplete entries, unsupported content, ignored formulas, and image content route results to review. `processed` means extraction completed without those warnings; it does not mean approved or authoritative.

## Persistence and tenant safety

Migration `0003_document_intelligence.py` adds `extraction_runs` and `extracted_fields`, and extends document status with needs_review/needs_ocr. Existing monetary columns and Phase 2 document/auth semantics are preserved.

Runs contain organization/document, initiator, version, idempotency key, previous attempt, status, input SHA-256, parser/extractor/schema/provider versions, start/finish/lease times, safe error code, configured limits, structured candidate snapshot, and warnings. Fields contain organization/document/run, path, raw/normalized values, exact NUMERIC for normalized decimals, confidence/reason, and JSONB evidence.

Composite foreign keys prevent attaching a run, previous run, or field to another tenant/document. Unique constraints protect version and request key per document; a PostgreSQL partial unique index permits only one active attempt. Explicit SQL scoping and current membership checks apply to every read/write. Existing SHA-256 duplicate upload protection remains separate from later duplicate-invoice detection.

Downgrade refuses to remove any extraction history or needs_review/needs_ocr document state. On a disposable empty test database the full chain can downgrade to base and upgrade to head. Populated production downgrade requires an explicit backup/reconciliation plan.

## Processing states and retries

Uploads begin pending. A claim moves document/run through queued and processing, then processed, needs_review, needs_ocr, or failed. Document-row locks serialize claims. Processing requests require a UUID Idempotency-Key. Reusing the key returns the original attempt; ordinary process returns the latest attempt. Reprocess creates a new version linked to the prior version. Terminal results are not overwritten by reprocessing.

Active leases expire after the configured worker timeout plus grace. A subsequent request audits a stale attempt as failed/interrupted; explicit reprocess can start the next version. An expired attempt cannot be overwritten by a late worker. There is no autonomous background retry/recovery daemon. Configurable attempt limits stop repeated work; exact-key reads remain idempotent at the limit. Owner/admin/analyst may process; viewers may inspect/download only.

## API and user experience

Prefix: `/api/v1/organizations/{organization_id}/documents/{document_id}`.

| Method/path | Result |
| --- | --- |
| POST `/process` | Process existing stored file or return prior attempt |
| POST `/reprocess` | Create another audited version |
| GET `/extraction` | Latest attempt, including failures, or null |
| GET `/extraction-runs` | Paginated history; limit 1–100, offset >= 0 |
| GET `/extraction-runs/{run_id}` | Specific attempt, candidate fields, and evidence |

All endpoints require authentication and current membership. Unknown/inaccessible resources return 404; viewers cannot process (403); unauthenticated requests return 401. The Next.js proxy forwards server-only tokens, validates UUID paths and write Origin, rejects request bodies on processing actions, and returns no-store JSON. API errors use controlled codes/messages without exception text or document content.

The Documents table links to a detail page with metadata, processing status, process/reprocess controls, refresh, structured candidate sections, uncertainty notes, expandable source evidence, private original download, and version history. React renders text as text, never document HTML. No leakage amounts or invented client data appear. Manual correction/approval is deferred; evidence and earlier machine results are preserved for a future audited workflow.

## Limits, logs, and operations

`FLA_PROCESSING_LIMITS` accepts a JSON Limits object; defaults are 100 PDF pages, 5,000 rows, 50,000 cells, 500,000 characters, 5,000 fields, 50 MiB expanded XLSX data, 20 seconds CPU budget, and 512 MiB address space. Bounds and validation live in `schema.py`. `FLA_MAX_EXTRACTION_ATTEMPTS` defaults to 10 (1–100). `FLA_MAX_UPLOAD_BYTES` retains the Phase 2 limit.

Processing logs include organization/document/run IDs, type, status, duration, and versions. They do not log document content, tokens, clauses, invoice data, or exception strings. Private temporary files are removed on completion/failure. Storage integrity checks run before parsing. Source-pattern secret scanning is bounded and does not replace credential-management controls.

## Validation and benchmark

Existing Phase 2 backend/frontend/security tests are retained. New tests cover synthetic contract/invoice extraction, exact Decimal normalization, missing/conflicting values, evidence locations, scanned and malformed files, malicious document text, XML/macros/formulas, processing limits, worker timeout/integrity, protected APIs, history/idempotency, stale leases, concurrent claims, tenant-safe foreign keys, and Phase 3 migration preservation/drift/refusal behavior.

Run `uv run python -m app.intelligence.benchmark` in backend for the synthetic golden benchmark; fixture truth is in `tests/fixtures/document_intelligence/golden.json`. Its 16 explicit-label documents yield 73/73 required checks, 0/571 missing-field fabrications, 9/9 invoice line checks, 7/7 pricing-entry checks, and 128/128 evidence checks. These exact results apply only to supported synthetic templates, not unseen enterprise contracts.

Work cannot run PostgreSQL 17 under an unprivileged user. Local database tests are skipped explicitly, never replaced with SQLite. The branch CI runs PostgreSQL 17.11, all backend/frontend checks, upgrade/check, benchmark/secret scan, downgrade/base and upgrade/check again. No phase is validated until the full CI passes. Current evidence and pending limitations are recorded in `phase3-validation.md`.

## Deferred and next phase

Deferred: OCR, broad multilingual/free-form extraction, semantic PDF tables/coordinates, AI-provider calibration, manual correction/approval, authoritative entity promotion, production queue and retry operations, real-provider acceptance, antivirus/storage operational controls, and the existing Phase 2 production debt.

Phase 4 should begin with business specifications in Work: candidate approval/promotion, contract-to-invoice linkage, amendment precedence/effective dates, price/discount/fee definitions, currency/unit compatibility, uncertainty exclusions, and reproducible evidence calculations. Approve worked examples and golden outcomes before implementing a minimal deterministic rule. No Leakage Compiler, Proof Engine, Recovery Ledger, enterprise integrations, or leakage detection has been implemented in Phase 3. Do not start Phase 4 automatically.
