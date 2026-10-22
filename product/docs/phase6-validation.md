# Phase 6 V1 Recovery Ledger — implementation and validation report

The separately authorized Phase 6 V1 implementation is delivered on phase6/recovery-ledger-implementation for review against main. It records reviewed economic recovery without changing Phase 4 financial findings or Phase 5 proof content. It is not merged, deployed, an accounting general ledger or a legal/tax certification. The [approved specification version 1.0](phase6-recovery-ledger-spec.md) and PD6-01–PD6-37 Option A remain the business authority.

Starting main: 15c7fc34d4d0092613dc2379f63d606594feebab. The resumed remote schema checkpoint was bb7091affd831e38c91ad3d9bf0f7fdbf6f5cf19. Checkpoints A and B are preserved in ancestry. No unverifiable lost implementation was reconstructed and Phases 1–5 were not restarted.

## Release acceptance and validation provenance

The complete configured CI must pass on the exact implementation PR head, including PostgreSQL 17.11, all backend tests without skips, frontend checks and migration checks. A previous green checkpoint is not final-head validation. The final-head SHA, CI run and PR URL are reported in the delivery report/PR checks rather than embedded self-referentially in this commit. This report documents the final implementation and test inventory; final release acceptance is the complete CI attached to that head.

| Validation | Evidence / acceptance |
| --- | --- |
| Full backend suite | 672 collected tests. All must pass without skips in PostgreSQL CI. Scratch-only execution passes 315 tests with 357 PostgreSQL-dependent skips; this is not the database acceptance result. |
| Full frontend suite | 100 tests in 12 files pass locally, including existing financial/proof regressions and recovery UI/proxy behavior. |
| PostgreSQL | CI runs the pinned postgres:17.11-bookworm service with commit-timestamp tracking enabled. Recovery fixtures create isolated schemas, apply all six migrations and use real commits; concurrent tests use independent sessions/connections. |
| Migration | Revision 0006_recovery_ledger. CI upgrade/head → schema drift check → full tests → empty full-chain downgrade/base → re-upgrade/head → second drift check. Dedicated tests preserve legacy data and reject downgrade of populated recovery/audit history. |
| Backend lint/format | Ruff check and format check pass locally. No standalone backend type-checker is configured; typed Pydantic input validation/runtime tests are retained. |
| Frontend lint/format/types/build | ESLint, Prettier, Next type generation/TypeScript and production build pass locally. No new PDF or extraction dependency. |
| Extraction benchmark | Existing 16 synthetic documents: 73/73 required fields, 7/7 pricing, 9/9 lines, 128/128 evidence, zero missing-field fabrication. It does not claim general recovery-document extraction. |
| Secret scan | Existing bounded pattern scan: 213 source files, zero findings. This is not exhaustive secret/security certification. |
| Documentation/policy | 100 local relative links, requirement/test-reference inventory, 38 independent Decimal equations and git diff --check checked. All 56 examples and policy sections remain unchanged; only Phase 6 execution metadata changes. Phase 4/5 whole-file hashes verified below. |

Historical CI checkpoints are preserved honestly: checkpoint B run 37149894195 failed on colliding self-reference FK names; the follow-up named them distinctly. Checkpoint C run 37151822252 and D run 37152249402 passed complete CI. E run 37153216771 passed complete CI. F1/F2/F3 exposed fixture/audit-reference/rollback issues and were repaired without removing recognition/integrity assertions. F4 run 37156781174 passed complete CI with 655 PostgreSQL backend tests, zero skips, and 100 frontend tests. F5 run 37157244157 passed 663 backend tests and failed one helper which attempted a read after disabling a guard; that read is now correctly denied. The final test submits the approval directly and still asserts 503 plus zero financial entries. F6 run 37157639530 passed 665 backend tests and failed the same now-corrected helper; frontend passed. F7 run 37158541014 passed complete CI with 671 PostgreSQL backend tests, zero skips, and 100 frontend tests. Final delivery still requires complete CI for the final head including the additional F8 case-root guard.

## Architecture and financial authority

