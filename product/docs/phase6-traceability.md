# Phase 6 V1 policy-to-code traceability

Business authority: [approved version 1.0](phase6-recovery-ledger-spec.md). All 37 Option A decisions remain unchanged. This is implementation evidence, not new policy.

Layer notation: DB = immutable/composite-FK/authority/audit triggers and PostgreSQL locks; S = backend service/schema/arithmetic/reporting; API = authentication, tenant routing and transport guards; UI = presentation and explicit commands. Source-byte meaning and actual filesystem capture are service responsibilities; the database cannot certify quotations or physical bytes. Financial/security authority does not depend on UI enforcement.

RW references below resolve to one individually executed test and the exact assertion intent in the worked-example table. Other uppercase references resolve to full test function names in the assertion index. These mappings were reviewed against assertions and service gates, not inferred from similar test names. PostgreSQL cases use isolated schemas and real commits; races use independent sessions/connections.

## Approved product decisions

| Requirement | Enforcement component / layer | Automated assertion references |
| --- | --- | --- |
| PD6-01 | create_case/authority; case uniqueness and positive guard (DB/S) | RW-22, RW-23, RW-24, RW-25, RW-26, RW-01 |
| PD6-02 | finding_state/readiness B gates; projection V (DB/S) | RW-11, BASIS |
| PD6-03 | RecoveryCase tenant/evaluation uniqueness; root identity_hash/aliases (DB/S) | RW-32, RW-34, ALIAS |
| PD6-04 | operational/lifecycle; independent projection axes (S/API/UI) | RW-01, RW-09, RW-48 |
| PD6-05 | approve realization; all recognition gates and source capture (DB/S/API) | RW-01, RW-02, RW-27, AUDIT |
| PD6-06 | explicit amount and remaining B/root budgets (DB/S) | RW-02, RW-06, CASHROOT |
| PD6-07 | strict supported method schemas and method gates (DB/S) | RW-07, RW-18, PREEXIST |
| PD6-08 | credit_balance/pending_credit; actual application/stock/reconciliation (S) | RW-03, RW-04, RW-05, RW-17, RESTORE, EXPIRY, ROOTCASE |
| PD6-09 | request/economic reference identity and append-only signed balances (DB/S) | RW-16, RW-34, DUP, REF |
| PD6-10 | linked negative/replacement budgets, immutable history (DB/S) | RW-31, RW-56, REV, IMM |
| PD6-11 | vendor proposals and party gate; explicit nullable positions (S/UI) | RW-09, RW-10, CLAIMS, VDATE |
| PD6-12 | claim gate, latest effective revision projection (S) | RW-08, RW-11, CLAIMS, BASIS, CLAIMQ |
| PD6-13 | inert nonfinancial observation/note; strict schema excludes forecast money (S/API/UI) | RW-18, RW-19, RW-20 |
| PD6-14 | no forecasting monetary field/method; notes are inert (S/API/UI) | RW-21, BOUNDARY |
| PD6-15 | original instrument/cost currencies, allocation compatibility (S/API) | RW-28, RW-50 |
| PD6-16 | SETTLEMENT/shared case gate; no multi-finding allocation model (S) | RW-29, RW-30 |
| PD6-17 | explicit principal/tax/extras then budget checks; no min cap (DB/S) | RW-40, RW-41, RW-54 |
| PD6-18 | financial.is_stale; explicit existing ProofSuccessor retire; no recognized-history transfer (S) | RW-13, RW-14, RW-39, AUTH |
| PD6-19 | current dismissal case gate; INVALIDATED_BASIS projection (DB/S) | RW-12, RW-56 |
| PD6-20 | owner lifecycle CAS and fresh readiness after reopening (DB/S/API/UI) | RW-15, RW-31, RW-32 |
| PD6-21 | fresh organization/membership fence, final-role triggers, own note revisions (DB/S/API/UI) | RW-36, RW-37, NOTE, AUTH |
| PD6-22 | immutable reviewed mapping + actual protected bytes + source pins (DB/S/API) | RW-27, RW-38, RW-55, EVIDENCE |
| PD6-23 | projection/report separated dimensions, complete matched populations (S/UI) | RW-02, RW-12, RW-28, RW-42, UNKNOWN, KCREDIT |
| PD6-24 | strict schema/routes exclude all gain-share monetary authority (S/API/UI) | RW-21, BOUNDARY |
| PD6-25 | internal action observations only; proxy whitelist and no external endpoints (API/UI) | RW-09, RW-48, BOUNDARY |
| PD6-26 | recovery_document_guard/immutable history, honest availability overlay (DB/S) | RW-38, IMM, DOWN, GUARD |
| PD6-27 | Limits, Budget, SQL timeout hook, shared PG admission/quota/body guard (S/API/DB locks) | DEFAULTS, LIMIT, PAGE, SOURCES, SQL, SLOTS, QUOTA |
| PD6-28 | Components explicit tax basis; compatible exclusive allocation (DB/S) | RW-41, RW-42, TAX, TAXBAD, UNKNOWN |
| PD6-29 | separate gross/principal/deductions/net; physical receipt projection (S/UI) | RW-43, RW-44, CASHROOT, DATECONFLICT |
| PD6-30 | scoped dated Party approvals/revocations, exact supplier/customer matches (S) | RW-45, RW-46, RW-47, RW-53, PARTY, VDATE |
| PD6-31 | operational workflow/notes, tenant member assignment; no money side effects (S/API/UI) | RW-48, NOTE, SIDE |
| PD6-32 | explicit commercial closure reasons, no finding dismissal (S/API/UI) | RW-49, RW-15 |
| PD6-33 | direct cost root identity, currency and incurred/paid/reversed budgets (S) | RW-50, RW-43, COSTFIX |
| PD6-34 | actual PostgreSQL commit publication K, source economic dates, date corrections (DB/S) | RW-51, RW-52, K, KCOMMIT, KCREDIT, TIME, DST |
| PD6-35 | protected upload/manual reviewed bindings; no ingestion/integration (S/API) | PAGE, RW-27, RW-47, BOUNDARY |
| PD6-36 | organization/membership fences, CAS/pins, semantic/request dedup, atomic audit (DB/S) | DUP, REV, CREDIT, AUTH, AUDIT, RW-54, RW-55 |
| PD6-37 | Money/NUMERIC(20,6), context80 Decimal, explicit quantum, ratio-only rounding (DB/S/UI) | RW-33, DECIMAL, PRECISION, TIMEEDGE |

