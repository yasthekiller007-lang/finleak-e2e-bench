# Phase 3 — Validation and final report

Status: the Document Intelligence implementation is validated by full GitHub CI. Phase 4 is not started; main is unchanged. The review PR must remain unmerged unless the user instructs otherwise.

## 1. Baseline and execution context

The executable main ZIP matched all 108 tracked files at `949c17190f3b3e8a709173e93ff5ef954cf19943`, the merged Phase 2 baseline. Earlier CI on identical content passed 153 backend / 27 frontend tests plus migrations/schema drift. Local Phase 2 had 78 passed / 75 PostgreSQL skips. Work cannot initialize PostgreSQL 17 under an unprivileged user. No unsafe workaround, SQLite substitution, weakened tenant checks, or application changes to bypass that limit were made.

## 2. Validation evidence

Code checkpoint: `96c9fec089f40f4411baa069a7cbe05e42612112`.
Git tree: `0318ee221ccba4cfbf02c2ae5de68f7644a4b9fd`, verified identical to the staged executable copy.
Authoritative CI: https://github.com/yasthekiller007-lang/financial-leakage-ai/actions/runs/37045800001 — both jobs completed successfully.

| Check | Local Work | Authoritative CI |
| --- | --- | --- |
| Backend suite | **155 passed, 118 skipped**, 0 failures | **273 passed**, 0 skipped/failures |
| Frontend suite | **46 passed** | **46 passed** |
| Backend lint and formatting | Passed | Passed |
| Frontend lint, formatting, TypeScript | Passed | Passed |
| Frontend production build | Passed | Passed |
| Locked dependency installation | Existing locked installs available | `uv sync --locked` / `npm ci` passed |
| Alembic upgrade to head (0003) | PostgreSQL unavailable | Passed |
| Alembic schema drift validation | PostgreSQL unavailable | Passed; no new upgrade operations |
| Downgrade to base / upgrade back to head | PostgreSQL unavailable | Passed on disposable database |
| Schema drift after re-upgrade | PostgreSQL unavailable | Passed; no new upgrade operations |
| Synthetic golden benchmark | Passed | Passed |
| Secret pattern scan | 138 source files, 0 findings | 138 source files, 0 findings |
| Live HTTP startup/access checks | **11 passed** | Covered separately from CI integration tests |

The full suite retains all 153 pre-existing backend tests and adds 120 new cases. Frontend retains all 27 pre-existing tests and adds 19. No previous security regression suite was removed or relaxed. PostgreSQL integration tests cover authentication, memberships/revocation, document upload/download, duplicate protection, protected processing/evidence, malformed/scanned files, golden contract/invoice outputs, tenant-safe constraints, request concurrency, retry/history and migrations. The entire suite ran with PostgreSQL 17.11 in GitHub CI.

Local live checks started the real backend and production Next.js frontend, then verified public health/login, readiness returning 503 without a database, protected backend/frontend processing and extraction returning 401, workspace/detail redirecting to login, and the unconfigured session endpoint returning 503. The initial smoke expectation for the unconfigured session was corrected from 200 to its actual fail-closed 503; application code was unchanged. Services and their process groups were stopped after checks. GitHub stopped its disposable service container during cleanup.

Authenticated workflow validation is the upload → process → latest/history/evidence → original-download integration suite with temporary cryptographic identity fixtures and real PostgreSQL. No real OIDC provider or authenticated browser acceptance session is available. That limitation remains explicit; no production authentication bypass was introduced.

## 3. Architecture, dependency, and data model changes

See [Document Intelligence](document-intelligence.md) for detailed architecture and [architecture](architecture.md) for the existing foundation. Parsing, provider proposals, normalization, evidence validation, bounded execution and persistence are separate modules. Provider proposals identify existing source records; they never supply trusted monetary values. The first provider is deterministic explicit-label extraction. No paid AI call, external model, embeddings or OCR infrastructure was added.

The only new direct dependency is `pypdf>=6,<7`, locked in `uv.lock`, for direct PDF text extraction and encryption/container inspection. Existing defusedxml and standard CSV/ZIP/XML tools handle inert spreadsheets. No frontend dependency was added.