Eight new tenant-scoped append-only tables provide the minimal stable representation: RecoveryCase, RecoveryInstrument, RecoveryProposal, RecoveryEvidence, RecoveryRecord, RecoveryAlias, RecoveryRequest and RecoveryPublication. Case uniqueness anchors one organization/immutable FinancialEvaluation. Economic root identity uses exact namespace/issuer/reference/currency independent of documents, proof revisions or extraction reruns; reviewed aliases cannot collide with another root. Credit state and all economic instrument authority remain bound to one case in both service and database; another case cannot consume/cancel that root. Legacy LeakageCase.recovered_amount remains unchanged and is never used as authoritative R or automatically imported.

Reviewed proposals preserve exact typed meaning, expected case predecessor and immutable evidence manifests. Approval appends a record with actor/reason/audit, method, economic precision, source pins, component amounts and original/root relationships. NUMERIC(20,6) and finite Decimal strings use context precision 80; unsupported scale, quantum or overflow fails explicitly. Only percentage display uses two-decimal HALF_UP with exact ratio inputs retained. Financial amounts are never rounded to fit a budget or edited afterward.

Database composite FKs enforce tenant relationships. Immutable/authority/audit triggers reject in-place changes, stale case chains, malformed proposal correspondence, unsupported final roles, invalid positive financial pins/budgets and forged known-at provenance. Referenced Document hash/size/type/storage identity and deletion remain protected. Trigger-origin FinancialAudit contains who/when/what/role/reason/target/predecessor; event and audit commit atomically. Service-layer recognition additionally enforces actual source-byte capture, complete reviewed field mapping, current financial currentness, dated economic attribution, physical credit/receipt reconciliation and all R01–R10. Actual filesystem bytes and human citation meaning cannot be certified by database constraints alone.

Organization locks and fresh membership fencing reuse the Phase 4/5 order. Recovery admission slots are acquired before waiting on the organization lock. The actor quota is serialized across all tenants and uses PostgreSQL clock time. Exact prepared head, decision, evaluation/proof fingerprints, party/readiness, root review, source metadata/byte capture and remaining original/case/instrument budgets are checked under one consistent authority fence. Sources are rehashed before financial commit. Failure rolls back all event/allocation/audit state; a losing race conflicts/retries instead of truncating money.

P, actual current V, approved B, effective C, vendor S/D, signed method-specific R, pending credit stock, actual N, costs and workflow remain separate. Direct refund does not fabricate C or S. B cannot exceed V or be revised below outstanding R/current actioned C. Issued credit is not R; applied credit/cash redemption share one physical root. De-recognition releases attribution, not physical AP availability or bank cash. Explicit evidence-backed AP restoration and actual cash returns are different actions. Corrected dates append history; unknown basis/withholding/counterparty/currency/stock coverage remains null/unresolved. Costs remain incurred/paid by original currency, never netted against P/R/N.

Current dismissal prevents new ordinary case authority. Existing historical recovery survives dismissal/staleness/closure as an exception overlay, with authorized corrective negatives allowed. Explicit existing same-scope ProofSuccessor links can retire unused pursuit; a case with any recognized history cannot transfer monetary authority under V1, including after full reversal. Overlapping predecessor/successor authority is blocked. No timestamps alone imply a successor.

## Historical time and reproducible reporting

Economic DATE, exact INSTANT, LOCAL timestamp and evidenced timezone are distinct. No midnight UTC or guessed source timezone is introduced. DST gaps/folds, date-only partial-day attribution and conflicting physical receipt dates return explicit unresolved/block results. Each claim/response/credit issue/application/cash/reduction/reversal/cost uses its own economic source date, not upload/approval/created_at.

RecoveryPublication captures actual pg_xact_commit_timestamp of the committed case/record transaction. The database checks the timestamp against source xmin. recorded_at is an insertion timestamp and never used as known-at K. Capture is independent retryable metadata after financial commit: failure cannot mislabel an already committed financial action as rolled back. Reads repair an uncaptured receipt only from actual PostgreSQL provenance. Tracking disabled or missing provenance fails closed. Existing installations must enable track_commit_timestamp=on at PostgreSQL server start; compose/CI configure it.