## Domain invariants

| Requirement | Enforcement component / layer | Automated assertion references |
| --- | --- | --- |
| I01 | projection never advances P/V/B/C/S/R from another dimension (S/UI) | RW-01, RW-09, CLAIMS |
| I02 | Recovery module consumes immutable FinancialEvaluation, never edits it (DB/S) | SIDE, RW-07, RW-19 |
| I03 | stale/successor gates require existing explicit Phase4/5 workflows (S) | RW-39, SIDE |
| I04 | authority separately checks confirmed/COMPLETE/party/B (S) | RW-25, RW-26, RW-01 |
| I05 | one instrument credit budget across methods; physical versus attributed stock (S) | RW-03, RW-17, CREDIT, RESTORE |
| I06 | strict schema/deferred methods; notes inert (S/API/UI) | RW-18, RW-20, RW-21 |
| I07 | evidence_gate and actual completed method checks (DB/S) | RW-09, RW-27, PREEXIST |
| I08 | lifecycle reason independent of finding/realized dimensions (S/UI) | RW-15, RW-49 |
| I09 | vendor position revisions cannot decide/evaluate a finding (S) | RW-09, RW-10, SIDE |
| I10 | nullable Components/projection coverage and compatibility gates (S/UI) | RW-28, RW-42, RW-44, UNKNOWN |
| I11 | currency/customer/tax filter plus overlap exclusion (S) | RW-28, RW-29, RW-41, RW-50 |
| I12 | explicit realized principal, no capped/proportional bundled allocation (S) | RW-29, RW-30, RW-40 |
| I13 | eight immutable tables, protected sources, trusted atomic audit (DB/S) | IMM, EVIDENCE, AUDIT, DOWN |
| I14 | unique case/evaluation and explicit retirement/recognized-history block (DB/S) | RW-32, RW-34, RW-14, RW-39 |
| I15 | current roles, composite tenant FKs, original byte capture and audited pins (DB/S/API) | RW-37, RW-55, AUTH, GUARD |
| I16 | original outstanding reversal budget; no cash from cancelled issuance (DB/S) | RW-05, RW-56, REV |
| I17 | explicit unused B/instrument/physical-credit budgets (DB/S) | RW-54, BASIS, CREDIT, PREEXIST |
| I18 | Components bridge and separate projection R/N/F/S (S/UI) | RW-08, RW-43, RW-44, RW-50 |
| I19 | server actual commit receipts and immutable economic correction lineage (DB/S) | RW-51, RW-52, KCOMMIT, KCREDIT |
| I20 | operational appends cannot change monetary fields or roles (S/API/UI) | RW-48, NOTE, SIDE |
| I21 | ordinary protected references/integrity; no new erasure/permanence workflow (DB/S/API) | RW-38, IMM, BOUNDARY |
| I22 | explicit count/byte/time busy results, full population bound (S/API) | LIMIT, SOURCES, SQL, SLOTS, QUOTA, PAGE |

