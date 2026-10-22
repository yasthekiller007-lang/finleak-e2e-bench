# Phase 4 V1 — Validation and implementation report

Updated 3 October 2026. The authorized Leakage Compiler and Contract-to-Invoice Engine implementation is complete on `phase4/leakage-compiler-engine`; it is ready for review, not automatically merged. Main remains `e1bdae347bfe6d9b8d7c9b92ec8efc3e723943a1`. No Phase 5/6 implementation has started. The approved financial policy remains [phase4-business-spec.md](phase4-business-spec.md), PD-01 through PD-07. The specification edits in this branch update execution/status wording only.

## Verified execution and validation

Complete code checkpoint: `a6cfc1ee10b0e9887a7511e9b0f336c75f4b8f34`.

Authoritative full PostgreSQL 17.11 CI: [run 37089925623](https://github.com/yasthekiller007-lang/financial-leakage-ai/actions/runs/37089925623). Backend job `111107891212` and frontend job `111107891057` both completed successfully. Backend: **386 passed**, zero failures/skips, including all retained Phase 1–3 tests and 113 added Phase 4 cases. Frontend: **62 passed**, including the previous 46 and 16 new cases. The final documentation follow-up is also checked by the same complete branch workflow before the review PR is opened; its exact head and review URL are supplied in the final delivery.

| Validation | Local Work | Authoritative GitHub CI |
| --- | --- | --- |
| Locked dependencies | Existing locked installations | `uv sync --locked`, `npm ci` passed |
| Backend Ruff lint / format | Passed | Passed |
| Backend suite | 222 passed, 164 PostgreSQL skips | **386 passed**, zero skips/failures |
| Backend standalone type checker | None configured | None configured; typed schemas and Ruff are used |
| Frontend lint / format / TypeScript | Passed | Passed |
| Frontend tests / production build | 62 passed; build passed | **62 passed**; build passed |
| Alembic upgrade through 0004 | No local PostgreSQL service | Passed |
| Full schema drift | No local PostgreSQL service | Passed; no new upgrade operations |
| Disposable downgrade/base → reupgrade/head | No local PostgreSQL service | Passed |
| Schema drift after reupgrade | No local PostgreSQL service | Passed; no new upgrade operations |
| Populated migration preservation / refusal of destructive downgrade | PostgreSQL suite only | Passed |
| Phase 3 synthetic extraction benchmark | Passed | Passed, unchanged results below |
| Secret-pattern scan | 160 source files, zero findings at code checkpoint with architecture draft | 159 committed source files, zero findings at code checkpoint |
| Git whitespace / artifact checks | `git diff --check` passed | No credentials, `.env`, generated builds or downloaded database artifacts committed |

Local PostgreSQL skips are explicitly not full database validation. Work's existing PostgreSQL initialization restriction was respected; no SQLite substitution or unsafe workaround was used. No application validation server was started during this implementation. GitHub cleaned up its disposable PostgreSQL container. Existing security and financial invariants were retained; failed CI checkpoints were corrected before this passing run. In particular, the real-extraction workflow uses a supported labeled CSV and asserts genuine extracted-field lineage, and standalone discount-base testing uses its own approved scope rather than silently disregarding a revoked price.

The retained 16-document extraction benchmark reports 73/73 required-field checks, zero fabricated values among 571 absent fields, 9/9 invoice-line checks, 7/7 pricing-entry checks and 128/128 evidence checks. These are synthetic supported-template regressions, not a claim of real enterprise accuracy.

## Required 32-point implementation report

| # | Item | Implemented state and evidence |
| --- | --- | --- |
| 1 | Starting main | `e1bdae347bfe6d9b8d7c9b92ec8efc3e723943a1`, verified clean with merged Phases 1–3 and approved specification PR #4 before coding. Remote main was rechecked after successful CI. |
| 2 | Final branch | `phase4/leakage-compiler-engine`; no direct main commits or automatic merge. |
| 3 | Final commit | Complete code checkpoint `a6cfc1ee10b0e9887a7511e9b0f336c75f4b8f34`; the final documentation commit SHA is reported in the delivery/PR. Local Git objects are checked against the exact GitHub tree/commit, not merely file counts. |
| 4 | Architecture | Stable reviewed financial sources, immutable approval history, pure typed compiler/arithmetic, PostgreSQL authority service, protected API and enterprise UI. See [architecture](phase4-architecture.md). |
| 5 | Database models | `ReviewedFinancialSource`, `FinancialRevision`, `FinancialRevisionEvidence`, `FinancialEvaluation`, `FinancialFindingDecision`, `FinancialAudit`. Existing ExtractedField gains a composite lineage uniqueness key; existing Contract/Invoice entities are not forced into incomplete financial truth. |
| 6 | Migration | `0004_reviewed_financial_engine.py`: frozen PostgreSQL DDL, tenant-safe composite foreign keys, revision/request/fingerprint uniqueness, exact NUMERIC(20,6), immutability, authority/audit/document guards and non-destructive downgrade refusal. |
| 7 | Approval | Analysts prepare evidence-backed reviews. Owner/admin approve, correct or revoke/withdraw using expected predecessors and UUID request keys. Viewers read only. Original machine and reviewed values, reason, uncertainty, cutoff, actor/time and lineage remain available. |
| 8 | Governing packet | Approved master/amendment/schedule/exhibit/exception documents with hashes, bounded scopes and period, explicit open-ended meaning and known-missing material. Missing relevant material blocks; revisions never rewrite old evaluations. |
| 9 | Matching | One master per invoice; approved exact reference, explicit approved PO relationship, or source-backed manual association. Strong conflicts block; supplier/entity/date/scope similarity yields review candidates only. |
| 10 | Compiler | Pure `app/financial/engine.py` consumes typed approved meanings and deterministic term-specific supersession. Missing/ambiguous/unsupported semantics return stable blockers. Versions: `reviewed-compiler/1`, `core-bundle/1`, `financial-snapshot/1`. |
| 11 | R1 | Fixed contracted unit price × compatible billed quantity compared with reconciled pre-tax billed amount, including explicit allocated reductions and approved rounding. F02 returns exactly 74,199.90. |
| 12 | R2 | Fixed fee for one approved complete cycle/event. No inferred calendar/day proration. F06 returns 400; F07 is assessed no-overcharge. |
| 13 | R3 | Explicit unconditional percentage applied only to complete approved eligible contractual base. Governing-source evidence is required for a standalone base. F04 returns 4,000. Combined price/discount F27 returns one 300 finding. |
| 14 | Snapshot | Immutable fenced revisions, calculation-driving revision IDs, source hashes and candidate/review lineage, packet, match, economic date, credits/tax/rounding decisions, exact calculation trace, reasons and behavior versions. |
| 15 | Idempotency | Canonical scoped semantic fingerprint plus tenant/fingerprint unique key; simultaneous identical requests produce one evaluation and one creation audit. Review retries reuse source/revision identity; changed material meaning gets a new evaluation. |
| 16 | Revision/staleness | Expected-revision compare-and-set, organization transaction lock and commit-time reread/hash checks. Old evaluations remain unchanged. Current eligibility is derived; disjoint reviews and filename changes do not reopen dismissed findings. |
| 17 | Blocked model | Persisted `NEEDS_REVIEW` with reason and null monetary values, including unapproved/revoked/material pending reviews. Stale attempts return controlled `409 STALE_INPUT`; zero is reserved for assessed no-overcharge discrepancy. |
| 18 | APIs | Tenant-scoped sources, current review context, history, review writes, compile, evaluate, evaluation list/detail, finding decisions, summary and audit under `/api/v1/organizations/{organization_id}/financial`. Bounded pagination and source evidence checks apply. |
| 19 | Frontend | Authenticated dashboard/register, review forms, packet/association preparation, owner/admin approval/revocation/assessment, stale/blocked labels, protected details and evidence/calculation views. Server-only token proxy enforces allowlisted routes, origin and payload limits. |
| 20 | Executive summary | Current undismissed non-overlapping potential by currency/rule bundle with assessed, blocked, stale and dismissed counts. Aggregates are views, not extra findings. Unknown amounts remain unknown; undercharges are separate, not netted; no recovery or guaranteed-savings claim. |
| 21 | Security | Current membership and roles rechecked/locked at action time; tenant-safe queries and composite FK evidence/association boundaries; source hash integrity; immutable authority and trigger-generated audit; no monetary edit endpoint or client-side role trust. |
| 22 | Backend tests | 386 passed in PostgreSQL CI, including 67 pure compiler/Decimal cases and API, authorization, immutable audit, lifecycle, migration and concurrent-transaction tests. All earlier suites remain present. |
| 23 | Frontend tests | 62 passed across eight files. Review roles, decisions/predecessors, blocked coverage, evidence/financial display and proxy security are covered; lint, format, TypeScript and build pass. |
| 24 | PostgreSQL CI | Full PostgreSQL 17.11 run 37089925623 succeeded on the exact complete code checkpoint. Concurrent approval/revocation, governing-packet revision, association revocation, duplicate/same-scope evaluations and stale attempts are exercised using independent transactions. |
| 25 | Migration validation | Upgrade, schema drift, disposable downgrade/reupgrade and second drift all passed. Integration tests preserve legacy data, cover full schema lineage and reject populated financial-history downgrade. |
| 26 | Golden financial regression | All 35 approved vector identifiers are represented: 34 pure-rule/core-or-blocked cases plus F20 real matching in PostgreSQL, with F32's second segment and parent allocation reconciliation tested separately. Coverage is mapped below. |
| 27 | Exact Decimal | Decimal strings only; floats/bools/nonfinite/excess scale rejected, bounded 80-digit context traps unintended inexact operations, fractional/large products retained, explicit quantum/stage/mode, invariant alternatives allowed, one positive cent retained and NUMERIC overflow blocked. |
| 28 | False positives | Unsupported tiers/surcharges/conditional discounts/minimums, missing packet/amendments, ambiguous match/precedence, currency/unit/date conflicts, unresolved credits, allocation gaps and actual reconciliation conflicts return null blockers. Forecast quantity alone produces no finding. |
| 29 | Limitations | Human source attestation, labeled extraction, serialized tenant throughput, bounded UI/source selectors and summary, richer authoring through typed API, credit-bearing period allocation blocked, no real-provider browser acceptance or production deployment. See architecture for exact bounds. |
| 30 | Deferred families | Tier/volume, surcharge/unauthorized-fee, conditional/early-payment discounts, minimum/take-or-pay, CPI/FX/SLA/rebates/tax interpretation, complex proration, cross-invoice/period credits, duplicate payment, SaaS discovery and recovery. No Proof Engine, Recovery Ledger, Firewall or Leakage DNA. |
| 31 | HANDOFF | Updated merged main/specification status, current implementation/CI, startup, reviewed authority, migration/audit, limitations and stop boundary. Specification metadata updated without changing policy or vectors. Historical Phase 3 reports remain historical. |
| 32 | Pull request | Review PR targets main and summarizes architecture, database, supported/deferred rules, security, tests, migrations and limitations. Its exact URL and final head are supplied in the final delivery. It is not merged automatically. |

## Approved golden-vector mapping

`backend/tests/test_financial_engine.py::test_approved_financial_vectors` checks exact Decimal discrepancies and null blocked outcomes. `backend/tests/test_financial_api.py` exercises F20 matching, real extraction/review/evaluation lineage and standalone contractual-base evidence; the concurrency and migration suites use PostgreSQL rather than mocks.

| Vector | V1 result | Test meaning |
| --- | --- | --- |
| F01 | NO_OVERCHARGE, 0 | Correct fixed unit price |
| F02 | POTENTIAL_LEAKAGE, 74,199.90 | (20.10 − 18.40) × 43,647 |
| F03 | UNDERCHARGE, −100; no potential | Cheaper billed unit price |
| F04 | POTENTIAL_LEAKAGE, 4,000 | 8% of eligible 50,000 contractual base |
| F05 | NO_OVERCHARGE, 0 | Correct 8% discount |
| F06 | POTENTIAL_LEAKAGE, 400 | Complete fixed fee 5,400 versus 5,000 |
| F07 | NO_OVERCHARGE, 0 | Correct fixed fee |
| F08 | Blocked, null | Deferred tier profile |
| F09 | Blocked, null | Deferred tier profile |
| F10 | Blocked, null | Deferred tier profile |
| F11 | Blocked, null | Deferred tier profile |
| F12 | POTENTIAL_LEAKAGE, 100 | Approved amendment effective before service |
| F13 | POTENTIAL_LEAKAGE, 200 | Service date retains applicable old price despite later invoice date |
| F14 | Blocked, null | Interval crosses price change without source allocation |
| F15 | Blocked, null | Currency mismatch |
| F16 | Blocked, null | Missing billed quantity |
| F17 | Blocked, null | Unresolved conflicting approved terms |
| F18 | Blocked, null | Deferred credit/financial profile |
| F19 | NO_OVERCHARGE, 0 | Allocated same-scope fee reduction |
| F20 | Blocked, null | Multiple candidate masters; supplier similarity does not approve a match |
| F21 | NO_OVERCHARGE, 0 | Allocated credit applied once |
| F22 | Blocked, null | Deferred prohibited-fee profile |
| F23 | Blocked, null | Deferred percentage surcharge |
| F24 | NO_OVERCHARGE, 0 | Comparable pre-tax base; tax is not leakage |
| F25 | Blocked, null | Retroactive applicability not approved |
| F26 | Blocked, null | Rounding alternatives change financial outcome |
| F27 | One POTENTIAL_LEAKAGE, 300 | Combined unit price plus discount without double counting |
| F28 | Blocked, null | Conditional early-payment discount |
| F29 | Blocked, null | Term expired before applicable service |
| F30 | Blocked, null | Incompatible unit |
| F31 | Blocked, null | Deferred minimum profile |
| F32 | Segment findings 320 + 60; aggregate view 380 | Approved allocated periods, reconciled to parent; no third finding |
| F33 | POTENTIAL_LEAKAGE, 200 | Eligible SKU base excludes unrelated 300 fee |
| F34 | Blocked, null | Posted amount conflicts with billed calculation |
| F35 | NO_OVERCHARGE, 0 | Forecast overrun is not contractual quantity authority |

Additional cases cover complete invariant rounding alternatives, component-versus-scope reconciliation, unknown versus explicitly open-ended dates, current review/role races, stale packets and approvals, relevant unallocated credits, missing known material, cross-tenant extracted lineage, prepared-review withdrawal, reapproval retries, historical monetary immutability and direct audit forgery rejection.

## Operational and review boundary

The implementation is a deterministic V1 with human-reviewed source meanings, not autonomous interpretation of arbitrary contracts. Supporting document presence and high extraction confidence never grant monetary authority. There is no production deployment, proof dossier, recovery workflow or recovered-value metric. Production database roles must not be schema owners or able to disable financial integrity triggers. Real OIDC-provider browser acceptance, broader extraction, operational storage/security controls and richer bulk review remain separately required.

Main is unchanged. Review this branch and its complete CI; do not automatically merge it or start Phase 5. The final delivery records the exact final branch SHA, verified clean tree and review PR URL.