Reports pin K, selected history IDs, ledger high-watermark, profile, tenant, currency/customer/tax filters, coverage and a deterministic projection digest. Reporting uses declared [start,end) economic boundaries. Missing historical eligibility observations are UNKNOWN, not fabricated from today's is_stale. Corrections/restatements preserve old K/digest. Correcting credit application date also corrects the period's pending stock without inventing restored credit. Unknown credit stock cannot hide behind a partial known-stock total. Multiple principal allocations to one CASH root produce one physical N receipt; contradictory corrected receipt dates leave recorded R/history accessible and block period cash attribution.

Complete bounded matched non-overlapping populations produce separate active/exception realization, matching V and qualified ratio; page results never produce authoritative portfolio totals. There is no persisted aggregate finding/proof, recovery export artifact, accounting period posting or general-ledger subsystem.

## Internal APIs and UI

All endpoints use current organization membership under /api/v1/organizations/{organization_id}/recovery. Mutations require a UUID Idempotency-Key, strict JSON and explicit expected predecessors.

| Route | Purpose / authority |
| --- | --- |
| POST /cases; GET /cases and /cases/{id} | Stable positive finding case creation/investigation and bounded detail/page reads. Owner/admin/analyst prepare; viewer reads. |
| POST/GET /instruments | Stable economic root identity and bounded root listing; identity alone grants no money. |
| POST /cases/{id}/proposals | Typed manually evidenced party/readiness/root/alias/claim/vendor/realization/reversal/credit/cost/retirement preparation. |
| POST /proposals/{id}/decision | Fresh owner/admin final approval/rejection; preparer may withdraw its proposal. Exact proposal/evidence/predecessor preserved. |
| GET /proposals/{id}/evidence | Protected routine evidence references/locator/supports; raw private bank fields and quotations are omitted. |
| POST /cases/{id}/lifecycle | Explicit owner/admin suspend/close/reopen, with reason and current head. |
| POST /cases/{id}/workflow and /notes | Attributed nonfinancial assignment/priority/target/follow-up/next action/escalation/notes; analyst operational authority does not grant financial role. |
| POST /cases/{id}/inspect | Explicit audited readiness/integrity observation, without creating Phase 4/5 authority. |
| GET /cases/{id}/history | Independent bounded record/proposal pages, immutable economic/recorded/actual known-at distinctions. |
| POST /report | Authorized bounded internal projection at explicit K/period/profile/currency/entity; no downloadable recovery artifact. |

The internal /recovery-ledger UI presents independent axes and exact labeled P/V/B/C/S/R/N/credit/cost values, unknowns, blockers, method/history detail, source mappings, preparation/approval, workflow and lifecycle. Viewers see no authority buttons; analysts prepare/operate without final money approval; owners/admins finalize. History and proposals paginate independently and show unresolved commit provenance explicitly. Server/database roles remain authoritative. Authenticated no-store server proxy routes whitelist paths/query keys, reject cross-origin writes and preserve Decimal strings/UUID identity.

Cases, reads, readiness and proposals never secretly evaluate/decide findings, generate/repair/review/export proofs, create ProofSuccessor, reprocess extraction or infer new reviewed facts. Where those authorities are missing, users use the existing explicit workflows separately. COMPLETE monetary proof is required where policy requires it; canonical JSON export and optional human review are not additional readiness prerequisites.

## Section 32 operational-limit traceability

Defaults are versioned engineering safeguards, not financial policy. Exceeding a limit yields a bounded error/retry, never amount/evidence truncation. RecoveryLimits in app/core/config.py loads FLA_RECOVERY_LIMITS; schema.Limits defines recovery-operations/1. DEFAULTS and the named assertions below resolve to full functions in [traceability](phase6-traceability.md).