## Recognition gates evaluated together

| Requirement | Enforcement component / layer | Automated assertion references |
| --- | --- | --- |
| R01 | create_case, positive_gate, exact current ready/lifecycle/case CAS (DB/S) | RW-22, RW-24, RW-26, RW-32, AUTH |
| R02 | authority pins actual decision/evaluation/scope; B gate (DB/S) | RW-11, RW-13, BASIS, AUTH |
| R03 | authority/proof.assert_package/verified_sources (S; DB proof/FK checks) | RW-25, RW-26, RW-38, RW-55, PROOF |
| R04 | party_gate with exact dated payer/payee/beneficiary association (S) | RW-45, RW-46, RW-47, RW-53, PARTY, VDATE |
| R05 | identity_hash/alias, instrument review origin, physical unused stock (DB/S) | ALIAS, REF, NAMESPACE, PREEXIST, RW-17 |
| R06 | strict completed method schema + settled/applied/unpaid discharge checks (DB/S) | RW-07, RW-09, RW-27, PREEXIST |
| R07 | Components/currency/quantum/source-backed principal gates (DB/S) | RW-28, RW-41, RW-44, TAXBAD, DECIMAL |
| R08 | explicit allocation then unused signed B/root/credit checks (DB/S) | RW-54, RW-40, BASIS, CREDIT |
| R09 | execute membership/organization fence, prepared head + source rechecks (DB/S/API) | AUTH, RW-55, DUP, EVIDENCE |
| R10 | append signed immutable event and trusted audit; one semantic creation (DB/S) | AUDIT, IMM, REV, DUP |

## Acceptance criteria