Migration 0003 adds tenant-owned `ExtractionRun` and `ExtractedField` records and extends document states. Runs retain versions, previous-run relationships, request keys, source hash, provider/parser/extractor/schema versions, initiator, timestamps, lease, limits, safe errors, candidate snapshots and warnings. Fields retain raw/normalized values, exact NUMERIC(20,6), confidence/reason and JSONB evidence. Composite foreign keys prevent cross-document/tenant references. Version/request uniqueness and the partial one-active-run index serialize processing. Financial precision and existing authoritative entities remain intact. Downgrade refuses history/review-state data loss; reversal succeeds only on the disposable empty validation database.

## 4. States, schema, provenance, and APIs

Pending uploads move through queued → processing → processed / needs_review / needs_ocr / failed. Explicit idempotency and reprocess versioning retain terminal history. Stale leases become audited failed/interrupted attempts on a subsequent request; no autonomous retry daemon exists. Attempt, file, character, row, cell, page, output, memory and time limits are configurable.

Contract candidates represent identity/parties/legal entities, effective/signature/expiry/renewal/notice dates, currency, product/service pricing, quantities, commitments, fixed/recurring/one-time fees, discounts/tiers/thresholds, rebates/credits/SLA terms, payment, escalation/index clauses, renewal/termination, PO/schedule/amendment references. Original/master/amendment/addendum/schedule/pricing-appendix candidates preserve parent/section/effective-date facts without applying precedence.

Invoice candidates represent identity/supplier/customer/billing entity, invoice/due/service dates, contract/PO/account references, currency, subtotal/discount/tax/fees/credits/total/amount due, and evidenced line description/sku/unit/quantity/price/discount/tax/fee/total/service/reference facts. All scalar fields are nullable. Exact Decimal normalization never fabricates totals, dates, currencies, prices or missing lines. Locale dates, bare dollar symbols, unsupported separators and conflicting sources remain unknown. A high-confidence explicit label is not a calibrated probability or approval.

Evidence is scoped to organization, document and extraction version. PDF evidence includes page/line/text span where available; spreadsheet evidence includes row/column/header and XLSX sheet/cell. Raw strings and source locations are retained. PDF bounding boxes and broad table reconstruction are deferred. Raster images, including images nested in Form XObjects, are detected conservatively; text-poor image pages require OCR without invented facts.

Protected API prefix: `/api/v1/organizations/{organization_id}/documents/{document_id}`. New endpoints: POST `/process`, POST `/reprocess`, GET `/extraction`, GET `/extraction-runs`, and GET `/extraction-runs/{run_id}`. Writes require a UUID Idempotency-Key and owner/admin/analyst role. Viewers may inspect/download. Reads check current membership and tenant/document scope. History is paginated. Missing/inaccessible resources return 404 and errors use controlled messages.

## 5. Frontend and security

Documents now link to a detail/review page: metadata, processing controls/status, structured nullable summaries, uncertainty notes, raw and normalized field evidence, original private download, and selectable version history. No leakage amount, fake customer data, internal parser terminology, or authoritative approval claim is displayed. Manual correction/approval is deferred.

Phase 2 OIDC verification, membership checks, private storage/downloads, upload classification and per-tenant SHA-256 duplicate protection are preserved. The Next.js proxy keeps tokens server-only, validates IDs/write Origin, refuses processing payloads, uses safe no-store JSON and bounds waits. Document HTML is rendered as escaped React text. Macros, unsafe XML entities, archive traversal/duplicate members and external workbook targets are rejected; formulas/cached values are ignored. No document text drives tool execution or changes authorization. Synthetic prompt-injection fixtures remain inert. The disposable worker strips application credentials and applies resource limits; it is not a full OS security sandbox. Logs retain identifiers/status/duration/versions without document content or exception strings. The source-pattern secret scan has bounded coverage and does not prove the absence of every possible secret format.

## 6. Golden benchmark

| Metric | Exact result |
| --- | --- |
| Synthetic documents | 16 |
| Required-field exact checks | **73 / 73** |
| Missing-field false fabrications | **0 / 571** |
| Invoice line-item checks | **9 / 9** |
| Contract pricing-entry checks | **7 / 7** |
| Evidence correctness checks | **128 / 128** |

Truth comes from synthetic explicit-label fixtures in `tests/fixtures/document_intelligence/golden.json`; generated files use independent source-location assertions. Mutation regressions fail on wrong amounts/dates, invented missing values, or wrong evidence locations. These results establish supported-template regression correctness, not real-world enterprise accuracy.

## 7. Known limitations, debt, and intentionally deferred work