| Approved limit | Setting / default | Enforcement | Automated assertion |
| --- | --- | --- | --- |
| Actual request JSON | request_bytes = 1048576 (1 MiB) | RecoveryBodyGuard counts real POST bytes; protected frontend proxy also bounds bytes | test_recovery_api.test_strict_request_boundary_and_unknown_fields; recovery-proxy test bounds actual bytes; DEFAULTS |
| Notes/reasons | text_chars = 4000 | Text Pydantic length and service.text_bounds for value/evidence/reasons | LIMIT[text_chars]; DEFAULTS |
| Original documents | documents = 50 | verified_sources/Budget.track union across the whole operation and multi-case page | LIMIT[documents]; SOURCES; DEFAULTS |
| Evidence bindings | bindings = 500 | proposal supported-leaf count; Budget.track union of proof and recovery source bindings | LIMIT[bindings]; DEFAULTS |
| Cumulative source-byte reads | source_bytes = 104857600 (100 MiB) | reused actual verify_source byte accounting on one Budget, including repeated capture/recheck | LIMIT[source_bytes]; existing proof canonical actual-source cumulative-limit test; DEFAULTS |
| Synchronous work | work_seconds = 25 | monotonic cumulative Budget plus remaining statement_timeout/lock_timeout before each ORM/raw SQL; safe rollback cleanup | SQL; DEFAULTS |
| Response/report content | response_bytes = 10485760 (10 MiB) | canonical result bounds and buffered RecoveryBodyGuard response; no partial body delivery | LIMIT[response_bytes]; DEFAULTS |
| History page | history_page = 100 | API Query and configurable Budget bound for record/proposal/root/case pages | PAGE; UI history pagination assertion; DEFAULTS |
| Complete aggregate population | projection_records = 10000 | full case+record report bound before totals, bounded publication and overlap/history scans | LIMIT[projection_records]; DEFAULTS |
| Tenant simultaneous operations | tenant_concurrency = 2 | shared PostgreSQL transaction advisory slots before organization waits; separate workers cannot multiply | SLOTS; DEFAULTS |
| Actor new financial authority / rolling minute | actor_operations_per_minute = 10 | shared PostgreSQL actor lock and immutable counted requests across tenants; database clock; semantic/request retries do not mint money | QUOTA; SEMQUOTA; DUP; DEFAULTS |

## Policy, financial and security review

[Complete traceability](phase6-traceability.md) maps every PD6-01–37, I01–22, R01–10, RW-01–56 and AC-01–50 to actual enforcement and specific automated assertions. All 56 worked examples have individually executed exact Decimal reference tests; race examples use independent connections. The mapping includes database/service/API/UI boundaries and 50 additional assertion references. Similar names alone do not establish coverage.

| Risk reviewed | Verified safeguard / residual limitation |
| --- | --- |
| Mixed revisions/current role loss | Eighteen two-order independent PostgreSQL race cases cover membership, finding, fact, packet, association, tax, party, B and closure; pinned old context or explicit denial, never mixed authority. |
| Duplicate money or exhausted budgets | Same-key/different-key simultaneous approval, independent competing payments/credits/reversals, semantic collision/alias and B/current-C floor tests; one semantic creation audit and exact shared remaining budgets. |
| Missing/forged audit or mutable history | Direct immutable/source mutations, forged journal, disabled shared guards, evidence appended after review and injected audit failure are rejected; financial/audit rollback is atomic. Privileged schema owners remain outside ordinary application guarantees. |
| Unavailable or changed source bytes | Actual original hash/size capture plus commit-bound recheck; tamper/loss/in-flight change tests. Protected routine evidence omits private raw fields. Human citations/discharge/legal meanings remain manual reviewer assertions. |
| Credit issuance / cash / tax / cost confusion | Pending versus R/N, VAT 108000−18000=90000, gross 50000/fee500/net49500, withholding unknown supported slice, one physical receipt, separate direct cost currency/status and explicit restoration tests. No automatic tax entitlement/net savings. |
| Wrong counterparty or financial basis | Exact reviewed dated supplier/customer/payer/payee/beneficiary relationships, no fuzzy/group inference; foreign/unknown/bundled/preexisting/paid-replacement gates. |
| Stale/dismissed/closed/successor authority | Historical facts preserved, ordinary positive authority blocked, negatives remain explicit, fresh readiness after reopen, existing-R successor reconciliation deferred. |
| Reporting fraud / partial totals | Actual committed-at K (including late commit), immutable date corrections, DST/date-only boundaries, unknown stock/receipt dates, full bounded population and separated currency/entity/exception metrics. |
| Scope/security regression | Existing Phase 4/5 code semantics/specifications unchanged; no-side-effect sentinels, full proof C01–C10/canonical/export/redaction regressions and negative deferred-route tests remain in complete CI. |