| Requirement | Enforcement component / layer | Automated assertion references |
| --- | --- | --- |
| AC-01 | create_case positive/dismissed guards (DB/S) | RW-22, RW-23, RW-24, RW-12 |
| AC-02 | investigation vs authority/COMPLETE gates (S/UI) | RW-25, RW-26, RW-13 |
| AC-03 | actual decision-derived V, explicit B bounds (DB/S) | RW-11, BASIS |
| AC-04 | case uniqueness/idempotency/lifecycle independent of proof identity (DB/S) | RW-32, RW-34, ALIAS |
| AC-05 | orthogonal projection and operational actions (S/UI) | RW-01, RW-09, RW-48 |
| AC-06 | strict completed method proposal and exact allocation/source pins (DB/S) | RW-01, RW-02, RW-27, TAX |
| AC-07 | supported methods, paid-original gate; nonfinancial consideration (S) | RW-07, RW-18, PREEXIST |
| AC-08 | pending_credit and credit_balance one-root consumption (S) | RW-03, RW-04, RW-17, CREDIT, CASHROOT, ROOTCASE |
| AC-09 | credit_state and linked reversals/restoration; expiry explicit (S) | RW-05, RESTORE, EXPIRY |
| AC-10 | stable namespace/ref identity and semantic collision checks (DB/S) | RW-16, RW-34, REF, NAMESPACE, ALIAS |
| AC-11 | immutable record/source triggers and original reversal bound (DB/S) | RW-31, RW-56, IMM, REV |
| AC-12 | negative exception vs current positive gate, no fabricated cash (S) | RW-31, RW-56, AUTH |
| AC-13 | explicit nullable vendor positions and conditional raw coverage (S/UI) | RW-08, RW-09, RW-10, CLAIMS |
| AC-14 | latest claim stock; draft/withdrawn/revised history, never external send (S) | RW-08, CLAIMS, BOUNDARY |
| AC-15 | inert observed later billing and forbidden monetary scenarios (S/API) | RW-18, RW-19, RW-20, SIDE |
| AC-16 | strict no annualized forecast financial field (S/API/UI) | RW-21, BOUNDARY |
| AC-17 | currency-specific roots/costs/report filters; no writable FX (S/API) | RW-28, RW-50 |
| AC-18 | shared SETTLEMENT/related_cases positive gate (S) | RW-29, RW-30 |
| AC-19 | component-evidenced principal/extras before exact B cap (DB/S) | RW-40, RW-41 |
| AC-20 | financial currentness under org fence; historic overlay (S) | RW-13, AUTH |
| AC-21 | existing ProofSuccessor only; recognized-history transfer deferred (S) | RW-14, RW-39 |
| AC-22 | current dismissal gate and INVALIDATED_BASIS history (DB/S) | RW-12, RW-56 |
| AC-23 | explicit role/reason lifecycle; fresh post-reopen ready (S/API) | RW-15, RW-32, RW-49 |
| AC-24 | fresh final-role service/trigger; own note and workflow (DB/S/API/UI) | RW-36, RW-48, NOTE, RW-01 |
| AC-25 | fresh membership held across independent approval transactions (DB/S) | AUTH, DUP |
| AC-26 | actual bytes/source-manifest/mapping/recheck (DB/S) | RW-27, RW-38, RW-55, EVIDENCE |
| AC-27 | complete matched report denominator, no overlapping active scopes (S) | RW-02, RW-08, RW-12, RW-14, RW-28, RW-52 |
| AC-28 | nullable components/money, pending stock vs R/N, exception categories (S/UI) | RW-03, RW-42, RW-43, RW-44, UNKNOWN |
| AC-29 | strict internal API/proxy boundary; existing proof exports untouched (API/S) | BOUNDARY, SIDE, RW-21, REDACTION |
| AC-30 | referenced Document guard/immutable history; availability overlay (DB/S) | RW-38, IMM, DOWN, GUARD |
| AC-31 | section32 exact defaults and cumulative/shared bounds (S/API/PG locks) | DEFAULTS, LIMIT, PAGE, SOURCES, SQL, SLOTS, QUOTA |
| AC-32 | explicit tax bridge/exclusive principal only, no entitlement inference (DB/S) | RW-41, RW-42, TAX, TAXBAD, UNKNOWN |
| AC-33 | gross before cost qualified R and separately retained net cash (S/UI) | RW-43, TAX, CASHROOT |
| AC-34 | explicit supported principal slice, unresolved withholding coverage (S) | RW-44, UNKNOWN |
| AC-35 | dated exact associations and explicit agency/continuity/beneficiary (S) | RW-45, RW-46, RW-47, RW-53, PARTY, VDATE |
| AC-36 | operational member assignment/escalation/notes never money or role (S/API/UI) | RW-48, NOTE, SIDE |
| AC-37 | explicit commercial reasons retain finding truth and U (S/UI) | RW-49, RW-15 |
| AC-38 | cost identity/currency/incurred/paid/reversal separated from R/N (S) | RW-50, RW-43, COSTFIX |
| AC-39 | each economic date drives stock/flow independently of entry time (S) | RW-51, RW-52, KCREDIT |
| AC-40 | actual publication commit K, selected IDs/digest/high-watermark (DB/S) | RW-52, K, KCOMMIT, KCREDIT |
| AC-41 | source DATE/INSTANT/LOCAL semantics; boundary ambiguity blocks (S) | TIME, DST, TIMEEDGE, DATECONFLICT |
| AC-42 | manual protected reviewed mapping; source instructions inert (S/API) | RW-27, RW-47, PAGE, BOUNDARY |
| AC-43 | UUID and semantic repeat/collision behavior, one creation audit (DB/S) | RW-34, RW-35, DUP, REF, ALIAS, SEMQUOTA |
| AC-44 | locked B/instrument/credit budgets vs competing updates (DB/S) | RW-54, AUTH, CREDIT, BASIS |
| AC-45 | all authority revisions and actual byte rechecks share fence (DB/S) | AUTH, RW-55, PARTY, TAXBAD |
| AC-46 | negative outstanding budget and atomic trigger journal (DB/S) | RW-31, RW-56, REV, AUDIT |
| AC-47 | Money/Decimal/NUMERIC(20,6), explicit quantum, display-only ratio rounding (DB/S/UI) | RW-33, DECIMAL, PRECISION |
| AC-48 | tenant query/FKs/error isolation, private routine evidence, unchanged redaction (DB/S/API/UI) | RW-37, RW-53, REDACTION |
| AC-49 | trusted actor/role/reason/predecessor trigger audit and enabled-guard checks (DB/S) | AUDIT, IMM, GUARD, RGUARD, DUP |
| AC-50 | no Phase4/5 service edits; monkeypatched no-side-effect tests plus existing full regressions (DB/S) | SIDE, PROOF, REDACTION, RW-07, RW-19, RW-24, RW-29, RW-39 |

## Worked examples: individually executed financial references

Every test below uses protected upload/review/evaluation/proof APIs and exact Decimal assertions. Expected values are taken from the approved worked examples, not from the implementation calculator. Negative cases assert blocked authority or unchanged/null money. Common stable/evidence fixtures do not replace the individual assertions.