- Labeled English templates only; arbitrary legal prose, broad layouts/languages, semantic PDF tables, image bounding boxes, vector-only/inline-image scans, deceptive text layers, locale conventions and Excel serial dates need more work.
- No OCR or live AI provider. A future provider needs source-grounding, calibration and adversarial validation before deployment.
- Extracted data remains reviewable candidates. No authoritative entity promotion, manual correction/approval or legal amendment precedence is implemented.
- Synchronous Linux execution, on-request lease recovery and bounded attempts are MVP mechanics; durable queueing, operational retry/reconciliation and robust worker sandboxing are deferred.
- Existing real OIDC acceptance, provider revocation/refresh, enterprise administration, storage/antivirus/retention/backups, rate limits, monitoring and broader operational security debt remains.
- No production deployment, leakage detection, financial rule compiler, Proof Engine, Recovery Ledger, fuzzy duplicate detection or enterprise integration was added.

## 8. Version control and handoff

All changes are on `phase3/document-intelligence`, based on validated main. A clearly marked checkpoint was committed before remote PostgreSQL validation because the required GitHub CI cannot test uncommitted local files. It was not declared validated before CI succeeded. The final documentation-only follow-up records observed results and receives its own CI run before review. Local executable content and remote Git trees are compared directly. The ZIP-import local history differs from the real GitHub history; matching Git trees establish exact executable equivalence.

No .env, credentials, local databases, node_modules, virtual environments, build/cache files or downloaded PostgreSQL artifacts are included. `git diff --check` passes. [HANDOFF.md](../HANDOFF.md) now records Phase 2 merge, current Phase 3 state, startup/configuration, tests, limitations and the exact next step. Main is unchanged, no automatic merge occurs and Phase 4 remains unstarted.

## 9. Exact recommendation for Phase 4

First specify with the user in Work how reviewed candidates become approved facts, how contracts/invoices link, what amendment/effective-date precedence applies, how price/discount/fee rules are defined, how units/currencies are matched, and which uncertainty blocks a claim. Use worked financial examples and golden expected outputs. Only after that specification and explicit authorization should implementation begin with one deterministic, evidence-backed comparison rule. Do not automatically begin the Leakage Engine.

## 10. Changed file inventory

- `.env.example`
- `.github/workflows/ci.yml`
- `HANDOFF.md`
- `README.md`
- `backend/app/api/intelligence.py`
- `backend/app/core/config.py`
- `backend/app/core/logging.py`
- `backend/app/db/models.py`
- `backend/app/domain/types.py`
- `backend/app/intelligence/benchmark.py`
- `backend/app/intelligence/execution.py`
- `backend/app/intelligence/extraction.py`
- `backend/app/intelligence/normalization.py`
- `backend/app/intelligence/parsing.py`
- `backend/app/intelligence/schema.py`
- `backend/app/intelligence/service.py`
- `backend/app/intelligence/worker.py`
- `backend/app/main.py`
- `backend/migrations/versions/0003_document_intelligence.py`
- `backend/pyproject.toml`
- `backend/tests/fixtures/document_intelligence/golden.json`
- `backend/tests/intelligence_fixtures.py`
- `backend/tests/test_extraction_concurrency.py`
- `backend/tests/test_intelligence.py`
- `backend/tests/test_intelligence_api.py`
- `backend/tests/test_phase3_migration.py`
- `backend/uv.lock`
- `docs/architecture.md`
- `docs/document-intelligence.md`
- `docs/phase3-validation.md`
- `frontend/src/app/(workspace)/documents/[organizationId]/[documentId]/page.tsx`
- `frontend/src/app/api/organizations/[organizationId]/documents/[documentId]/extraction-runs/[runId]/route.ts`
- `frontend/src/app/api/organizations/[organizationId]/documents/[documentId]/extraction-runs/route.ts`
- `frontend/src/app/api/organizations/[organizationId]/documents/[documentId]/extraction/route.ts`
- `frontend/src/app/api/organizations/[organizationId]/documents/[documentId]/process/route.ts`
- `frontend/src/app/api/organizations/[organizationId]/documents/[documentId]/reprocess/route.ts`
- `frontend/src/app/globals.css`
- `frontend/src/components/document-detail.tsx`
- `frontend/src/components/document-workspace.tsx`
- `frontend/src/lib/documents.ts`
- `frontend/src/lib/intelligence-proxy.ts`
- `frontend/src/lib/intelligence.ts`
- `frontend/tests/document-detail.test.tsx`
- `frontend/tests/documents.test.tsx`
- `frontend/tests/intelligence-proxy.test.ts`
- `tools/secret_scan.py`