No production deployment, real OIDC-provider browser acceptance, penetration certification, enterprise load capacity, legal authenticity, accounting/regulatory compliance or tax recoverability is claimed.

## Preservation, limitations and deferred scope

Whole-file Phase 4 policy SHA-256: 1ee9eebf9ca81496f616c8bf55e64389341141762a501c3ec91fa654bb99fe09. Whole-file Phase 5 policy SHA-256: 1dac7eb8377322552e12cc0c87b49baaa60123e53938209bb7e98699415c6e2a. PD-01–07, PD5-01–14 and all PD6 Option A/alternative bodies, I01–22, R01–10, RW-01–56 and AC-01–50 are unchanged. Phase 6 specification changes are execution/status metadata only. Existing financial/proof services and canonical business calculations are untouched; earlier migration tests only extend excluded metadata when testing their historical schema versions.

Manual evidence meaning, economic duplicate/relationship/discharge interpretation and actual source availability remain operational responsibilities. No recovery-document AI/extraction, live bank/AP reconciliation or global legal-entity identity master is introduced. Routine source masking does not redact or mutate canonical evidence; recovery data is not inserted into existing redacted proof export envelopes. No new Recovery Ledger export workflow exists.

Synchronous organization serialization and shared safety limits bound throughput; some valid large cases/reports return explicit resource errors. Full production load tuning and monitored storage/runtime/provider infrastructure are deferred. PostgreSQL commit tracking must stay enabled; if a crash leaves provenance uncaptured until PostgreSQL removes that transaction metadata, the system cannot invent K and fails closed until an explicit future safe recovery policy. Already captured immutable receipts remain available under ordinary existing safeguards. This is not a universal retention period, legal hold or permanent-retention promise.

Currentness/integrity observations must be explicitly recorded to support historical eligible ratios; missing support is UNKNOWN. Contradictory physical source dates block affected period attribution. A genuine recovery can be known before its financial approval, but an unapproved event cannot enter authoritative R. Precise monetary/tax/quantum/beneficiary evidence can block recognition rather than being guessed.

Deferred: FX, bundled multi-finding settlements, recognized-history successor money transfer, avoided/annualized/forecast monetary savings, gain-share/billing, vendor/public communication/sharing, recovery exports/PDF/accounting journals/GL/ERP posting, live integrations, autonomous recognition/recovery automation, legal/tax interpretation, retention/erasure automation, Firewall, Leakage DNA and all later phases. No dormant alternate writable financial authority fields are introduced for them.

## Pushed checkpoints

| Milestone | Commit |
| --- | --- |
| A architecture | 8145b519db62d65cf5eb5c656fcdd6eaf845ca14 |
| B schema / migration | bb7091affd831e38c91ad3d9bf0f7fdbf6f5cf19 |
| B FK correction | 91234e49acbb260908504a157631b5b1a33b078a |
| C recognition services | dfc41c0b9c457e1505fb7311e48a6c78f4250e63 |
| D APIs / reporting | 91b18b6041a8da819bd2f22ee7e1513c8ba20980 |
| E frontend / proxy | 61826daf422bfc0a3221734a8928dbb2ffa93749 |
| F1 commit cutoff / authority | ffdcd07f50ca3ca9c3b1a4ff88a6523fa144aca2 |
| F2 financial references | c25a0c44f4ca8af13a2021cfdd8e44620e7131f7 |
| F3 independent races / audit origins | 86701d10ee48a19ce9bd6bc858cb4c81d105c658 |
| F4 rollback / shared bounds | 6ab7ef969a50e396e63dc03d31f0188a3b2d7e50 |
| F5 historic credit stock / guards | 1e9192530724e4e074fa9f3c6d9c002fa5eebf08 |
| F6 database-time quota / ambiguous receipts | 8936e0ed4ac69d5f17bdfca8afb9ed303a4f2f17 |
| F7 cost/precision/quota retry review | 98c652beedefa1b46aa6464e594059ba0fff14b5 |
| F8 instrument/case authority | 9e536b47bcfecb77c3bc5a7913cfb59a13b9b292 |

The final documentation/validation checkpoint and exact head are the delivery commit shown by the PR. Do not merge automatically or begin another phase.