| Example | Test in backend/tests/test_recovery_worked_examples.py | Concrete assertion intent |
| --- | --- | --- |
| RW-01 | `test_RW01_full_cash` | R=50000, U=0; C/S absent, lifecycle remains OPEN |
| RW-02 | `test_RW02_partial_cash` | R=30000, U=20000, ratio=60.00; D absent |
| RW-03 | `test_RW03_credit_issue` | Pending=20000, R=0; N null |
| RW-04 | `test_RW04_credit_applied` | Applied credit R=20000, pending=0; N null |
| RW-05 | `test_RW05_credit_reversal_and_unused_cancellation` | R=15000/U=35000; cancellation of unused credit changes no R |
| RW-06 | `test_RW06_offset_later_invoice` | Offset R=12000, pending=8000, U=38000 |
| RW-07 | `test_RW07_unpaid_replacement_liability` | Unpaid liability 120000−70000=50000; R=50000/P unchanged/N null |
| RW-08 | `test_RW08_settlement_separate_from_performance` | Settlement/claim separated from approved supported performance; exact residual |
| RW-09 | `test_RW09_acknowledgment_is_not_cash` | S=50000, R=0; finding decision unchanged |
| RW-10 | `test_RW10_dispute_is_not_false_positive` | Explicit dispute retained; no false-positive transition |
| RW-11 | `test_RW11_confirmation_withdrawal` | Withdrawn confirmation removes current V/READY without editing P |
| RW-12 | `test_RW12_dismissal_preserves_receipt` | Dismissal keeps historical R and INVALIDATED_BASIS exception; ratio null |
| RW-13 | `test_RW13_stale_basis` | Revised fact makes stale; old R retained, new authority frozen |
| RW-14 | `test_RW14_explicit_unused_successor` | Explicit unused predecessor retirement enables successor B=45000; old blocked |
| RW-15 | `test_RW15_partial_commercial_closure` | Commercial CLOSED still R=30000/U=20000 |
| RW-16 | `test_RW16_distinct_refunds` | 20000+15000=35000 R/N; U=15000 |
| RW-17 | `test_RW17_one_root_application_and_cash` | 12000 applied+8000 cash consumes 20000 root once; extra cent denied |
| RW-18 | `test_RW18_future_price_correction_not_money` | Future price correction note leaves actual R unchanged |
| RW-19 | `test_RW19_later_invoice_observation` | Later corrected invoice note does not quantify avoided R |
| RW-20 | `test_RW20_forecast_deferred` | Forecast monetary proposal rejected; attributed note not recovery |
| RW-21 | `test_RW21_annualization_deferred` | Annualization arithmetic exact; no annualized writable financial authority |
| RW-22 | `test_RW22_undercharge_no_case` | UNDERCHARGE evaluation cannot create a monetary case |
| RW-23 | `test_RW23_no_overcharge_no_case` | NO_OVERCHARGE evaluation cannot create a monetary case |
| RW-24 | `test_RW24_blocked_assessment_no_case` | BLOCKED assessment cannot create monetary identity; unknown remains null |
| RW-25 | `test_RW25_incomplete_proof_no_ready` | INCOMPLETE exact proof permits investigation but no B/READY |
| RW-26 | `test_RW26_complete_unconfirmed_not_validated` | COMPLETE unconfirmed proof still V/B null |
| RW-27 | `test_RW27_source_free_claim_is_not_authority` | Source-free claim cannot get financial approval |
| RW-28 | `test_RW28_foreign_currency_no_fx` | EUR receipt cannot allocate against USD finding; R=0/ratio null |
| RW-29 | `test_RW29_explicit_bundle_allocation_deferred` | Explicit two-finding SETTLEMENT remains unallocated |
| RW-30 | `test_RW30_ambiguous_bundle_no_cap_first` | Unknown bundle no min/cap-first allocation; U/ratio null |
| RW-31 | `test_RW31_reversal_closed` | Closed case accepts supported linked negative; original/history retained |
| RW-32 | `test_RW32_reopen_same_case_requires_fresh_ready` | Reopen keeps same case and demands a fresh readiness approval |
| RW-33 | `test_RW33_one_cent_exact` | One-cent R exact; no materiality suppression |
| RW-34 | `test_RW34_semantic_retry` | Repeated semantic realization returns same record identity |
| RW-35 | `test_RW35_concurrent_same_proposal` | Independent concurrent same proposal returns same economic approval |
| RW-36 | `test_RW36_analyst_prepares_owner_approves` | Analyst prepares but cannot finalize; owner approves |
| RW-37 | `test_RW37_tenant_history_and_attachment_hidden` | Other-tenant history/evidence IDs return 404 without source metadata |
| RW-38 | `test_RW38_source_loss_preserves_history` | Original loss preserves R=10000 but evidence exception/ratio null |
| RW-39 | `test_RW39_successor_with_realized_history_cannot_transfer` | Recognized predecessor cannot retire/transfer money to successor P=45000 |
| RW-40 | `test_RW40_evidenced_extra_consideration` | 60000 full bank receipt with 50000 compatible principal yields R=50000/N=60000 |
| RW-41 | `test_RW41_evidenced_vat_principal` | 108000 inclusive credit with 18000 VAT yields only 90000 R; tax entitlement NOT_ASSESSED |
| RW-42 | `test_RW42_unknown_vat_blocks_ratio` | Unknown VAT leaves principal/pending/ratio unavailable; no inferred tax rate |
| RW-43 | `test_RW43_gross_and_net_are_distinct` | 50000 verified principal, 500 fee, N=49500; gross R=50000 |
| RW-44 | `test_RW44_unknown_withholding_supported_slice_only` | Unresolved withholding admits evidenced 49500 slice only; U/overall ratio null |
| RW-45 | `test_RW45_parent_payer_requires_reviewed_mandate` | Parent payer requires explicit reviewed mandate rather than name inference |
| RW-46 | `test_RW46_rename_continuity_and_acquisition` | Rename continuity supported; acquired entity cannot assume liability without reviewed association |
| RW-47 | `test_RW47_processor_name_not_relationship` | Processor/intercompany attribution requires scoped evidence-backed relationship |
| RW-48 | `test_RW48_workflow_no_financial_side_effect` | Assignment/priority/follow-up/escalation preserve all money |
| RW-49 | `test_RW49_not_pursued_is_not_false_positive` | Commercial not-pursued reason preserves P/V/U, does not dismiss finding |
| RW-50 | `test_RW50_cost_currencies_and_status_separate` | Incurred/paid cost by original currency separate from P/R/N |
| RW-51 | `test_RW51_credit_economic_year_cutoffs` | December issue stock=20000/Rflow=0; January application Rflow=20000/pending=0 |
| RW-52 | `test_RW52_corrected_economic_date_preserves_as_known` | Old K report replays byte-equivalent content; corrected date changes only later restatement period |
| RW-53 | `test_RW53_different_payee_requires_beneficial_discharge` | Different payee requires customer-benefit mandate/discharge |
| RW-54 | `test_RW54_independent_competing_payments` | Independent 6000 payments compete for B=10000; one winner, no truncation |
| RW-55 | `test_RW55_source_change_during_capture_aborts` | Source changes during capture abort with R=0 |
| RW-56 | `test_RW56_de_recognition_is_not_cash_return` | De-recognition changes attributed R without bank outflow; evidenced actual return separately changes N |

## Additional assertion index

| Reference | Test source / function | Reviewed assertion |
| --- | --- | --- |
| AUTH | [test_recovery_concurrency.py](../backend/tests/test_recovery_concurrency.py): `test_approval_serializes_every_calculation_and_recovery_authority` | Eighteen independent-connection orders: membership, finding, fact, packet, association, tax, party, pursuit, closure each before/after approval; denies changed authority or retains consistent old pins. |
| DUP | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_simultaneous_approval_idempotency_one_money_one_audit` | Same-key and different-key simultaneous approvals return one realization ID and exactly one creation audit. |
| REV | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_independent_reversals_share_unreversed_budget` | Independent competing reversals: one winner, original outstanding amount cannot be over-reversed. |
| CREDIT | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_independent_credit_consumption_race_uses_shared_physical_budget` | Two 15000 applications compete for 20000; one succeeds, R=15000 and pending=5000. |
| AUDIT | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_untrusted_journal_insert_and_financial_audit_failure_rollback` | Forged journal rejected; injected trigger audit failure produces no realization or realization audit. |
| IMM | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_database_history_and_source_metadata_are_immutable` | Direct UPDATE of seven history/source tables is rejected below the API. |
| GUARD | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_reads_and_writes_fail_closed_when_shared_integrity_guards_disabled` | Read and write both return 503 when document or audit origin/immutability triggers are disabled. |
| RGUARD | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_disabled_guards_fail_closed` | Disabled recovery audit trigger denies direct approval and commits zero realizations. |
| BASIS | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_pursuit_revision_preserves_current_claim_and_outstanding_realization` | B=29999.99 below R=30000 and B=35000 below C=40000 both fail; prior B/R remain unchanged. |
| PARTY | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_party_revocation_and_dated_relationship_freeze_authority` | Revocation makes readiness BLOCKED and ratio null; a pinned old association cannot recognize money. |
| VDATE | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_vendor_response_requires_dated_counterparty_authority` | Vendor position before the reviewed relationship start is denied; S remains null. |
| REF | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_same_key_changed_meaning_and_economic_reference_collision` | Same request key with changed instrument reference conflicts; same economic reference with changed allocation conflicts. |
| ALIAS | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_instrument_alias_review_retry_and_collision_preserve_one_root` | Approved alternate identity resolves original root; another root cannot claim that alias. |
| NAMESPACE | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_missing_economic_namespace_cannot_create_authoritative_root` | Empty namespace rejected with 422. |
| SIDE | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_recovery_has_no_automatic_financial_or_proof_side_effects` | Evaluation, decision and proof generation replaced with failing sentinels; cash still works, counts/core remain unchanged. |
| BOUNDARY | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_json_duplicate_nan_and_deferred_routes_are_rejected` | Duplicate JSON keys/NaN rejected; recovery export/vendor/send/gain-share/integration/journal routes absent. |
| NOTE | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_note_revision_and_workflow_do_not_grant_roles` | Analyst cannot revise another actor note or gain final authority from workflow; own revision is retained. |
| K | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_known_at_cannot_be_backdated_and_receipt_cannot_be_forged` | Caller known-at field rejected; fabricated publication timestamp rejected by the database. |
| KCOMMIT | [test_recovery_concurrency.py](../backend/tests/test_recovery_concurrency.py): `test_as_known_excludes_transaction_that_committed_after_cutoff` | Record exists before K but transaction commits after K: old flow=0, later flow=10000. |
| LIMIT | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_complete_operations_fail_explicitly_at_configured_resource_bounds` | Six configured limits (sources/bindings/bytes/response/projection/text) produce explicit bounded errors. |
| PAGE | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_history_page_limit_and_source_instruction_are_not_authority` | Page 101 rejected; quoted instructions to invent money remain inert notes with R=0/B=null. |
| SOURCES | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_case_page_uses_shared_source_limit_across_all_cases` | Two cases exceed a shared three-source operation bound; page fails rather than returning partial authoritative content. |
| SQL | [test_recovery_concurrency.py](../backend/tests/test_recovery_concurrency.py): `test_cumulative_sql_work_budget_includes_flush_and_lock_queries` | Expired work budget rejects subsequent SQL/flush work, not merely explicit service checkpoints. |
| SLOTS | [test_recovery_concurrency.py](../backend/tests/test_recovery_concurrency.py): `test_two_tenant_slots_are_shared_by_independent_workers` | Two separate database sessions occupy both tenant slots; third independent worker gets busy. |
| QUOTA | [test_recovery_concurrency.py](../backend/tests/test_recovery_concurrency.py): `test_actor_quota_is_shared_across_tenants_and_retry_does_not_consume` | Ten final actions shared across two tenants; eleventh denied, identical retry remains available. |
| CASHROOT | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_partial_allocations_share_one_raw_cash_receipt` | 20000+30000 principal allocations share one 50000 bank receipt; R=50000/N=50000, never N=100000. |
| RESTORE | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_credit_restoration_is_separate_and_bounded` | Negative R alone leaves pending=0; separately evidenced restoration adds 5000 once, extra restoration denied. |
| PREEXIST | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_preexisting_credit_and_paid_replacement_do_not_qualify` | PREEXISTING credit cannot create R; paid original cannot use unpaid-liability reduction. |
| CLAIMS | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_claim_revisions_replace_not_add_and_vendor_unknown_stays_unknown` | C 20000 then 10000 yields 10000, draft/withdrawal null; unknown dispute and foreign-currency response remain separate/null. |
| KCREDIT | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_corrected_credit_application_date_restates_stock_without_restoring_credit` | December AP date corrected to January: December pending=20000/Rflow=0; January pending=0/Rflow=20000; old digest unchanged. |
| UNKNOWN | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_unknown_credit_does_not_hide_in_partial_known_credit_stock` | Known and unknown credit roots together return pending=null/ratio=null and UNRESOLVED coverage. |
| DATECONFLICT | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_shared_receipt_conflicting_date_corrections_return_unresolved` | Contradictory dates for one physical bank receipt leave R intact, N null and report explicitly blocked. |
| EXPIRY | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_evidenced_credit_expiry_changes_only_pending_stock` | Reviewed explicit expiry consumes pending stock; R/P/V unchanged. |
| EVIDENCE | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_evidence_bindings_cannot_be_added_after_review` | Database refuses an additional evidence binding after approval. |
| DECIMAL | [test_recovery_values.py](../backend/tests/test_recovery_values.py): `test_exact_cent_quantum_overflow_and_ratio_display_separation` | Exact cents and sums, unsupported quantum and overflow rejection; 33.33 ratio display cannot alter monetary inputs. |
| PRECISION | [test_recovery_values.py](../backend/tests/test_recovery_values.py): `test_invalid_precision_has_no_financial_rounding_fallback` | Float/bool/NaN/Infinity/excess scale/overflow are rejected. |
| TAX | [test_recovery_values.py](../backend/tests/test_recovery_values.py): `test_evidenced_tax_and_cash_bridges_preserve_distinct_components` | Exact inclusive VAT, bank fee/net bridge, unresolved withholding preserve separately evidenced components. |
| TAXBAD | [test_recovery_values.py](../backend/tests/test_recovery_values.py): `test_tax_unknown_or_inconsistent_bridge_cannot_be_complete` | Unknown basis, missing VAT or inconsistent gross bridge cannot be COMPLETE. |
| TIME | [test_recovery_values.py](../backend/tests/test_recovery_values.py): `test_date_only_and_half_open_boundaries_are_not_midnight_utc_guesses` | Inclusive start/exclusive end, exact midnight, full date coverage, partial-day/unknown-timezone blocks. |
| DST | [test_recovery_values.py](../backend/tests/test_recovery_values.py): `test_nonexistent_and_ambiguous_dst_local_sources_are_unresolved` | America/New_York gap and fold both explicitly unresolved. |
| TIMEEDGE | [test_recovery_values.py](../backend/tests/test_recovery_values.py): `test_temporal_extremes_return_unresolved_instead_of_guessed_date` | Representational date/offset overflow is unresolved, not a guessed date or server error. |
| DEFAULTS | [test_recovery_values.py](../backend/tests/test_recovery_values.py): `test_approved_operational_profile_defaults_are_exact` | All eleven operational defaults plus profile compared exactly. |
| MIGRATION | [test_phase6_migration.py](../backend/tests/test_phase6_migration.py): `test_phase6_legacy_preservation_empty_downgrade_reupgrade_and_schema` | Legacy user/org/document preserved; six-revision metadata has no drift; empty Phase6 downgrade/re-upgrade has no drift. |
| DOWN | [test_phase6_migration.py](../backend/tests/test_phase6_migration.py): `test_phase6_authoritative_history_refuses_downgrade` | Populated authoritative instrument and trusted audit cause explicit data-loss refusal. |
| COSTFIX | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_cost_corrections_are_bounded_and_keep_recovery_separate` | Explicit incurred/paid negative corrections retain original money and source, cannot exceed outstanding cost, and leave R/N unchanged; semantic repeat returns original ID. |
| CLAIMQ | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_claim_cannot_bypass_approved_currency_quantum` | C=0.001 cannot bypass reviewed 0.01 quantum; C remains null. |
| SEMQUOTA | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_semantic_retry_at_full_actor_quota_does_not_mint_or_charge_authority` | After unrelated case-head change and quota full, same realization/cost meaning returns original IDs and no new counted authority. |
| ROOTCASE | [test_recovery_security.py](../backend/tests/test_recovery_security.py): `test_credit_state_cannot_change_another_case_root_at_service_or_database` | Another case cannot cancel a reviewed credit root: service409, original pending=20000, direct SQL rejected by instrument/case authority trigger. |
| PROOF | [test_proof_api.py](../backend/tests/test_proof_api.py): `test_real_source_chain_exact_outputs_c01_c10_and_no_recalculation` | Existing Phase5 source chain, exact outputs and all C01–C10 still pass without recalculation. |
| REDACTION | [test_proof_api.py](../backend/tests/test_proof_api.py): `test_export_actual_checksum_private_download_current_membership_and_recursive_redaction` | Existing private JSON export checksum/current authorization/recursive redaction remain intact. |

## Frontend checks

[Recovery UI tests](../frontend/tests/recovery-workspace.test.tsx) assert viewer read-only behavior, analyst preparation without final money buttons, explicit owner lifecycle, null versus known zero, exact string/boolean evidence mapping, and paginated history with unresolved commit provenance rather than created_at substitution.

[Recovery proxy tests](../frontend/tests/recovery-proxy.test.ts) assert authentication before resource access, server-side credentials, no-store responses, route/query whitelist, cross-origin rejection, actual body bounds and exact Decimal/idempotency preservation. Existing proof/financial UI tests remain in the full suite. UI checks complement the server/database authority tests; they are not the financial enforcement layer.

## Coverage interpretation

All listed requirements have specific implementation and automated assertion references. Excluded capabilities are covered by strict schema/route rejection, unchanged existing policy and no-side-effect checks; they do not have dormant writable financial fields. This review does not claim exhaustive exploration of every possible input/interleaving, enterprise load certification, legal evidence authenticity, accounting/tax compliance, live bank reconciliation or production deployment. Manual quotations/relationship/discharge meaning remain reviewer assertions. See [validation and limitations](phase6-validation.md).
