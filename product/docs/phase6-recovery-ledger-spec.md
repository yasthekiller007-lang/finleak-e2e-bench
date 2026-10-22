# Phase 6 — Recovery Ledger: business, product and domain specification

**Version:** 1.0. **Status:** APPROVED PHASE 6 V1 BUSINESS / PRODUCT / DOMAIN SPECIFICATION.

**Approved product decisions:** PD6-01 through PD6-37 — Option A for every decision. **Approval date:** 3 October 2026, by explicit user product approval.

**Merge status:** Specification PR [#9](https://github.com/yasthekiller007-lang/financial-leakage-ai/pull/9) is merged. This approved Phase 6 V1 specification version 1.0 was included at specification-merge baseline `87bf0f8bd06cac67061a24850b645cd048406b67`. The implementation starts from main `15c7fc34d4d0092613dc2379f63d606594feebab`, which also includes merged status-cleanup PR #10.

**Implementation status:** Separately authorized by the user on 3 October 2026 and implemented on `phase6/recovery-ledger-implementation` for review. Implementation is not merged and no production deployment is claimed. See [implementation validation](phase6-validation.md) and [policy-to-code traceability](phase6-traceability.md); final delivery requires complete CI on the exact implementation PR head. Business/product/domain policy below remains unchanged.

**Historical specification starting main:** `4e574e17ff7dbc69ed4b2b3a5ab0db1ab930f4f7`, including merged PR #8 and Phases 1–5 V1. **Historical specification branch:** `phase6/recovery-ledger-spec`. **Previous validated specification checkpoint:** `6d032eb2ca5acb697869a20abbfe49294898306a`.

**Historical specification-finalization authorization (execution status superseded by the later explicit implementation authorization above):** This task authorized specification finalization only. Phase 6 application implementation, migrations, APIs, frontend implementation, implementation tests, integrations, vendor communications, recovery automation, gain-share billing, Firewall and Leakage DNA are NOT authorized. No Phase 6 application functionality or production deployment is claimed; no accounting, legal, tax or regulatory compliance claim is made.

[Phase 4 business policy](phase4-business-spec.md), PD-01–PD-07, and [Phase 5 proof policy](phase5-proof-engine-spec.md), PD5-01–PD5-14, remain approved, authoritative and unchanged. Read [Phase 4 architecture](phase4-architecture.md), [Phase 4 validation](phase4-validation.md), [Phase 5 validation](phase5-validation.md), [Document Intelligence](document-intelligence.md) and [HANDOFF](../HANDOFF.md). Historical phase-status text in older documents does not override the merged baseline or the separately granted implementation authorization. That authorization changes execution status only, not this approved policy.

**Authority convention:** inherited constraints and the user's express prohibitions remain mandatory. The user approved Option A for all PD6-01–PD6-37 on 3 October 2026; section 38 and the corresponding definitions, invariants, states, metrics, examples and future acceptance criteria constitute the authoritative Phase 6 V1 policy. Options B/C are non-approved alternatives and confer no V1 authority. A later proposed policy change requires separate explicit approval and a complete dependency/consistency review. Product approval does not approve any actual fact, case, event or evidence; those still require the specified role-controlled review. The specification is merged and separate explicit Phase 6 V1 implementation authorization has since been granted. Deferred capabilities and any policy change still require their own explicit authorization.

## 1. Purpose

Phase 4 asks whether a reviewed scope has potential leakage. Phase 5 explains exactly why that immutable result exists. The approved Recovery Ledger specification defines recording what people did afterward, which economic events were independently evidenced and approved, what was attributable to the finding, and what remains unresolved. It is an internal operational system of record, not a general ledger, debt/legal-liability register, bank balance, guaranteed savings engine or billing system.

**Simple on the surface, rigorous underneath.** A summary distinguishes potential, internal confirmation, commercial pursuit, claim, vendor position, gross verified realization by method, net bank receipt, pending credits, unresolved exposure and closure reason. Drill-down preserves the complete evidence, approvals, allocation, dates and reversal history.

## 2. Scope

Approved V1 scope: one tenant-scoped case per positive immutable evaluation; investigation before readiness; owner/admin commercial readiness; manual source-backed claims and vendor responses; individual cash, applied-credit and verified liability-reduction events; partial/multiple realizations; append-only corrections/reversals; closure/reopening; internal assignment/notes; exact currency/basis-specific views. PD6-01–PD6-12, PD6-20–PD6-23 and PD6-28–PD6-37 govern this approved profile.

Deferred: grouped finding cases and bundled settlement allocations; monetary avoided-value/annualized forecasting; FX; other-consideration valuation; gain-share eligibility/invoicing; public/vendor sharing or communication; ERP/AP/bank integrations; payment controls; autonomous recognition; general-ledger postings; legal/tax interpretation; retention/erasure automation; new leakage families. Recording a remediation offset referencing a later invoice does not enable Phase 4 cross-invoice pricing/credit calculations or modify any assessed actual amount.

## 3. Definitions

| Concept | Approved meaning and boundary |
| --- | --- |
| Potential P | Exact positive `FinancialEvaluation.potential`; immutable, tax-exclusive Phase 4 comparison. It proves neither prior payment nor legal debt. |
| Internally validated V | P under a pinned existing Phase 4 owner/admin `confirmed` decision. An active/current V is unknown when that authority is absent or the evaluation is stale; a historical V remains visible. No separately typed validated amount. |
| Commercial pursuit ceiling B | Owner/admin-approved eligible subset to pursue, `0 < B <= V`, with rationale and scope. It is a commercial target, not a correction of financial truth. Defaulting it from P before readiness is forbidden. |
| Claimed C | Evidenced current claim principal for one scope, possibly below B. Draft, sent/actioned, withdrawn and replaced are separate records. Not cash or legal liability. |
| Vendor acknowledged S | Evidenced vendor position/agreed settlement principal, not payment. Gross settlement and principal attribution are separately recorded. |
| Disputed D | Explicit amount and scope disputed in vendor evidence. Not automatically P−S, C−S or V−R. Unknown when the response is incomplete. |
| Recovery instrument | Stable economic credit/payment/offset identity independent of documents, uploads, proof revisions and proposal retries. |
| Recovery observation | A reviewed or proposed fact about an economic instrument. Recording it alone creates no recognized recovery. |
| Approved realization allocation | Owner/admin-approved, evidence-backed amount of an actual realization attributed once to the case's compatible principal scope. |
| Gross verified realized recovery R | Signed approved tax-exclusive principal realization before separately evidenced recovery costs, separated into cash-performance, applied-credit and liability-reduction components. It is not necessarily the net bank receipt. Never display this as unqualified cash/savings. |
| Net cash N | Exact evidenced cash credited to the identified beneficiary account after documented payment deductions; preserve its own gross/tax basis. Never backsolve unknown components. |
| Credit pending Kc | Approved valid issued principal not yet consumed, reversed or explicitly cancelled/expired. A bounded stock, not realized recovery or a forecast. Missing reconciliation makes the affected balance unknown. |
| Remaining U | `B−R` only with compatible, complete and nonnegative allocation reconciliation. Call it “unrealized pursuit balance”, not debt or disputed value. Closure does not zero it. |
| Recovery cost F | Separately evidenced directly attributable cost, with currency, nature and incurred/paid states; never a rewrite of P, V or R. |
| Avoided future value | A counterfactual economic comparison requiring its own approved baseline; an actual corrected invoice alone does not establish what otherwise would have been billed. Monetary recognition deferred in approved V1. |
| Known-at K | Server-established commit time/order when an approved fact or decision entered authoritative ledger history. Distinct from source economic date and upload/created time. |

Absent or unassessed money is null, not zero. A zero sum of a completely enumerated approved ledger means “no approved attributed realization in this covered set”; it does not prove that no cash ever arrived. Proposed/unallocated/unknown-basis amounts appear separately with explicit coverage.

## 4. Domain invariants

| ID | Invariant |
| --- | --- |
| I01 | Potential ≠ validated ≠ pursued ≠ claimed ≠ acknowledged ≠ realized; none of those stages automatically advances another. |
| I02 | A Phase 6 event never changes evaluation E/A/Δ/P, currency, scope, economic date, matching, terms, amendments, rounding or prior credit treatment. |
| I03 | Correct financial basis through new Phase 4 reviews/evaluation and a separately anchored Phase 5 proof, never a recovery amount edit. |
| I04 | COMPLETE proof ≠ confirmed finding ≠ human proof review ≠ commercial readiness ≠ economic realization. |
| I05 | Credit issued ≠ applied ≠ cash. One economic benefit is consumed once across all related documents/methods/cases. |
| I06 | Forecast/annualized/avoided values never enter cash or historical realized recovery. |
| I07 | User-entered amount, approval click, vendor promise or settlement agreement alone is not realization evidence. |
| I08 | Closed/not pursued/commercially written off ≠ false positive ≠ fully recovered ≠ accounting write-off. |
| I09 | Vendor response is evidence of that counterparty's position, not replacement contractual truth. |
| I10 | Unknown ≠ zero; unknown tax basis, currency, beneficiary or economic identity cannot become a compatible allocation by numeric equality. |
| I11 | Different currencies, entities, tax bases and overlapping principal scopes cannot be summed or compared as compatible recovery. |
| I12 | Unallocated settlement is not finding recovery; `min(payment,P)` and automatic proportional allocation are not approved evidence. |
| I13 | Originals, approved observations, approvals, allocations, actions, reversals and corrections are append-only; no overwritten money or deleted history. |
| I14 | New proof revision/export/rerun never creates a new case or benefit. A successor evaluation never silently transfers recovery. |
| I15 | Source-byte integrity, tenant isolation, current role checks and transactional trusted audit are required for financial authority. |
| I16 | Reversal cannot exceed unreversed recognized amount; a cancelled promise reverses no cash that never existed. |
| I17 | Positive recognition cannot exceed B or the unused evidenced instrument budget on the same basis. Supporting evidence must precede arithmetic caps. |
| I18 | Gross agreement, gross performance, taxes, deductions, net bank receipt, costs and other consideration remain distinct. |
| I19 | Economic dates, knowledge times and reporting policy versions remain separate; current corrections cannot rewrite an earlier as-known report. |
| I20 | Workflow fields, priorities, assignments, targets, escalations and notes have no financial recognition side effects. |
| I21 | Existing source/delete/disclosure safeguards remain intact; no new legal authenticity, permanent retention or compliance promise. |
| I22 | A resource limit yields an explicit bounded result, never truncated authoritative totals or suppressed amounts. |

## 5. Recovery identity model and architecture inspected

Conceptual structures below are not a database schema or table mandate. A later authorized implementation must select a minimal design after specification merge and separate explicit implementation authorization.

| Existing implemented asset | Reuse / exact limitation |
| --- | --- |
| `ReviewedFinancialSource`, `FinancialRevision`, `FinancialRevisionEvidence` ([models](../backend/app/financial/models.py)) | Stable invoice/master and reviewed meaning/provenance. ExtractionRun is candidate lineage, not business identity. Do not repopulate or duplicate legacy Contract/Invoice entities. |
| `FinancialEvaluation` | Immutable scoped financial anchor, unique tenant/fingerprint, exact `NUMERIC(20,6)`, snapshot. Positive finding ID is its evaluation UUID. Legacy LeakageCase/recovered_amount is not Phase 4/5 recovery truth. |
| `FinancialFindingDecision` / [service](../backend/app/financial/service.py) | Append-only actual `confirmed`, `false_positive`, `needs_review` records. Default `detected` is derived. Current API `needs_review` can be a staleness overlay: inspect the decision and `is_stale` separately. |
| `ProofFamily` / `ProofPackage` ([models](../backend/app/proof/models.py)) | Family unique tenant/evaluation/kind; exact immutable content revision/fingerprint plus envelope. Attach specific package at readiness/action/recognition, never a floating “latest proof”. |
| `ProofEvent` / `ProofArtifact` | Existing attributed review/disclosure/annotation history, private verified JSON; final review is optional and separate. Recovery facts do not belong in proof annotations/core/artifacts. No export required to recognize recovery. |
| `ProofSuccessor` / [service](../backend/app/proof/service.py) | Authorized distinct evaluations with same known invoice source, scope/members, currency/unit/period; unique edges, no forks/cycles. It cannot link a changed invoice identity/currency/scope merely because vendors match. No recovery transfer is implemented. |
| `FinancialAudit` | Trusted trigger-origin durable audit, immutable, organization/actor/time/action/target/detail. Future recognized recovery needs compatible trusted origins, not direct arbitrary INSERT or a duplicate journal. |
| Authority/concurrency | Existing organization lock → fresh membership share lock → source/evidence lock order. Source bytes use consistent bounded captures; PostgreSQL alone cannot lock an external disk writer. |
| [Proof API](../backend/app/api/proof.py), [financial UI](../frontend/src/components/financial-workspace.tsx), [proof UI](../frontend/src/components/proof-workspace.tsx) | Server-scoped role/tenant controls, no-store proxy, explicit generation, historical detail and separate warnings. No Recovery Ledger route/UI exists. |
| Private Document storage / Phase 3 | Document ID/hash/type/size; inert uploaded sources, manual citations or existing run/field evidence. Secondary credit/other documents have no sophisticated authoritative extraction. A new extraction feature is not required/authorized by this spec. |

Missing conceptual capabilities: case identity, commercial readiness/pursuit revision, instrument identity/aliases/consumption, recovery proposal/approval, method-specific reviewed evidence, beneficiary/counterparty associations, allocation/reversal links, credit lifecycle, costs, workflow history, and reproducible time-aware projections. Existing party meanings are reviewed `supplier_party`/`customer_party` keys, not an implemented universal legal-entity master or cross-company payment-authority registry. Those gaps cannot be papered over with fuzzy names. Tenant-safe relationships to decision/audit identities may need engineering integrity work later; no migration/schema is chosen now.

Approved case identity: `(tenant, immutable positive evaluation UUID)` with its own operational case ID. One investigation case across all proof content revisions; close/reopen the same case. Economic instruments have a tenant-wide identity using reviewed issuer/payer namespace, legal entity, transaction/credit reference, currency and origin. Preserve source spelling and explicit alias links. One document can support multiple distinct bank rows; multiple documents can support one transaction. A hash is a byte identity, neither sufficient nor necessary by itself for economic deduplication.

## 6. Eligibility to enter Recovery Ledger

Approved PD6-01 Option A: owner/admin/analyst may create an INVESTIGATION case for a positive existing POTENTIAL_LEAKAGE evaluation. It may be unconfirmed, lack proof, or be stale, provided currentness/decision/proof warnings are explicit. A dismissed finding is not eligible for a new ordinary case; keep an existing case's historical record. UNDERCHARGE, NO_OVERCHARGE and NEEDS_REVIEW assessments have no positive finding identity and cannot enter monetary recovery cases, even with a COMPLETE explanation.

Commercial READY requires owner/admin approval pinning: current confirmed decision ID; exact evaluation fingerprint/scope/currency; COMPLETE monetary proof package/fingerprint; currently available/hash-verified required sources; reviewed counterparty/beneficiary; explicit B; tax/precision profile; readiness reason/time/version. Optional human proof review is not mandatory, preserving PD5-03. Investigation preparation does not grant claim or realization authority. Missing readiness money is null.

Historical economic transactions may be recorded as observations even if readiness is blocked. Positive finding attribution is approved only after the gates pass; no loss of raw transaction history and no inference that readiness magically occurred on the original transaction date.

## 7. Recovery lifecycle

Use orthogonal axes (PD6-04), not a single overloaded progression:

| Axis | Approved values / derivation |
| --- | --- |
| Case lifecycle | OPEN / SUSPENDED / CLOSED, via attributed owner/admin events. |
| Readiness | INVESTIGATION / READY / BLOCKED. READY is a pinned approval plus current gating, not a manual badge immune to stale data. |
| Finding | Actual Phase 4 decision history and scoped CURRENT/STALE/UNKNOWN, separately observed. |
| Claim | NONE / DRAFT / RECORDED_ACTION / WITHDRAWN / REPLACED. Claims are revisions, never cumulatively added. |
| Vendor position | NO_RESPONSE / ACKNOWLEDGED / PARTLY_DISPUTED / DISPUTED / UNRESOLVED, based on explicit response coverage. |
| Realization | NO_APPROVED_VALUE / PARTIAL / AT_PURSUIT_CEILING / UNKNOWN, derived from compatible R/B and coverage. |
| Credit | ISSUED / AVAILABLE / PARTLY_CONSUMED / CONSUMED / CANCELLED / EXPIRED / REVERSED, with event history. |
| Evidence | VERIFIED_AT_APPROVAL plus current AVAILABLE_VERIFIED / UNAVAILABLE / MISMATCH / UNCHECKED overlays. |

| Transition/action | Authority and conditions | Invalid shortcut |
| --- | --- | --- |
| Absent → OPEN/INVESTIGATION | Owner/admin/analyst, eligible unique evaluation and audited request. | Proof reissue cannot create another case. |
| INVESTIGATION/BLOCKED → READY | Owner/admin, full pinned readiness gates and expected predecessor. | Analyst, COMPLETE alone or unconfirmed/stale evaluation. |
| OPEN → SUSPENDED; READY → derived BLOCKED | Owner/admin suspension or material gate loss observation; keep history. | Zeroing recovery or silently continuing positive approvals. |
| SUSPENDED → OPEN | Owner/admin reason; readiness independently rechecked. | Reopen automatically restores old READY. |
| OPEN/SUSPENDED → CLOSED | Owner/admin reason and explicit pursuit disposition; no financial calculation change. | Closing implies recovery/false positive. |
| CLOSED → OPEN | Owner/admin reason/predecessor; retain all prior closure and money history. | New duplicate case or restoring reversed amounts. |
| Positive monetary approval | OPEN + READY, explicit proposal/evidence/allocation, current fence. | CLOSED/stale/dismissed/proposal-only authority. |
| Reversal/corrective de-recognition | Owner/admin, verified link to approved historic event and remaining reversible budget; allowed when closed/stale/dismissed. | Freeze preventing correction of an overstatement. |

Assignment, note or response does not automatically move lifecycle. An economic receipt can exist without a recorded platform claim: if all recognition gates pass, approve the direct remediation evidence; do not fabricate an email/action. Closure remains explicit even at B. Full B recovery need not recover all V when B<V.

## 8. Monetary dimensions, tax, gross/net and precision

At a stated knowledge cutoff, V is P only if the pinned Phase 4 confirmation exists; active V additionally requires current eligibility. B is commercial, C/S/D are evidenced positions, R is a sum of approved attributed principal events. They are different measures, never an additive funnel. If claim or response covers only part of a scope, preserve the covered component IDs and explicit unknown remainder.

For one fully reconciled event, source-level `gross_received = net_cash + bank_fees + withholding + other_deductions` holds only where each same-currency component and meaning is evidenced. Unknown components are null; the equation cannot invent them. Agreed settlement is not gross receipt. Noncash consideration is separate and unvalued for V1 finding recovery unless it falls within a supported verified liability reduction. Do not sum different bases simply because the currency matches.

**Approved PD6-28 tax policy:** inherited P is tax-exclusive. Record raw inclusive/exclusive/unknown basis, explicitly evidenced principal, VAT/tax components and source/reviewer mapping. Allocate and cap only the compatible principal. A 108000 USD credit with an explicit 90000 principal + 18000 VAT breakdown, applied and approved against P=90000, contributes R=90000, not 108000; VAT adjustment stays separate. No assumed tax rate, deduction eligibility, recoverability, refund from authorities, withholding treatment or net-tax benefit. Recoverability may remain NOT_ASSESSED even when the source principal is separable. Unknown/contradictory basis blocks affected allocations, remaining balance and ratio; keep raw money as an unallocated observation.

**Approved PD6-29 gross/net policy:** display “Gross verified realized recovery — tax-exclusive principal, before separately evidenced costs”, cash-performance component, gross actual remittance, net bank receipt and deductions separately. For an evidenced discharged 50000 principal refund, bank fee 500, net bank credit 49500, R=50000 and N=49500; F=500 is a separate cost observation, not another benefit or automatic subtraction. This is not a net-savings policy. A withholding amount is not recognized merely because it is deducted: its tax entitlement/payment-beneficiary/discharge meaning requires explicit evidence and otherwise remains excluded/unresolved. An independently evidenced net principal portion can be approved separately; unresolved material deductions block the overall recovery ratio until reconciliation is complete.

**Approved PD6-37 precision policy:** reuse finite decimal strings and existing 20 digits/6 fractional places without coercion; respect currency-specific evidenced monetary precision, not universal cents. Exact bounded sums/subtractions only, with an explicitly adequate Decimal context (80 digits is reusable for bounded source inputs). No automatic financial quantization, tolerances, epsilon, materiality deletion or residual allocation. Unrepresentable/excess-scale values fail explicitly. Ratios are presentation only: exact numerator/denominator retained; two-decimal percentage with explicitly labeled HALF_UP display rounding, never rounded back into monetary records. Source precision or quantum uncertainty affecting attribution blocks approval. All two-decimal USD examples below expressly use aligned fixture amounts, not a real-document default.

## 9. Recovery methods and realization evidence

| Method | Required source-backed event | When principal may enter R / distinction |
| --- | --- | --- |
| Cash refund | Settled beneficiary receipt, remittance/settlement principal mapping, payer/payee authorization and tax/deduction reconciliation. | At actual settlement/availability evidence, not initiation. Gross principal performance and N stay separate. |
| Vendor credit / invoice credit | Issuer/credit identity, linked remedy scope, face/principal/tax, availability/conditions; later AP application. | Issuance only Kc; R only actual approved application or cash redemption, once. |
| Offset against later invoice | Credit root, exact later invoice/account, AP/remittance applied amount/date and balance reconciliation. | Applied principal is noncash R; does not alter old Phase 4 A or enable a pricing family. |
| Corrected replacement invoice | Original still-unpaid payable, explicit replacement/void relationship, corrected payable/reconciliation and same supported remedy scope. | Verified effective liability reduction, not cash. If original already paid, correction alone is pending credit/claim until refund/application is evidenced. |
| Waived unpaid balance | Specific payable, unconditional effective release and posted/reconciled balance reduction. | Verified liability reduction; not a legal judgment or bank receipt. A promise/conditional waiver is not realization. |
| Negotiated settlement | Source agreement, compatible principal/extras and accepted scope. | S only until a supported realization method occurs. |
| Forward contract/price correction | Explicit corrected terms/action and later verified invoice observations. | No monetary R or avoided-value metric in approved V1. |
| Service credit | Exact eligible existing finding principal and supported currency credit instrument/application. | If remedy concerns an unrelated SLA issue, unallocated/unsupported; no new SLA leakage rule. |
| Other manual / barter / equipment | Attributed source observation and approval of its factual existence. | No free-entry monetary realization or invented fair value; unsupported consideration stays outside R. |

Do not require sophisticated extraction from credit/bank documents. Manual reviewed evidence must be actual tenant-owned protected sources, locators/quotes and support mappings, with explicit reviewer-attestation limitations. An internal approval or journal note alone does not prove external settlement.

## 10. Partial recoveries

Support arbitrary source-supported positive slices within the unused B and instrument budget (PD6-06). P/V remain unchanged. For P=V=B=74199.90, C=74199.90, S=50000, explicit disputed D=24199.90, cash principal 30000 and issued-unapplied credit 20000: R=30000, Kc=20000, U=44199.90; S is not R and U is not D. After application of that distinct credit, R=50000, Kc=0, U=24199.90. Never report R=70000 by adding S, credit issuance and application.

An eligible realized subcomponent can be separately proposed/approved when its identity/basis/evidence is complete and the remainder explicitly unresolved. No “partial approval” by arbitrary percent of an incomplete total. A small genuine realization, including a supported one cent, remains recorded. A recovery proposal exceeding a budget is rejected, not silently truncated.

## 11. Multiple recovery events

Each refund/installment/application/reduction has immutable identity, exact method/currency/principal/date, instrument, evidence, actor/time, proposed revision, approval, allocation and optional reversal predecessor. R derives from approved positive allocations minus approved reversal/de-recognition allocations, not a mutable recovered_amount. Preserve both cumulative realized inflows and linked reversals so net-after-reversal R does not masquerade as cash after fees.

One cash line or credit benefit can appear in many source documents but has one consumed economic identity. Bank row reference/namespace/beneficiary/date/amount are reviewed identity evidence; uncertain duplicate detection yields conflict review, not automatic deduplication/recognition. Same reference reused by a vendor needs explicit disambiguating evidence. Do not automatically treat equal amounts/dates as duplicates or different uploads as different money.

## 12. Credits and offsets

Record issued face/principal/tax, conditions, expiry where explicitly known, application/redemption/cancellation/reversal events and current reconciled balances. Under PD6-08, issuance/availability is not R. A reconciliation can establish known zero unused balance; missing terms/application history remain unknown. Do not auto-expire at today's date without source-backed expiry semantics and an audited state observation. Contractual conditions that require interpretation remain blockers, not automation.

Application budget consumes the credit root once across invoice offsets and cash redemption. Issued 20000, applied 12000, cash redeemed 8000 yields R=20000 and Kc=0, not 40000. If an applied credit is converted to cash, require evidence of the AP application reversal/restored payable before credit consumption is released; a classification transfer without new economic benefit cannot increase total R. Missing relationship blocks another allocation.

Phase 4 pre-existing credits already included in evaluated A cannot be claimed again as remediation. A known relevant unresolved earlier credit cannot be bypassed by Phase 6 to rescue a blocked Phase 4 result. Distinguish event purpose, assessed bridge entry identity, economic date and scope, not upload timestamp. Later source-backed remediation is an independent ledger event, never retroactively injected into old A. Manual AP offset evidence here does not extend Phase 4's deferred cross-invoice credit calculation policy.

## 13. Avoided future leakage

Approved PD6-13 requires recording the corrective action and actual later invoices as nonmonetary “Observed corrected billing” only. An actual later invoice at 18.40 rather than a prior billed 20.10 proves the observed rate, not that 20.10 would otherwise have continued or that the company would have purchased the same quantity. A zero-overcharge later Phase 4 assessment does not itself calculate avoided savings. V1 avoided-realized amount is null/unimplemented, not zero.

Non-approved alternative B would require a separately approved counterfactual baseline profile, stable comparable scope/entity/currency/tax, actual complete later quantities/period, no volume/mix/tax change attribution, fixed horizon, source-backed causality and non-overlap with refunds/credits. That profile and its financial calculation are NOT authorized here. A reviewed future contractual term belongs in Phase 4 fact review; Recovery Ledger cannot reinterpret or compute a new leakage family.

## 14. Annualized savings

Approved PD6-14 defers monetary forecast and annualized metrics. A human assertion “10000 per month ×12=120000 annually” is labeled attributed unapproved scenario, never a platform recovered/avoided finding or dashboard metric. A contract ending in three months cannot support an unexplained twelve-month horizon. No numeric confidence or automatic forecast decay is introduced.

Any later approved forecasting profile must specify observation window, fixed/variable quantity assumptions, baseline/recurrence, eligible period, contract end/renewal evidence, maximum horizon, expiry/revalidation, arithmetic/rounding/version and scenario status. Forecast, actual avoided-value and historical recovery remain separate; no gain-share base follows automatically.

## 15. Disputes and vendor responses; claims and commercial closure

Claim revisions pin principal/scope/B, action type, actual action date, source evidence, actor, recorded-at and superseded/withdrawn predecessor. Prepare is not actioned; a user draft or unsent platform note cannot assert vendor contact. Internal tracking records a human action taken outside the platform; it does not send anything. Current C is one effective claim revision, not sum of repeated follow-ups. No new claim above B; gross tax/extras may be recorded separately but are not same-basis claimed principal.

Vendor responses separately identify responder/legal-entity authority, accepted/disputed/conditional amounts, scope/date, response source and incomplete coverage. Record partial coverage rather than infer the rest disputed. Agreement S can differ from C/P and must reconcile principal/extras explicitly before any finding allocation. Dispute, denial or nonresponse neither dismisses a Phase 4 finding nor changes P. Withdrawn pursuit leaves P/V and existing receipts intact.

PD6-32 reasons for “Closed — not pursued / commercial write-off”: economics of pursuit, commercial relationship, immateriality, remedy evidence insufficiency, limitation/time-bar concern requiring outside legal review, management decision, operational inability, partial settlement accepted/no further pursuit, duplicate operational case or invalid financial basis. Require owner/admin, attributed rationale, effective date, unresolved pursuit amount/coverage and history. Do not declare a legal limitation period, accounting provision, bad-debt expense or false positive from this label. Financial truth review remains a distinct Phase 4 decision. Reassignment/priority/target/follow-up/next action/escalation are PD6-31 operational metadata only.

## 16. Evidence requirements and counterparty attribution

Approved R01–R10 recognition checks are deterministic business gates, not a confidence score or Phase 5 completeness replacement:

| Check | Requirement before positive recognized allocation |
| --- | --- |
| R01 | Same authorized tenant, stable eligible case/evaluation, OPEN lifecycle, current ready predecessor. |
| R02 | Pinned confirmed Phase 4 decision, evaluation fingerprint and exact supported principal scope. |
| R03 | Pinned COMPLETE monetary proof, integrity consistent, required originals currently hash-verified; optional human review separate. |
| R04 | Correct reviewed supplier/customer, payer/payee/beneficiary and any explicit cross-entity relationship at the economic event date. |
| R05 | Stable unused economic instrument identity, no pre-assessment credited/recovered benefit reuse. |
| R06 | Method-specific completed economic event and exact date; agreement/initiation alone insufficient. |
| R07 | Same currency, comparable tax-exclusive principal, fully evidenced deduction/amount component scope and precision. |
| R08 | Explicit principal allocation within unused B and instrument/credit budget; no guessed proportional/capped attribution. |
| R09 | Fresh owner/admin approval of exact proposal/evidence/predecessors; source capture and all material inputs fenced/rechecked at commit. |
| R10 | Atomic immutable event/approval/allocation + trusted audit + semantic/request idempotency; failed transaction creates no recognized orphan. |

Evidence bundle records Document ID/hash/known size/type, preserved original bytes, locator/citation and manual/extracted origin, exact observed raw/reviewed fields, issuer/payer/payee/beneficiary account reference, transaction/credit namespace, monetary/tax/deduction components, economic date, relationship to original claim/finding and any later applied payable, reviewer/role/reason/time, proposal revision and policy version. Store account evidence privately; mask routine display without changing canonical evidence. OIDC/token/storage paths are never evidence fields. An uploaded email may establish acknowledgment, not cash. Reviewed internal AP reconciliation must cite its underlying credit/payable/settlement records; source-free user journals cannot prove a reduction.

**PD6-30:** exact legal-entity/identifier consistency, not similar vendor names. Parent/subsidiary relationships alone do not authorize payment attribution. Different payer or payee needs reviewed agency/assignment/collection mandate, remittance and beneficiary reconciliation identifying amount/scope, applicable dates, authority and contradictions. A rename preserves identity only with evidenced continuity; acquisition of assets/group membership does not imply liability transfer. Shared processors need underlying merchant/payee transaction evidence. Intercompany settlement needs an explicitly evidenced authorized discharge relationship and benefited customer; otherwise observe, block finding attribution. Tenant membership is never proof of corporate beneficial entitlement. V1 uses scoped reviewed associations, not a new global entity matching service.

## 17. Proof Engine relationship

Case creation may lack proof; READY/positive recognition under PD6-01/05 requires a COMPLETE MONETARY_FINDING_PROOF for the exact evaluation. ProofFamily supplies stable evidence anchor; ProofPackage supplies pinned revision/fingerprint at the specific decision. Store actual FinancialFindingDecision ID, currentness observation and any explicit ProofSuccessor separately. ProofArtifact may support a historical presentation but redacted export is not full internal evidence and export authority remains Phase 5 owner/admin. Human REVIEWED is optional; COMPLETE neither confirms the finding nor approves commercial action.

Later proof-only repaired evidence/schema/assembly revision does not duplicate/rebase a recovery case, change earlier package references or recognize new value. New readiness approval may explicitly pin a compatible newer package; old references remain. Recovery evidence attaches to ledger events, not old proof core/annotations. No automatic proof generation/reevaluation is triggered by viewing or creating a case. Users may invoke the existing authorized generation command separately. Source/evidence loss after recognition is an availability overlay, not an automatic financial reversal.

## 18. Historical immutability

Separate immutable event content from approval/rejection/withdrawal/correction records and current operational projections. Proposed evidence revisions retain predecessors. Once approved, recorded monetary components, allocation, method, economic date, source hash, counterparty and approval history cannot be edited in place. A new source or interpretation creates a new reviewed record, never a replaced original or updated financial column.

A historical approved realization remains visible if its finding later becomes stale/dismissed, case closes or source becomes unavailable. Present “Approved recorded realization as known at K; current eligibility/evidence exception”, not a claim that bytes are currently verified. Current eligible-attribution metrics separate exception buckets; they do not delete or secretly zero transactions. Detailed totals include both eligible and exception categories only once and disclose which basis/approval/availability population they cover. No amount is silently reclassified as unverified legal debt.

## 19. Reversals and corrections

Distinguish economic reversal (cash actually returned, credit application reversed, liability reinstated) from correction of an incorrectly recognized allocation (wrong amount/date/case/source). Each requires owner/admin, exact original allocation/instrument and remaining unreversed amount, event type, economic date, reason/evidence, actor/time, expected predecessor and trusted audit. Partial reversals permitted; combined reversals cannot exceed outstanding original recognition. Credit cancellation before application only reduces Kc; it cannot create a negative R.

Economic reversal contributes a linked negative allocation on its own actual date. Recognition correction appends de-recognition/replacement, preserving original observations and bank receipt; it does not assert the bank sent money back. A wrong date correction retains original date, corrected evidence date and known-at order; current-knowledge restatement may change period attribution, while an old as-known report is reproducible. Correction never changes P/V or proof.

If a later receipt merits re-recognition after de-recognition, use an explicit supported replacement linked to the same economic root, once. Reversal permission stays available for CLOSED/SUSPENDED/stale/dismissed cases so mistakes can be corrected; new positive approvals require fresh readiness. Ordinary reversal cannot cause a negative residual R or invent a new payment liability; excess adverse cash facts may be retained as non-attributed observations requiring review.

## 20. Reopening and not-pursued cases

CLOSED means no further ordinary pursuit authorized under that closure reason, not fully recovered. Owner/admin may reopen with reason, effective date and expected closure/case head; preserve prior decisions and money. Reopening rechecks current finding/proof/evidence; it does not restore READY, revive expired credits, undo reversals or mint a new case. Analyst may propose reopening but not finalize it.

Later genuine receipt may be recorded while closed; positive attribution requires explicit reopening/readiness. Corrective negative allocations do not require reopening. “Commercially written off” retains U as historical unpursued exposure, never an accounting write-off or legal waiver assertion unless a separately evidenced method-specific waiver exists. Workflow assignment changes are attributed revisions and cannot reopen/close financial authority.

## 21. Duplicate and double-count prevention

| Collision | Required approved treatment |
| --- | --- |
| Same request UUID/body/actor/target | Same persisted result; no second case/event/approval/audit creation. Different meaning conflicts. |
| Different keys, same economic payment/credit | Same root identity; conflicting proposed facts require review, not another benefit. |
| Credit issued then applied | Issuance stock then one application flow. No R at issuance. |
| Credit plus related cash refund | Consume the same credit/remedy root once; distinct independent benefits require explicit source scope evidence. |
| Correction then later invoice observation | Historical liability reduction can enter R once; observed corrected future pricing has no monetary avoided metric in V1. |
| Settlement plus payment | Agreement is S; performance is R; no sum S+R. |
| Multiple proofs for one evaluation | One recovery case and existing finding, regardless of exports/content revisions. |
| Old/new evaluations of one assessed money scope | Explicit relationship and freeze/rebase rules; no two active overlapping pursuit/realization budgets. |
| Pre-existing Phase 4 credit | Evaluated bridge identity is already accounted for, not fresh recovery. |
| Cost reused as fee and legal invoice | One cost economic identity; source alias duplicates do not add cost. Cost is never subtracted twice from N. |

Tenant-wide economic root consumption and compatible principal scope are mandatory, not merely per-case UUID uniqueness. A suspected duplicate/missing source namespace blocks further consumption. Do not silently merge uncertain rows; retain conflicting observations. No aggregate case or extra financial finding is created.

## 22. Scope and allocation; excess settlement; changed findings

Approved PD6-16 defers bundled multi-finding allocations. V1 may record a tenant-owned unallocated settlement observation related nonfinancially to several findings, but none receives R without a supported individual allocation profile. Even an explicit 100000 settlement allocation across 40000/70000 findings remains a deferred V1 operation; do not fake two unrelated root instruments. A later approved profile must enforce sum allocations ≤ documented principal, per-finding B, scope disjointness and reversals across the entire shared instrument atomically. Proportional allocation is not a default.

PD6-17: finding attribution bounded by approved B≤V; raw receipt/extras remain complete. At P=50000 and payment=60000, source allocation 50000 principal +10000 documented goodwill allows R=50000 and a separate unallocated/other-consideration 10000 observation. Without that breakdown, approval is blocked; do not automatically recognize `min(60000,50000)` or create a new leakage family for the excess. Interest, costs, damages and unrelated issues require separately identified basis; V1 does not make them finding principal.

PD6-18: material staleness/successor suspends new positive attribution/action authority; raw real-world observations and reversals remain available. Preserve old case/evaluation/P/package and recorded R. A new evaluation needs its own case and explicit same-scope relationship where the existing ProofSuccessor rules support it. With no recognized history, owner/admin may retire the predecessor's unused pursuit and approve a new case after full checks. With recognized history, monetary reallocation/transfer and new overlapping successor recognition are deferred until a separately approved reconciliation profile exists; a new investigation case does not duplicate old recovery. Changed currency/entity/period/invoice source cannot use a false same-scope successor shortcut.

PD6-19: a later `false_positive` blocks pursuit/positive attribution and excludes the case from active eligible KPIs; preserve receipts and approvals as an explicitly invalidated-basis historical category. Do not make bank money disappear or auto-return it. An actual refund back is its own evidenced economic reversal. Phase 4 re-confirmation is distinct and must pass its stale checks; material correction requires new facts/evaluation/proof. Needs-review or UNKNOWN currentness is not treated as current.

## 23. Currency rules

Approved PD6-15 requires preserving foreign-currency observations by original currency but prohibiting V1 finding allocations, ratios or cross-currency totals without the same currency/basis. A USD finding and EUR receipt stay separate; no market-rate lookup, manually typed conversion or currency-label substitution. Cross-currency costs can be recorded as separate evidence, not subtracted from USD. Pin supported currency meaning/precision for the event period, preserving original source denomination; no universal two-decimal or current-code assumption.

## 24. Time recognition and reporting cut-off

Approved PD6-34 requires economic date D and server-known/approval cutoff K for every projection. Date-only sources remain dates; timestamps retain source timezone/precision. Normalize actual instants only from established source timezone; no assumed bank timezone or midnight. Half-open report periods `[start,end)` use date/instant semantics declared in the report profile, with economic-cutoff inclusivity stated. Ambiguous date/time boundaries block affected recognition/period ratio rather than choosing created_at.

| Metric/event | Economic date; authoritative knowledge |
| --- | --- |
| Potential | Existing evaluation's pinned assessed service/billing scope; detection timestamp is separately the system evaluation date. Never redistribute P with recovery dates. |
| Internal confirmation / readiness | Actual Phase 4 decision/ledger approval commit timestamp for authority; source/effective action date separately recorded. Never backdate system authority. |
| Claim | Evidenced human action date; platform recorded/approved-at K separately. Draft/upload date is not claim date. |
| Acknowledgment/agreement | Evidenced vendor response/agreement date, not entry date or cash date. |
| Credit issued / pending stock | Source credit issue date plus known validity/application history as known at K. Issue date contributes to issued stock, no R flow. |
| Credit applied / offset | Evidenced effective AP application/settlement date; contributes approved principal flow then. |
| Corrected/waived unpaid payable | Evidence-backed effective posted reduction date, not a proposed replacement upload. |
| Cash | Evidenced settled/available beneficiary date; initiation/remittance instruction is not settlement. |
| Observed corrected future billing | Source later invoice/service period; monetary avoided recognition deferred. No created_at substitution. |
| Economic reversal | Actual cash return/application reversal/reinstatement date. |
| Recognition/date correction | Corrected original economic fact plus new immutable known-at entry; explicitly labeled restatement, not fabricated cash flow. |
| Direct recovery cost | Evidenced incurred/service date and paid date as separate cost metrics; neither substitutes for a recovery date. |

A report context contains tenant, period/cutoff, K/ledger high-watermark, approved policy/profile version, currency/tax/entity filters, selected event/approval/state-observation identifiers, coverage/limits and deterministic projection digest/reference. Dashboard aggregates remain views, not new aggregate findings/proofs or a promised persisted reporting subsystem. Retain enough immutable authorized action observations to reproduce former currentness/decision/evidence eligibility at K; today's `is_stale` cannot reconstruct yesterday's status. Missing historic observation support means UNKNOWN historical eligibility, not fabricated CURRENT.

Example: credit issued 2026-12-31, applied 2027-01-10. December issued stock can include it if known by the chosen K; realized application flow belongs to January. A 2026-12-31 cash receipt first approved 2027-01-15 is absent from a report known through 2027-01-05; a later-knowledge December restatement may include it, labeled with the new K. Do not overwrite the earlier report's event history. Corrections carry provenance; no general-ledger period reopening or statutory accounting claim is implemented.

## 25. Roles and approvals

| Action | Owner/Admin | Analyst | Viewer |
| --- | --- | --- | --- |
| Authorized case/history/evidence views | Yes | Yes | Read only |
| Create investigation, propose evidence/action/response/event | Yes | Yes | No |
| Assignment/priority/next action/target/follow-up/notes | Yes | Attributed operational changes within existing tenant membership | No |
| Final readiness/B; approve actioned claim/vendor monetary meaning | Yes, pinned evidence/predecessors | Propose only | No |
| Approve realization, reversal/correction, cost recognition | Yes, all relevant gates | Propose only | No |
| Final suspension, closure/reopen, successor/rebase relationship | Yes | Propose only | No |
| Financial fact/finding decisions, proof generation/review/export | Existing Phase 4/5 permissions unchanged | Existing preparation/generation only | Existing reads only |
| Vendor contact, public sharing, payments, billing or money edits | No Phase 6 V1 capability | No capability | No capability |

Approved PD6-21 requires owner/admin final authority with attributed preparer/approver, permitting the same owner/admin to prepare and approve. This does not claim segregation-of-duties compliance. A mandatory distinct approver is a non-approved alternative, not silently imposed. Analyst can append its own note revision/retraction; owner/admin can moderate by attributed events. Escalation is operational, not financial approval. Removed assignees can remain historical but cannot act after membership loss. Recheck and hold current role through authoritative commit/capture; approval-role-at-action remains frozen.

## 26. Audit trail

Preserve trusted who/when/what/role/tenant/target/reason/request/previous revision for case creation, readiness/B revision, evidence addition/review, claim/action revision/withdrawal, response, observation/proposal approval/rejection, realization/allocation, costs, instrument alias/association, reversal/correction, scope relationship, suspension/closure/reopening, workflow change and integrity observation. Successful financial event and audit commit together. No direct forged journal origin or missing-audit money. Repeated semantic success returns the existing identity/creation audit; an authorized distinct review decision remains an attributed event.

Denied/stale/idempotency/conflicting/bounded-resource attempts use safe attributed operation records where compatible with existing architecture; no successful recovery entry or other-tenant metadata. Logs contain minimal IDs/codes/version/duration, not documents, bank details, source quotations, JSON payloads or tokens. Audit is not a legal certificate or a general ledger. Read views need not fabricate authoritative mutations; meaningful integrity transitions must be auditable.

## 27. Aggregation, dashboards, ratios and recovery costs

Approved PD6-23 requires separate measures and explicit populations:

| View | Semantics / exclusions |
| --- | --- |
| Potential / internally confirmed | Existing compatible current disjoint Phase 4 scope views. Never P+V, never claims/receipts folded into these amounts. |
| Pursuit / claimed / acknowledged / disputed | Separate effective stock at K and compatible scope; revisions replace current position, not additive claims. |
| Approved recorded realization | Signed attributed cash-performance, applied-credit, liability-reduction components, including reversals; historical/exception categories shown separately. No S/Kc/forecast values added. |
| Net cash received | Actual bank component by currency/entity/basis, not necessarily finding-compatible principal; show allocation/coverage. Cash-component reversals separately visible. |
| Pending credit | Reconciled unused principal stock, not period recovery flow. Issued/application/expiry/reversal dates visible. |
| Unrealized pursuit balance | B−R only within complete compatible allocation; closure label does not remove it. Acknowledged/disputed/pending values are not additional residuals to sum. |
| Recovery ratio | R/V for active confirmed current compatible scope and complete attribution/basis reconciliation; explicitly gross before costs, numerator methods disclosed. Null if V absent/zero, stale/dismissed/unknown, material basis unresolved or coverage incomplete. No cross-currency blended percentage or average case percentages. |
| Direct recovery costs | Separately evidenced incurred/paid stocks/flows by currency and period, never automatically netted. |
| Avoided/forecast/annualized/gain-share | Unimplemented/not assessed; no numeric zero/Total Savings tile implying coverage. |

Portfolio ratio, if shown, uses sum eligible non-overlapping R divided by sum matching V in one currency/entity/tax profile, with pinned population and numerator-method mix; not ratio of unrelated cohorts, not average percentages. Historical realization from a stale/dismissed/superseded/unavailable-evidence case remains visible in an exception bucket and is not duplicated in active eligible R. Overlapping predecessor/successor scope cannot enter either sum twice. Cost or undercharge cannot offset P/R. Unknown/partial populations and resource bounds must be visible; do not market limited results as complete enterprise recovery.

Approved PD6-33 supports optional reviewed direct recovery costs (external recovery firm, legal, bank/payment, collection), each economically deduplicated and attributed with source/currency/date/approval and incurred versus paid state. No allocation of shared legal invoices by guessed percentage. Record unallocated cost separately. A deducted bank fee in N may also appear once as F; never subtract it again from N or label R−F as approved net savings. There is no automated net-savings, tax-adjusted benefit, overhead costing or gain-share metric.

## 28. Gain-share boundary

Approved PD6-24 permits no gain_share_eligible_value, commission accrual, invoice or recovery-fee billing in V1. A vendor cash/credit amount cannot be converted into platform revenue by a percent field. A later commercial policy must specify qualifying methods, gross/net/tax basis, realization/cut-off, reversals/clawback, costs, customer agreement, FX, excluded cases and forecasting treatment. No annualized forecast or validated potential creates billable value under this specification.

## 29. External communication boundary

Approved PD6-25 permits internal tracking only: people contact suppliers outside the platform; attach reviewed evidence of actual action/response. No email sending, dispute delivery, public tokens, external/vendor accounts, recipient directory, autonomous legal claim or supplier portal. Existing owner/admin JSON proof export/redaction permissions remain unchanged; recording a claim does not imply a file was sent or create an external-sharing authorization. No external messages are sent in this specification task.

## 30. Integrations boundary

Approved PD6-35 requires manual secure upload and evidence review; no connector required or created. Future ERP/AP/bank/payment/procurement evidence must preserve upstream tenant/account namespace, transaction ID/version, actual settlement versus initiation status, correction/reversal lineage, economic/knowledge dates, source hash/capture and current authorization. Imports would propose observations, never bypass owner/admin recognition, source integrity, deduplication or tax/entity allocation. Broad OCR/extraction, reconciliation automation and connector credentials are separately deferred.

## 31. Security, tenant isolation and retention

Every source, instrument, proposal, proof, case, decision, event, approval, allocation, cost, workflow record and report query stays tenant-scoped, with future database composite integrity as well as server checks. Guessable UUID/reference/hash never grants access. Authorize before revealing existence, names, bank evidence, amounts, hidden metadata, search/filter counts or audit. Cross-tenant references return controlled nondisclosing errors. Proof view access grants no extra original/export right. Private storage, verified captured downloads, server-only tokens, CSRF/origin checking, no-store and safe generated attachment names remain required.

Source text/notes are inert escaped content, not commands or prompts. No remote URL fetching or spreadsheet formula/macro execution. Recovery evidence may contain bank/customer data absent from original proof; it needs its own controlled presentation, not inclusion in a Phase 5 redacted export envelope. Never reintroduce hidden values through sibling metadata, identifiers, filenames, annotations, hashes or diagnostics. Recovery V1 export/public sharing is not added by the conceptual V1 UI; any later export requires an explicit disclosure policy.

PD6-26 inherits ordinary referenced-source preservation and truthful integrity/availability states. The approved policy requires extending those guards in a later authorized implementation to authoritative recovery evidence, approval history and reversals; reuse trusted storage/audit patterns. No universal duration, legal hold, permanent retention claim, legal erasure, offboarding or backup purge. A later explicit compliance/legal policy must govern originals, copied values, bank identifiers, proofs, artifacts, actor data, logs/backups and permissible tombstones. Evidence unavailable after approval stays an explicit warning/history category; changed bytes are quarantined and cannot support new approval. No hidden source copy or erased-data bypass.

## 32. Operational safety and concurrency

Approved PD6-27 adopts the versioned `recovery-operations/1` initial defaults, not financial invariants: actual request JSON 1 MiB; notes/reasons 4000 characters; 50 source documents and 500 evidence bindings per authoritative operation; 100 MiB cumulative reads; 25-second synchronous work; response/report content 10 MiB; history page 100 records; complete synchronous aggregate population at most 10000 relevant ledger records; two concurrent ledger operations per tenant across workers; ten new financial-authority operations per actor per rolling minute across tenants. Existing upload/proof limits remain unchanged. Do not accidentally multiply quotas by worker count or declare a truncated aggregate complete. Large valid scopes yield explicit limit/busy/retry results; safe measured/versioned tuning cannot weaken isolation, audit, integrity or monetary semantics.

PD6-36: future authoritative operation reuses organization → fresh membership → instrument/case/evidence lock ordering under PostgreSQL; pin case head/readiness/B, latest actual financial decision and scoped currentness observation, exact evaluation/proof fingerprint, evidence revision/hash/capture, counterparty association, currency/tax/precision profile, and unused instrument/case/reversal budgets. Validate all before commit; authority and trusted audit commit atomically. Concurrent change either occurs before and rejects stale inputs or waits; never combine old approval with new tax/party/source. External source writers require actual consistent byte capture and commit-bound identity verification, not just database metadata. Failure creates no partial recognized event or consumed budget.

One proposal approval wins under expected-predecessor semantics; same semantic repeated approval resolves to the original identity, distinct request key does not create another recognized allocation. Independent events compete against one locked remaining budget. Partial reversal races share the original outstanding amount. Same UUID with different meaning conflicts. Ambiguous duplicates/namespace collisions require review. Closed/stale/dismissed gates are checked under the same fence; reversal authority is the explicit historical exception described in section 19. Readers/report projections also have bounded consistent knowledge snapshots and fresh tenant membership, not mixed current dashboards assembled from separately changing queries.

## 33. Future API/product concepts

Conceptual commands only, no endpoints/schema implemented: create investigation; propose/revise readiness/B; approve readiness; record/revise/withdraw claim; record vendor response; propose reviewed observation/instrument/relationship; approve/reject realization/allocation or cost; reverse/correct with expected original budget/head; suspend/close/reopen; append workflow update/note; read case/timeline/event/evidence/history; query a bounded as-of projection. Positive monetary commands accept evidence identity/proposal predecessors, not client-supplied authoritative P/V or role. Every write uses request and semantic idempotency; conflicts cannot overwrite original results. Case lists/queries disclose pagination/coverage; an incomplete summary is explicitly incomplete.

Conceptual safe errors distinguish inaccessible/not found, forbidden role, ineligible assessment, readiness/finding stale, proposal predecessor conflict, economic duplicate ambiguity, evidence unavailable/mismatch, tax/currency/entity/scope incompatibility, budget overflow, unsupported method/group allocation, closed case, precision/date ambiguity and bounded-resource/retry. Error fields never expose bank values/paths/other-tenant IDs. Failure is not a false positive, zero recovery or deletion of historical approvals. This is a later implementation contract, not an API addition now.

## 34. Future UI/UX concepts

Executive card shows exact currency/tax-exclusive P; actual Phase 4 confirmation/currentness; B/C; explicit S/D when known; R labeled gross before evidenced costs and separated by method; N and F; Kc; compatible U; case lifecycle/closure reason and next operational action. At P=74199.90, C=60000, S=50000, cash R=30000, Kc=20000, display U=44199.90 if B=P; do not show D=24199.90 unless the vendor explicitly disputed that amount. Ratio uses V, not C, and its limitations are adjacent.

Progressive drill-down: overview → evidence-backed claim/response → instrument timeline → realization/approval/reversal → tax/deduction/party/allocation bridge → pinned finding/proof → history/as-of/coverage. “Observed credit issued, not applied”, “No approved attributed value”, “Finding now stale” and “Commercially closed, unrealized pursuit balance remains” are visible, not audit-only warnings. Analysts prepare; owner/admin sees explicit final-approval and expected-currentness conflicts; viewers read. No Approve button may imply legal certification or turn free-form text into cash.

## 35. Worked examples

All examples are independent documentation fixtures under the **approved Option A profile**. Unless explicitly changed: one authorized tenant; one current positive USD finding with P=V=B=50000.00, confirmed by the existing Phase 4 decision; OPEN/READY; a pinned COMPLETE monetary proof; hash-verified protected originals; exact tax-exclusive principal; evidenced payer/payee authority and two-decimal USD precision; no prior allocation or unresolved deductions. “Approve” means fresh owner/admin approval with R01–R10 and trusted audit, never the passage of time or a user-entered number. Omitted claim/response/cost values remain null. A stated R=0.00 means a fully enumerated approved attribution ledger has no realized value; it does not assert that no external money exists. Each aggregation excludes overlapping scopes and separates stocks, flows, methods, currencies, basis and knowledge cutoff. Arithmetic checks are documentation checks, not new financial rules.

### RW-01 — Full cash refund

- **Source facts:** Vendor remits and beneficiary bank settles 50000.00 against the exact finding principal.
- **States:** OPEN/READY; no claim is fabricated; realization becomes AT_PURSUIT_CEILING.
- **Monetary values:** P=V=B=50000.00; gross principal=net bank N=50000.00; R=50000.00; U=0.00.
- **Evidence:** Bank settlement row, remittance scope/basis and beneficiary reconciliation, captured originals.
- **Allowed action:** Approve the identified cash-performance allocation.
- **Blocked action:** Recognize initiated payment alone or automatically close the case.
- **Expected ledger result:** One positive 50000.00 allocation; immutable P and proof; case remains OPEN until explicit closure.
- **Aggregation behavior:** Cash-performance R counted once; neither P+R nor agreement+payment is a recovery total.

**Arithmetic check:** 50000.00 - 50000.00 = 0.00.

### RW-02 — Partial cash refund

- **Source facts:** An independently evidenced 30000.00 refund settles; no evidence for another payment.
- **States:** OPEN/READY, PARTIAL; unanswered remainder is not automatically disputed.
- **Monetary values:** R=N=30000.00; U=20000.00; D=null.
- **Evidence:** Exact bank row and allocation to supported principal; coverage of remaining pursuit explicit.
- **Allowed action:** Approve only the 30000.00 completed event.
- **Blocked action:** Recognize 50000.00, overwrite P to 30000.00 or infer D=20000.00.
- **Expected ledger result:** One partial realization, unchanged finding; explicit unresolved pursuit balance.
- **Aggregation behavior:** Compatible R/V displays 60.00% only with complete eligible coverage; U is not a debt finding.

**Arithmetic check:** 50000.00 - 30000.00 = 20000.00; 30000.00 / 50000.00 * 100 = 60.00.

### RW-03 — Credit issued, not applied

- **Source facts:** Vendor issues an unconditional 20000.00 principal credit; complete AP reconciliation shows unused balance.
- **States:** Credit AVAILABLE; no approved realization.
- **Monetary values:** Kc=20000.00; R=0.00; U=50000.00; cash N=null.
- **Evidence:** Issued credit, legal entity/reference, remedy scope and AP unused-credit reconciliation.
- **Allowed action:** Approve issued-credit observation and available stock.
- **Blocked action:** Treat credit face amount or vendor issue date as cash/application recovery.
- **Expected ledger result:** Stable credit root with no consumption allocation yet.
- **Aggregation behavior:** Pending credit stock 20000.00 appears separately; never add it to realized R.

### RW-04 — Credit applied

- **Source facts:** RW-03-style credit is actually applied for 20000.00 against a payable, evidenced independently.
- **States:** Credit CONSUMED; realization PARTIAL.
- **Monetary values:** R=20000.00 applied-credit; Kc=0.00; U=30000.00; N=null.
- **Evidence:** Original credit, exact AP application/payable and posted balance reduction date.
- **Allowed action:** Approve consumption of that root once.
- **Blocked action:** Add another 20000.00 because issuance and application are separate documents.
- **Expected ledger result:** One 20000.00 application allocation linked to issued root; no changed Phase 4 actual.
- **Aggregation behavior:** Noncash R 20000.00, cash component 0.00; no 40000.00 recovery.

**Arithmetic check:** 20000.00 - 20000.00 = 0.00; 50000.00 - 20000.00 = 30000.00.

### RW-05 — Credit reversal

- **Source facts:** Of an approved 20000.00 application, AP reinstates 5000.00 liability; separately consider full cancellation before any application.
- **States:** Partial application reversal; historical positive allocation retained. Pre-application cancellation changes credit stock only.
- **Monetary values:** Applied scenario R=15000.00 and U=35000.00. Unused-credit cancellation scenario R remains 0.00, Kc becomes 0.00.
- **Evidence:** Original application plus posted reinstatement; or unused-credit cancellation source, with distinct event meaning.
- **Allowed action:** Approve linked -5000.00 economic reversal in applied scenario.
- **Blocked action:** Delete application history or create -20000.00 R for a credit never realized.
- **Expected ledger result:** Positive and negative records remain; any restored credit availability needs separate evidence.
- **Aggregation behavior:** Signed applied-credit balance 15000.00; cancellation stock is not a realized loss.

**Arithmetic check:** 20000.00 - 5000.00 = 15000.00; 50000.00 - 15000.00 = 35000.00.

### RW-06 — Offset against a later invoice

- **Source facts:** Credit 20000.00 supports AP offset 12000.00 against a later invoice; unused root balance is fully reconciled.
- **States:** Credit PARTLY_CONSUMED; realization PARTIAL.
- **Monetary values:** R=12000.00; Kc=8000.00; U=38000.00.
- **Evidence:** Exact credit root, later payable identity, AP application and supported scope/basis.
- **Allowed action:** Approve actual offset as noncash remediation.
- **Blocked action:** Recompute old Phase 4 A, invent cross-invoice pricing rules or recognize the unused 8000.00.
- **Expected ledger result:** One consumption event tied to later payable and original finding remedy.
- **Aggregation behavior:** Applied-credit flow 12000.00 and remaining-credit stock 8000.00 separate.

**Arithmetic check:** 20000.00 - 12000.00 = 8000.00; 50000.00 - 12000.00 = 38000.00.

### RW-07 — Corrected replacement invoice

- **Source facts:** Original unpaid payable 120000.00 is voided and replaced by 70000.00 with effective posted liability reduction.
- **States:** OPEN/READY; liability-reduction realization AT_PURSUIT_CEILING.
- **Monetary values:** R=50000.00 noncash; N=null; P remains 50000.00.
- **Evidence:** Original unpaid status, explicit void/replacement link, supported principal and AP balance reconciliation.
- **Allowed action:** Approve proven 50000.00 payable reduction.
- **Blocked action:** Treat replacement upload alone as realization. If original was paid, require later refund/application instead.
- **Expected ledger result:** One liability-reduction allocation, never a cash receipt or edited invoice evaluation.
- **Aggregation behavior:** Noncash method shown distinctly; replacement face amount 70000.00 is not R.

**Arithmetic check:** 120000.00 - 70000.00 = 50000.00.

### RW-08 — Settlement below potential leakage

- **Source facts:** P=V=B=74199.90; claim C=74199.90; vendor agreement S=50000.00 explicitly disputes D=24199.90; 30000.00 cash settles and 20000.00 credit is issued.
- **States:** PARTLY_DISPUTED; PARTIAL realization; credit AVAILABLE until application.
- **Monetary values:** Initially R=30000.00, Kc=20000.00, U=44199.90. After approved application R=50000.00, Kc=0.00, U=24199.90.
- **Evidence:** Agreement/response allocation, bank receipt, credit and later actual AP application.
- **Allowed action:** Approve each evidenced completed method once.
- **Blocked action:** Add S to payment/credit or infer D merely from subtraction without the explicit vendor source.
- **Expected ledger result:** Separate agreement, cash, issuance, application; P/V remain 74199.90.
- **Aggregation behavior:** Final R=50000.00, never 70000.00 or 100000.00; agreement/credit stock excluded from R.

**Arithmetic check:** 74199.90 - 30000.00 = 44199.90; 30000.00 + 20000.00 = 50000.00; 74199.90 - 50000.00 = 24199.90.

### RW-09 — Acknowledgment without payment

- **Source facts:** Vendor expressly acknowledges 50000.00 but provides no settled receipt, application or effective reduction.
- **States:** ACKNOWLEDGED; OPEN/READY; no approved realization.
- **Monetary values:** S=50000.00, R=0.00, U=50000.00; N=null.
- **Evidence:** Protected vendor response with authority and scope; absence of completed-event evidence explicitly displayed.
- **Allowed action:** Approve the response as the vendor's evidenced position.
- **Blocked action:** Convert acknowledgment, scheduled transfer or agreement into R.
- **Expected ledger result:** Response history only; financial truth remains independently confirmed.
- **Aggregation behavior:** S stock shown apart from realized methods; no positive cash amount.

### RW-10 — Vendor dispute

- **Source facts:** Vendor explicitly disputes entire claim C=50000.00; no economic remedy occurs.
- **States:** DISPUTED; Phase 4 remains confirmed; case may remain OPEN.
- **Monetary values:** D=50000.00, R=0.00, U=50000.00; no assumed acknowledged amount.
- **Evidence:** Attributed response identifies amount/scope and legal-entity authority.
- **Allowed action:** Record dispute, next action and independently request financial review.
- **Blocked action:** Automatically dismiss the finding or treat dispute as negative bank recovery.
- **Expected ledger result:** Separate vendor-position event; no altered P/decision/proof.
- **Aggregation behavior:** D is a position measure, never subtracted from P or added to R.

### RW-11 — Internal validation then withdrawal

- **Source facts:** Existing confirmed decision is followed by an authorized Phase 4 needs_review decision; an earlier claim remains historical.
- **States:** Readiness BLOCKED; current V unknown; historical confirmation retained.
- **Monetary values:** P=50000.00, current V=null, R=0.00; no invented zero validation.
- **Evidence:** Actual decision IDs and recorded reason, exact case/claim predecessors.
- **Allowed action:** Suspend pursuit, record raw observations, retain earlier action; later financial confirmation uses existing Phase 4 authority.
- **Blocked action:** Continue ordinary positive approvals using old confirmation or erase the claim.
- **Expected ledger result:** Authority change observed; old readiness/action remains immutable.
- **Aggregation behavior:** Excluded from current confirmed eligible denominator; historical decision view remains reproducible at its K.

### RW-12 — False-positive decision after case creation

- **Source facts:** A recorded 10000.00 receipt predates later authorized dismissal of the finding.
- **States:** Finding false_positive; readiness BLOCKED; closure reason may be invalid financial basis.
- **Monetary values:** P history 50000.00; approved recorded R history 10000.00; current eligible ratio=null.
- **Evidence:** Historic receipt/approval plus actual later decision; no source indicating cash returned.
- **Allowed action:** Preserve exception-category receipt and close/suspend ordinary pursuit.
- **Blocked action:** Delete R, fabricate -10000.00 cash reversal or keep it in an active confirmed KPI.
- **Expected ledger result:** Invalidated-basis historical attribution clearly labeled; separate future return only with real evidence.
- **Aggregation behavior:** Historical receipt counted once in exception category, excluded from current eligible R/V.

### RW-13 — Stale finding

- **Source facts:** After approved R=10000.00, calculation-driving facts change and evaluation becomes stale.
- **States:** Existing proof retains issued completeness; financial currentness STALE; readiness BLOCKED.
- **Monetary values:** Historical P=50000.00 and R=10000.00 retained; active V/ratio=null.
- **Evidence:** Pinned earlier input revisions, later revision/currentness observation and recorded receipt.
- **Allowed action:** Retain raw subsequent transactions and reversals; obtain a new Phase 4 evaluation separately.
- **Blocked action:** Treat old COMPLETE proof as fresh authority or silently update P.
- **Expected ledger result:** Historical case frozen for new positive attribution; source/evaluation histories remain.
- **Aggregation behavior:** Stale-basis money appears as exception history once, not active confirmed recovery.

### RW-14 — Explicit successor evaluation

- **Source facts:** Same supported scope has old P=50000.00 and new P=45000.00; authorized ProofSuccessor; no recognized history on predecessor.
- **States:** Old pursuit retired; new case initially INVESTIGATION, separately confirmed/proved/readied with B=45000.00.
- **Monetary values:** Old/new P separately 50000.00/45000.00; both R=0.00; no 95000.00 aggregate exposure.
- **Evidence:** Exact same-scope successor authorization, new facts/evaluation/proof and prior unused budget retirement.
- **Allowed action:** Ready successor after explicit predecessor exclusion and all fresh gates.
- **Blocked action:** Infer succession by timestamp or perform this transfer where predecessor has recognized history.
- **Expected ledger result:** Separate evaluation/case histories with one current unused pursuit scope.
- **Aggregation behavior:** Active view selects successor once; historical predecessor remains inspectable, never summed for same money.

### RW-15 — Partial recovery then closure

- **Source facts:** R=30000.00 of B=50000.00; owner accepts commercial closure without further pursuit.
- **States:** CLOSED; PARTIAL realization; confirmed finding remains independent.
- **Monetary values:** R=30000.00; historical U=20000.00 remains unpursued exposure.
- **Evidence:** Settled receipt and attributed closure reason, date and unresolved-balance coverage.
- **Allowed action:** Close for partial settlement/commercial decision.
- **Blocked action:** Zero U, label fully recovered or convert closure to false_positive.
- **Expected ledger result:** Closure event appended; receipt and potential unchanged.
- **Aggregation behavior:** Approved history retained; open-case count excludes it but money is not deleted by operational filtering.

**Arithmetic check:** 50000.00 - 30000.00 = 20000.00.

### RW-16 — Multiple refunds

- **Source facts:** Two distinct bank transactions refund 20000.00 and 15000.00, with separate references and principal slices.
- **States:** OPEN/READY; PARTIAL.
- **Monetary values:** R=N=35000.00; U=15000.00.
- **Evidence:** Both settlement rows and explicit non-overlapping allocation to the original remedy scope.
- **Allowed action:** Approve both within case/instrument budgets.
- **Blocked action:** Merge distinct payments merely because payer/date match or repeat a row via another upload.
- **Expected ledger result:** Two stable economic roots, two signed allocations; no mutable recovered_amount edit.
- **Aggregation behavior:** Cash-performance sums exactly 35000.00 once.

**Arithmetic check:** 20000.00 + 15000.00 = 35000.00; 50000.00 - 35000.00 = 15000.00.

### RW-17 — Refund plus credit, one benefit

- **Source facts:** One 20000.00 credit is applied for 12000.00 and redeemed for 8000.00 cash, not two independent full benefits.
- **States:** Credit CONSUMED; PARTIAL overall realization.
- **Monetary values:** Applied-credit R=12000.00; cash-performance R=8000.00; total R=20000.00; Kc=0.00.
- **Evidence:** Credit root, AP application, remaining balance and matching cash redemption.
- **Allowed action:** Consume two explicit slices of one root.
- **Blocked action:** Count face credit+application+cash, or redeem already consumed 12000.00 without evidenced AP restoration.
- **Expected ledger result:** Root budget used once; actual N=8000.00 separate from noncash R.
- **Aggregation behavior:** 20000.00 total by two methods, never 40000.00.

**Arithmetic check:** 12000.00 + 8000.00 = 20000.00; 20000.00 - 12000.00 - 8000.00 = 0.00.

### RW-18 — Cash recovery and future price correction

- **Source facts:** Historical refund 10000.00 settles; supplier signs future rate correction from 20.10 to 18.40.
- **States:** Cash PARTIAL; remediation action recorded; future monetary avoidance deferred.
- **Monetary values:** R=N=10000.00; U=40000.00; avoided-realized and annualized amounts=null.
- **Evidence:** Receipt/remittance and separately reviewed correction source; no future invoice yet.
- **Allowed action:** Approve historic cash and record nonmonetary corrective action.
- **Blocked action:** Multiply rate difference by guessed future volume/horizon or add a forecast to R.
- **Expected ledger result:** One cash allocation and a separate action observation.
- **Aggregation behavior:** Only 10000.00 enters realized recovery; action count may increase without monetary effect.

**Arithmetic check:** 50000.00 - 10000.00 = 40000.00.

### RW-19 — Later invoice evidences corrected billing

- **Source facts:** Later verified invoice charges 18.40 for 1000 units after rate correction; old billed rate was 20.10.
- **States:** “Observed corrected billing”; no approved counterfactual profile.
- **Monetary values:** Actual later line=18400.00; illustrative rate-difference scenario=1700.00; monetary avoided realization=null; R=0.00.
- **Evidence:** Actual later invoice/period/quantity and correction; these do not prove future 20.10 would otherwise have continued.
- **Allowed action:** Record actual corrected billing and, separately, any existing supported Phase 4 assessment.
- **Blocked action:** Recognize 1700.00 as V1 savings/recovery, reuse refunds for that scope or invent causality.
- **Expected ledger result:** Nonmonetary observation, no avoidance financial allocation.
- **Aggregation behavior:** No monetary avoidance KPI; scenario arithmetic explicitly outside platform recognized totals.

**Arithmetic check:** 18.40 * 1000 = 18400.00; (20.10 - 18.40) * 1000 = 1700.00.

### RW-20 — Forecast not yet realized

- **Source facts:** Analyst predicts 10000.00 monthly future benefit; no later economic invoice/receipt exists.
- **States:** Attributed planning note only; no verified future realization.
- **Monetary values:** Avoided/forecast platform amounts=null; approved R=0.00.
- **Evidence:** Forecast author/assumptions documented, but no counterfactual/actual-event evidence profile approved.
- **Allowed action:** Save bounded nonfinancial planning context, labeled unapproved scenario.
- **Blocked action:** Promote prediction to realized savings, recovery or gain-share eligibility.
- **Expected ledger result:** Note history, no monetary event.
- **Aggregation behavior:** Excluded from R and avoided-value dashboards; no numeric confidence badge legitimizes it.

### RW-21 — Annualized scenario

- **Source facts:** Human projects 10000.00 per month for 12 months; actual contract ends in three months.
- **States:** Unapproved scenario; renewal/recurrence not established.
- **Monetary values:** Illustrative arithmetic 120000.00; platform annualized/realized-avoidance=null; R=0.00.
- **Evidence:** Planning assertion and contract end date, not approved future economic basis.
- **Allowed action:** Record attributed assumptions and contradiction as a note.
- **Blocked action:** Display “120000.00 saved”, auto-extend horizon or invoice gain-share.
- **Expected ledger result:** No forecast-money persistence or recognition under approved V1.
- **Aggregation behavior:** Scenario is outside all realized totals; even three-month extrapolation is not approved policy.

**Arithmetic check:** 10000.00 * 12 = 120000.00.

### RW-22 — Undercharge assessment

- **Source facts:** Existing Phase 4 assessment is UNDERCHARGE, including a possibly COMPLETE explanatory package.
- **States:** No positive finding identity and no recovery case.
- **Monetary values:** Phase 6 P/V/B/R=null/not applicable, never fabricated zero leakage.
- **Evidence:** Exact assessment result and explanatory-proof kind.
- **Allowed action:** View authorized assessment/proof.
- **Blocked action:** Create monetary case, collect supplier “overcharge” or invert sign into a new family.
- **Expected ledger result:** No recovery case or financial authority record.
- **Aggregation behavior:** No entry in positive potential/confirmed/recovery population.

### RW-23 — No-overcharge assessment

- **Source facts:** Phase 4 returns NO_OVERCHARGE with known zero delta, not positive monetary finding.
- **States:** Explanatory assessment only.
- **Monetary values:** Original assessment may have known zero delta; recovery amounts are not applicable/null.
- **Evidence:** Pinned assessment/scope and optional explanatory proof.
- **Allowed action:** Read explanation and review new evidence through existing workflows.
- **Blocked action:** Create a recovery case merely because proof is COMPLETE.
- **Expected ledger result:** No case/claim/realization identity.
- **Aggregation behavior:** Excluded from monetary-finding recovery denominators; no unknown money converted to zero.

### RW-24 — Blocked Phase 4 assessment

- **Source facts:** NEEDS_REVIEW assessment lacks a complete governing packet; potential money is unknown.
- **States:** Blocked assessment, no positive finding; COMPLETE explanatory package can explain blockers.
- **Monetary values:** P/V/B/R=null.
- **Evidence:** Exact blockers and pinned available revisions.
- **Allowed action:** Fix facts/packet through existing review and run a separately authorized Phase 4 evaluation.
- **Blocked action:** Treat processed documents/estimated amount as finding truth or use Phase 6 to bypass the block.
- **Expected ledger result:** No recovery case until a distinct eligible positive evaluation exists.
- **Aggregation behavior:** Explicit unknown assessment count, no positive monetary sum.

### RW-25 — Incomplete proof

- **Source facts:** Positive current confirmed finding exists, but its issued monetary proof is INCOMPLETE.
- **States:** OPEN/INVESTIGATION; technical completeness remains deterministic C01–C10.
- **Monetary values:** P=V=50000.00; B=null; no positive approved allocation; remaining U/ratio=null.
- **Evidence:** Pinned finding and exact incomplete package with missing requirements.
- **Allowed action:** Prepare evidence/proposal, request authorized proof repair/generation separately.
- **Blocked action:** Mark READY, send/action a platform-authorized claim or recognize cash just because an owner clicks approval.
- **Expected ledger result:** One investigation case; real-world cash observation retained if present, without attribution.
- **Aggregation behavior:** Investigation population separate from ready/eligible realization; no invented B=P.

### RW-26 — Complete proof, unconfirmed finding

- **Source facts:** COMPLETE monetary proof exists for a detected finding; no actual confirmed decision.
- **States:** OPEN/INVESTIGATION; optional human proof review does not confirm financial truth.
- **Monetary values:** P=50000.00; V/B=null; approved attribution total 0.00 with explicit non-ready coverage; ratio=null.
- **Evidence:** Exact proof package and absence of confirmation, not derived UI needs_review as a decision substitute.
- **Allowed action:** Create investigation and prepare review; existing Phase 4 owner/admin may separately decide.
- **Blocked action:** Infer V=P, READY or recovery from COMPLETE/REVIEWED alone.
- **Expected ledger result:** No automatic proof generation/confirmation/financial event.
- **Aggregation behavior:** Potential may appear in inherited view; case excluded from confirmed recovery metric.

### RW-27 — Claimed recovery without source evidence

- **Source facts:** User types “received 30000.00” with no protected bank/remittance source.
- **States:** Unsupported proposal; recognition evidence INCOMPLETE.
- **Monetary values:** Proposed raw 30000.00; approved R=0.00; independently verified actual receipt=null.
- **Evidence:** Attribution of user assertion only; missing source/settlement/basis explicitly shown.
- **Allowed action:** Save a proposal or reject it; upload/review required sources.
- **Blocked action:** Promote note/manual number to verified receipt, fake source hash or accept approval click as external evidence.
- **Expected ledger result:** No positive approval/allocation; unsupported assertion preserved under role controls.
- **Aggregation behavior:** Proposed values never enter R; no claim that cash actually received is zero.

### RW-28 — Different-currency receipt

- **Source facts:** USD finding receives an evidenced EUR 20000.00 transaction; no V1 FX attribution profile.
- **States:** Reviewed unallocated observation; affected case coverage unresolved.
- **Monetary values:** Raw receipt EUR 20000.00; USD approved R=0.00; USD-compatible attribution/ratio=null pending resolution.
- **Evidence:** Original currency, settled bank source, counterparty and scope; no supplied exchange rate authorizes conversion.
- **Allowed action:** Preserve EUR transaction with original basis and warning.
- **Blocked action:** Relabel EUR as USD, use a typed/market FX rate or sum 50000 USD +20000 EUR.
- **Expected ledger result:** No finding allocation; raw receipt remains distinct.
- **Aggregation behavior:** Separate currency observations, no cross-currency total or conversion-based ratio.

### RW-29 — Explicit allocation across multiple findings

- **Source facts:** Findings P=40000.00 and 70000.00; one 100000.00 settlement explicitly assigns 40000.00 and 60000.00 principal.
- **States:** Reviewed bundled-settlement observation; multi-finding attribution profile deferred under PD6-16 A.
- **Monetary values:** Raw 100000.00; proposed split 40000.00/60000.00; each approved case R=0.00, allocation/ratio unresolved.
- **Evidence:** Full signed allocation and bank settlement, not guessed proportions.
- **Allowed action:** Preserve source-backed allocation proposal and related-finding references for future review.
- **Blocked action:** Recognize bundled allocations in V1 or disguise one payment as independent roots.
- **Expected ledger result:** Unallocated economic instrument; explicit evidence alone does not enable deferred capability.
- **Aggregation behavior:** No 100000.00 finding-level R; 110000.00 compatible disjoint potential remains an inherited presentation view, not a new aggregate finding.

**Arithmetic check:** 40000.00 + 60000.00 = 100000.00; 40000.00 + 70000.00 = 110000.00.

### RW-30 — Ambiguous multi-finding settlement

- **Source facts:** Vendor pays 100000.00 referencing findings 40000.00 and 70000.00 but gives no allocation or extras reconciliation.
- **States:** Unallocated, ambiguous; no guessed individual monetary authority.
- **Monetary values:** Raw receipt 100000.00; per-case allocation=null; approved case totals remain 0.00 with unresolved coverage.
- **Evidence:** Bank receipt and broad settlement description; missing principal split explicitly recorded.
- **Allowed action:** Retain observation, request counterparty clarification outside the platform.
- **Blocked action:** Allocate proportionally, fill first case until capped or claim 100000.00 recovery on each.
- **Expected ledger result:** One root with no approved finding consumption.
- **Aggregation behavior:** Unallocated bank receipt shown separately from finding R; no recovery ratio for the unresolved population.

### RW-31 — Reversal after closure

- **Source facts:** Fully recorded 20000.00 receipt is later returned to the vendor after case closure.
- **States:** CLOSED throughout correction; economic reversal allowed independently of positive readiness.
- **Monetary values:** Historical positive 20000.00; signed reversal -20000.00; R=0.00; U=50000.00 if other coverage complete.
- **Evidence:** Original allocation and actual outbound settlement/date/party, not a source-free deletion request.
- **Allowed action:** Owner/admin approves linked reversal without reopening.
- **Blocked action:** Delete original, reopen automatically or reverse more than unreversed 20000.00.
- **Expected ledger result:** Both economic events retained with separate dates/audits.
- **Aggregation behavior:** Old-period inflow remains; return-period reversal shown; cumulative signed R=0.00.

**Arithmetic check:** 20000.00 - 20000.00 = 0.00.

### RW-32 — Reopening

- **Source facts:** A partially recovered case R=10000.00 was commercially closed; owner chooses renewed pursuit.
- **States:** CLOSED → OPEN; readiness independently rechecked, not automatically restored.
- **Monetary values:** P/V unchanged; R=10000.00; U=40000.00 with complete reconciliation.
- **Evidence:** Closure predecessor, reopen reason and current proof/finding/source/counterparty observations.
- **Allowed action:** Append reopen, then fresh readiness if all gates pass.
- **Blocked action:** Create duplicate case, resurrect reversed credit or reset recognized balance.
- **Expected ledger result:** Same case ID and full closure/reopen history.
- **Aggregation behavior:** Operational open-case count changes; money changes only through separately approved economic events.

**Arithmetic check:** 50000.00 - 10000.00 = 40000.00.

### RW-33 — One-cent recovery

- **Source facts:** P=V=B=0.01; a supported USD principal receipt settles 0.01 exactly.
- **States:** AT_PURSUIT_CEILING, OPEN until explicit closure.
- **Monetary values:** R=N=0.01; U=0.00.
- **Evidence:** Actual bank row and exact principal mapping; two-decimal USD fixture precision evidenced.
- **Allowed action:** Approve one cent with the same controls as larger money.
- **Blocked action:** Apply epsilon/materiality suppression, round to zero or waive source requirements.
- **Expected ledger result:** Immutable 0.01 realization once.
- **Aggregation behavior:** Exact cent retained; display precision cannot change stored amount or financial cap.

**Arithmetic check:** 0.01 - 0.01 = 0.00.

### RW-34 — Duplicate submission

- **Source facts:** Same 10000.00 bank transaction submitted twice with the same request; later repeated with a different key/upload.
- **States:** First proposal/approval authoritative; identical retry resolves existing semantic identity.
- **Monetary values:** R=10000.00, never 20000.00.
- **Evidence:** Same reviewed root/reference/beneficiary and aliases, independent of upload/hash identity.
- **Allowed action:** Return original result on identical retry; attach reviewed additional evidence without new benefit.
- **Blocked action:** Treat new UUID/document as new payment; accept same request key with changed amount.
- **Expected ledger result:** One instrument/allocation/creation audit; conflicting meaning gives explicit conflict.
- **Aggregation behavior:** One 10000.00 benefit across all documents and requests.

### RW-35 — Concurrent approval of same proposal

- **Source facts:** Two owner/admin sessions approve the exact same 30000.00 proposal concurrently using independent transactions.
- **States:** Serialized/fenced authority; one semantic approval, other resolves same result or safe stale/retry.
- **Monetary values:** R=30000.00; remaining B budget=20000.00.
- **Evidence:** Same proposal/evidence revision/root, current roles and case predecessor.
- **Allowed action:** Commit one atomic financial event with trusted audit.
- **Blocked action:** Produce two allocations/audits by worker-local locking or independent reads.
- **Expected ledger result:** No mixed revisions or duplicate benefit; no partial records after losing transaction.
- **Aggregation behavior:** 30000.00 once, never 60000.00; final budget checked at commit.

**Arithmetic check:** 50000.00 - 30000.00 = 20000.00.

### RW-36 — Analyst proposes, owner approves

- **Source facts:** Analyst reviews a 15000.00 receipt and submits proposal; authorized owner checks exact pinned evidence.
- **States:** PROPOSED → APPROVED only by fresh owner/admin authority.
- **Monetary values:** Before approval R=0.00; after approval R=15000.00, U=35000.00.
- **Evidence:** Preparer attribution, source capture, proposal revision and approver role/reason/time.
- **Allowed action:** Analyst prepares; owner/admin approves; operational analyst notes remain independent.
- **Blocked action:** Analyst self-grants approval via assignment, client role or request field.
- **Expected ledger result:** Distinct attributed preparer/approver history; no claim of mandatory dual control.
- **Aggregation behavior:** Proposed amount excluded until authoritative commit; approved 15000.00 counted once.

**Arithmetic check:** 50000.00 - 15000.00 = 35000.00.

### RW-37 — Cross-tenant attack

- **Source facts:** Tenant A analyst supplies tenant B case/proof/document/payment ID to a proposal/read command.
- **States:** Uniform authorized-not-found/denied result; no financial authority.
- **Monetary values:** No B amounts or totals revealed; neither ledger changes.
- **Evidence:** Only safe actor/own-tenant attempt code; no foreign filenames, hashes, bank data or diagnostic payload.
- **Allowed action:** Authorized reads/preparation confined to tenant A.
- **Blocked action:** Cross-tenant association, enumeration, source capture, successor or export reuse.
- **Expected ledger result:** No proposal/allocation/audit target exposing B; safe attempt record where supported.
- **Aggregation behavior:** No foreign value/count leaks through dashboards or errors.

### RW-38 — Evidence becomes unavailable

- **Source facts:** Approved R=10000.00 previously captured valid bytes; original later unavailable despite deletion safeguards.
- **States:** Historical VERIFIED_AT_APPROVAL; current evidence UNAVAILABLE; positive readiness BLOCKED.
- **Monetary values:** Recorded historical R=10000.00 remains; current eligible ratio=null, not R rewritten to zero.
- **Evidence:** Stored original hash/capture/approval and new availability observation; never claim current verification without bytes.
- **Allowed action:** Show historical record/warning; repair availability via separately reviewed evidence/proof revision as appropriate.
- **Blocked action:** Delete authoritative evidence, export unverifiable bytes or approve another positive allocation with missing required sources.
- **Expected ledger result:** Availability overlay and protected references, no silent financial reversal.
- **Aggregation behavior:** Historical amount once in evidence-exception category, excluded from current eligible numerator/denominator population.

### RW-39 — Corrected finding amount through Phase 4

- **Source facts:** Old P=50000.00 has recorded R=10000.00; new reviewed facts yield same-scope evaluation P=45000.00.
- **States:** Old financial basis stale; new case may investigate; monetary successor reconciliation deferred.
- **Monetary values:** Old P/R remain 50000.00/10000.00; new P=45000.00; no automatic transfer or extra overlapping recognition.
- **Evidence:** New Phase 4 revision/evaluation and proof; explicit supported successor relationship where valid.
- **Allowed action:** Preserve both histories and prepare reconciliation for later approved profile.
- **Blocked action:** Edit old P/proof/R, pretend its receipt is a second receipt or open an overlapping new recognition budget.
- **Expected ledger result:** Historical realization remains on original authority; investigation cannot double spend scope.
- **Aggregation behavior:** Current disjoint potential view chooses proper current evaluation; old recovery exception not duplicated on new case.

### RW-40 — Payment exceeds finding

- **Source facts:** Payment 60000.00 explicitly comprises 50000.00 finding principal and 10000.00 goodwill.
- **States:** Supported principal AT_PURSUIT_CEILING; extra consideration outside finding.
- **Monetary values:** R=50000.00; raw gross/net receipt=60000.00; extra=10000.00; U=0.00.
- **Evidence:** Settlement allocation, bank source and compatible principal/tax/entity mapping.
- **Allowed action:** Preserve full receipt and approve only explicitly identified 50000.00 principal.
- **Blocked action:** Recognize R=60000.00 or apply min(payment,P) when extra 10000.00 meaning is unknown.
- **Expected ledger result:** One root, supported principal consumption and separate non-finding consideration; no new leakage family.
- **Aggregation behavior:** Finding R=50000.00, raw receipt 60000.00 separate; goodwill never counted twice.

**Arithmetic check:** 50000.00 + 10000.00 = 60000.00.

### RW-41 — Compatible tax-inclusive credit

- **Source facts:** P=V=B=90000.00 tax-exclusive; applied credit face 108000.00 explicitly includes principal 90000.00 and VAT 18000.00.
- **States:** Credit consumed and approved compatible principal AT_PURSUIT_CEILING; tax recoverability NOT_ASSESSED.
- **Monetary values:** R=90000.00; raw applied credit=108000.00; tax adjustment=18000.00 separate; U=0.00.
- **Evidence:** Explicit source tax breakdown and actual AP application; no inferred tax rate or tax-authority benefit.
- **Allowed action:** Approve tax-exclusive principal allocation only.
- **Blocked action:** Claim recovery exceeded P, add VAT to R or assert VAT is recoverable by this customer.
- **Expected ledger result:** Immutable raw components, separately reviewed principal/basis; no Phase 4 tax calculation change.
- **Aggregation behavior:** Compatible principal ratio 100.00%; raw inclusive face/tax excluded from finding R.

**Arithmetic check:** 90000.00 + 18000.00 = 108000.00; 90000.00 / 90000.00 * 100 = 100.00.

### RW-42 — Unknown tax basis

- **Source facts:** Credit face 108000.00 against P=90000.00 has no reliable inclusive/exclusive or component evidence.
- **States:** Unallocated observation; basis UNKNOWN; recognition blocked.
- **Monetary values:** Raw credit 108000.00; compatible principal=null; approved R=0.00 with unresolved coverage; U/ratio=null.
- **Evidence:** Protected original face amount; missing tax breakdown/meaning explicitly recorded.
- **Allowed action:** Request corrected source/basis review, retain full raw observation.
- **Blocked action:** Assume 20% VAT, recognize capped 90000.00 or call unknown tax recoverable.
- **Expected ledger result:** No finding allocation even if application is otherwise evidenced.
- **Aggregation behavior:** Unknown-basis credit excluded from compatible pending-principal/realized totals; no numeric recovery ratio.

### RW-43 — Gross receipt, bank fee and net cash

- **Source facts:** Agreement and remittance explicitly discharge 50000.00 principal; bank charges evidenced fee 500.00 and credits 49500.00 net.
- **States:** Settled supported cash performance AT_PURSUIT_CEILING; direct-cost approval separate.
- **Monetary values:** S=gross principal=R=50000.00; N=49500.00; F=500.00 if separately approved; no platform net-savings metric.
- **Evidence:** Gross-principal discharge/remittance, bank fee and beneficiary net credit; exact source reconciliation.
- **Allowed action:** Approve gross verified principal recovery with qualified label and separate fee/cash components.
- **Blocked action:** Collapse S/R/N, show unqualified “50000.00 cash saved” or subtract fee twice from N.
- **Expected ledger result:** One benefit and one linked direct cost, immutable raw gross/net components.
- **Aggregation behavior:** R/V=100.00% gross-before-costs when complete; N and F separately visible, no automatic net value.

**Arithmetic check:** 49500.00 + 500.00 = 50000.00.

### RW-44 — Withholding unresolved

- **Source facts:** Agreement 50000.00; bank settles independently evidenced tax-exclusive principal 49500.00; 500.00 withholding entitlement/discharge remains unclear.
- **States:** Known portion approved; overall realization UNKNOWN because material reconciliation is UNRESOLVED.
- **Monetary values:** S=50000.00; R=N=49500.00; deduction observation=500.00; full gross performance/withholding recovery=null; U/overall ratio=null pending reconciliation.
- **Evidence:** Net principal remittance/settlement; deduction source does not establish tax entitlement, beneficiary discharge or recoverability.
- **Allowed action:** Approve independently supported 49500.00 slice, retain unresolved 500.00.
- **Blocked action:** Recognize gross 50000.00 or silently equate withholding with bank cost/recoverable tax.
- **Expected ledger result:** Partial allocation with explicit unresolved component; no invented tax benefit.
- **Aggregation behavior:** Known recorded R displayed with incomplete coverage; no 99.00% eligible population ratio until material reconciliation is complete.

**Arithmetic check:** 50000.00 - 49500.00 = 500.00.

### RW-45 — Parent/subsidiary payer

- **Source facts:** Invoice supplier Subsidiary A; payment 20000.00 from Parent B, same group but distinct legal entity.
- **States:** Attribution blocked before reviewed agency/discharge evidence; READY restored only after explicit association review.
- **Monetary values:** Raw receipt 20000.00; before association R=0.00 with unresolved coverage; afterward supported R=20000.00.
- **Evidence:** Dated mandate/authority, remittance and exact original obligation/beneficiary, not group website or name similarity.
- **Allowed action:** Owner/admin approve source-backed cross-entity relationship applicable on payment date, then separately approve realization.
- **Blocked action:** Infer payer entitlement from parent/subsidiary status or use a later nonretroactive mandate for earlier payment.
- **Expected ledger result:** Immutable association and approval pins; no merged legal identities.
- **Aggregation behavior:** Only associated compatible principal enters R; raw payment remains visible separately beforehand.

### RW-46 — Rename versus acquisition

- **Source facts:** Vendor changes trading name with same evidenced legal identifier; alternatively another company acquires assets without documented liability transfer.
- **States:** Rename continuity review can preserve identity; acquisition attribution remains BLOCKED.
- **Monetary values:** Proposed 10000.00 receipt can become R only in fully evidenced continuity/authorization scenario; acquisition R unresolved, not assumed.
- **Evidence:** Registry/source continuity and transaction scope; acquisition additionally needs assignment/discharge/beneficiary evidence.
- **Allowed action:** Record dated aliases with source and approve only supported economic identity.
- **Blocked action:** Merge entities by similar names, asset purchase or new logo; rewrite earlier source identity.
- **Expected ledger result:** Stable instrument/case identities with explicit continuity history, no fuzzy identity inference.
- **Aggregation behavior:** One benefit if qualified, never duplicate by old/new names; acquisition observation not included in R without gates.

### RW-47 — Shared processor / intercompany settlement

- **Source facts:** Statement shows generic processor payment 10000.00; an intercompany note claims it discharged supplier obligation.
- **States:** Counterparty/beneficial attribution UNRESOLVED.
- **Monetary values:** Bank observation 10000.00; compatible principal allocation=null; approved R=0.00 with unresolved coverage.
- **Evidence:** Missing underlying merchant/customer transaction and authorized intercompany discharge relationship.
- **Allowed action:** Preserve raw evidence and request precise mandate/reconciliation.
- **Blocked action:** Associate by processor name, account ownership alone or internal unsupported statement.
- **Expected ledger result:** No recognized allocation until identity, beneficiary and obligation mapping are evidenced and reviewed.
- **Aggregation behavior:** Unallocated bank amount separate; no positive finding-level ratio.

### RW-48 — Case ownership and priority change

- **Source facts:** Analyst assigns another active analyst, changes priority/target/follow-up and writes an internal next action; existing R=10000.00.
- **States:** Workflow revisions only; lifecycle/readiness/finding authority unchanged.
- **Monetary values:** P/V/B/R unchanged; no changed claim, evidence or recognized amount.
- **Evidence:** Attributed operational revision, tenant membership and previous field values.
- **Allowed action:** Bounded role-controlled workflow changes with history.
- **Blocked action:** Gain owner/admin RBAC from assignment, trigger vendor contact or cause financial approval by escalation.
- **Expected ledger result:** Nonfinancial operational events, immutable financial history untouched.
- **Aggregation behavior:** Workload/priority views may change; financial totals cannot.

### RW-49 — Commercial write-off / not pursued

- **Source facts:** Valid confirmed 50000.00 finding has no realization; management opts not to pursue for relationship/economics reasons.
- **States:** CLOSED — NOT_PURSUED with explicit reason; finding remains confirmed.
- **Monetary values:** R=0.00; historical U=50000.00; no recovered value or accounting expense inferred.
- **Evidence:** Owner/admin decision/rationale/date, unresolved pursuit coverage; no vendor liability waiver.
- **Allowed action:** Close commercial strategy with honest unpursued balance.
- **Blocked action:** Mark false_positive, declare statutory time bar, record bad-debt write-off or set P/U to zero.
- **Expected ledger result:** Closure history separate from financial decision; reopen remains explicit.
- **Aggregation behavior:** Closed strategy segment retains known unresolved amount; recovery KPI cannot show 100% from abandonment.

### RW-50 — Direct recovery costs

- **Source facts:** Gross realized R=20000.00; reviewed legal fee USD 2000.00 incurred/paid and collection fee USD 1000.00 incurred but unpaid; another EUR 500.00 fee.
- **States:** Recovery approval unchanged; separate cost proposals/approvals with incurred/paid axes.
- **Monetary values:** USD incurred F=3000.00, USD paid F=2000.00; EUR incurred 500.00 separate; no net-savings metric.
- **Evidence:** Cost invoices/mandates and payment where claimed paid, direct case allocation and economic identity.
- **Allowed action:** Track costs independently; leave shared/unallocated fees unallocated without evidence.
- **Blocked action:** Edit P/R, subtract unpaid costs automatically, combine EUR/USD or deduct bank charges again from already-net N.
- **Expected ledger result:** Attributed cost history linked to scope, no new recovery benefit or original-leakage recalculation.
- **Aggregation behavior:** R=20000.00 gross-before-costs; cost currency/status views separate, no USD 3500.00 mixed-currency cost total.

**Arithmetic check:** 2000.00 + 1000.00 = 3000.00.

### RW-51 — Credit issue and application across reporting years

- **Source facts:** Credit 20000.00 issued 2026-12-31, applied 2027-01-10; both approved/known by 2027-01-20.
- **States:** December-end AVAILABLE stock; January application consumes it.
- **Monetary values:** December-end Kc=20000.00 and December R flow=0.00; January R flow=20000.00 and later Kc=0.00.
- **Evidence:** Source issue/application dates, AP reconciliation and immutable approval known-at times.
- **Allowed action:** Reproduce December and January views at stated K/period/profile.
- **Blocked action:** Recognize December recovery from issue date, use upload created_at or add December stock+January flow as total recovery.
- **Expected ledger result:** Separate issue/application events; December stock reconstructed from economic history known at K.
- **Aggregation behavior:** Annual 2026 R excludes application; 2027 R includes it once, with explicit late-knowledge coverage if relevant.

### RW-52 — Late approval and corrected economic date

- **Source facts:** Receipt 10000.00 initially evidenced 2026-12-31, approved 2027-01-15; 2027-01-20 correction establishes actual settlement 2027-01-02.
- **States:** Original approval/date preserved; corrected date effective only under new knowledge cutoff.
- **Monetary values:** At K=2027-01-05 no approved R; at K=2027-01-16 December view includes 10000.00; at K=2027-01-21 restated December 0.00, January 10000.00.
- **Evidence:** Original source plus correction and server-established approval/correction order; no forged backdated authority.
- **Allowed action:** Append de-recognition/replacement of period attribution, retain same receipt root and old report context.
- **Blocked action:** Mutate original date, imply a bank return or overwrite K=January16 report history.
- **Expected ledger result:** One economic benefit with immutable time correction lineage.
- **Aggregation behavior:** Full-history net R=10000.00, never doubled across date corrections; each as-known report reproducible.

### RW-53 — Different payee / benefited customer

- **Source facts:** Invoice customer A; vendor pays customer affiliate B 10000.00, with no assignment or beneficial discharge evidence.
- **States:** Beneficiary association BLOCKED, even if A/B share tenant access.
- **Monetary values:** Raw B receipt=10000.00; A-compatible attribution=null; case approved R=0.00 with unresolved coverage.
- **Evidence:** Bank payee and customer identity; missing mandate, beneficiary reconciliation and original obligation discharge.
- **Allowed action:** Record observation and propose explicit source-backed association.
- **Blocked action:** Treat organization membership/group ownership as A's recovery or assign B's money by user assertion.
- **Expected ledger result:** No authorized finding allocation until reviewed relationship applies on economic date.
- **Aggregation behavior:** No cross-entity eligible ratio; raw amount remains a separately identified observation.

### RW-54 — Concurrent independent payments exceed remaining budget

- **Source facts:** Two distinct supported 30000.00 payments are concurrently proposed against B=50000.00.
- **States:** First approval commits; second fails stale/budget recheck safely.
- **Monetary values:** R=30000.00; unused B=20000.00; raw observed payments total=60000.00.
- **Evidence:** Distinct roots and explicit scope, current shared case predecessor/unused budget.
- **Allowed action:** Preserve both raw receipts; request a newly evidenced compatible second allocation/extras review if one is supportable.
- **Blocked action:** Commit R=60000.00 or silently truncate second proposal from 30000.00 to 20000.00.
- **Expected ledger result:** One positive approval; second no partial money/audit success; raw second observation not deleted.
- **Aggregation behavior:** R=30000.00 once until separately approved corrected proposal; full raw receipt view 60000.00 is not finding R.

**Arithmetic check:** 30000.00 + 30000.00 = 60000.00; 50000.00 - 30000.00 = 20000.00.

### RW-55 — Source integrity changes during approval

- **Source facts:** Proposal says 10000.00; required bank source bytes or approved tax/counterparty revision changes during capture/approval.
- **States:** Safe INTEGRITY_CONFLICT or STALE_INPUT; no positive authority commit on mixed inputs.
- **Monetary values:** Proposed 10000.00 remains unapproved; R unchanged 0.00.
- **Evidence:** Bounded consistent original capture/hash, pinned material revisions and commit-time fences.
- **Allowed action:** Abort/retry after explicit fresh source/revision review; expose safe error code.
- **Blocked action:** Trust stored filename/hash metadata, mix old basis with new source or emit partial approved event.
- **Expected ledger result:** No recognized/audit orphan; prior immutable history preserved.
- **Aggregation behavior:** Failed proposal never enters money totals; errors expose no source bytes, account details or foreign-tenant data.

### RW-56 — Cash return versus recognition correction

- **Source facts:** One 10000.00 bank receipt was attributed incorrectly for 3000.00; alternatively actual 3000.00 is later sent back. These are independent alternatives, not both applied.
- **States:** Owner/admin correction permitted even when CLOSED/stale; distinct economic versus attribution reversal types.
- **Monetary values:** Either corrected R=7000.00 with actual incoming bank N still 10000.00, or R=7000.00 plus separately evidenced outgoing cash 3000.00.
- **Evidence:** Original receipt/allocation and corrected attribution source; alternative requires actual outbound bank settlement/date.
- **Allowed action:** Append linked -3000.00 de-recognition or economic reversal with precise type and remaining budget.
- **Blocked action:** Fabricate bank outflow for an accounting error, delete original or reverse same slice twice.
- **Expected ledger result:** Signed attribution history and raw bank facts remain separate and immutable.
- **Aggregation behavior:** R=7000.00 once; cash-flow period totals reflect only actual settled events; correction is labeled restatement, not payment.

**Arithmetic check:** 10000.00 - 3000.00 = 7000.00.

## 36. Acceptance criteria for future implementation

These are **future acceptance requirements, not implemented tests or passing results**. Product policy is approved; these requirements may be implemented only after specification merge and separate explicit implementation authorization. Non-approved alternatives cannot be used without separate policy approval and revision of the affected criteria. A future test suite must use real independent PostgreSQL transactions for races and independent source bytes/economic reference cases, rather than mirroring a calculator. Existing Phase 4/5 financial golden cases, tenant isolation, proof/export integrity, C01–C10 and immutable-state protections must remain unchanged.

| ID | Future scenario and required result | Trace |
| --- | --- | --- |
| AC-01 | Only a positive existing evaluation creates a case. Undercharge/no-overcharge/blocked assessments and their explanatory proofs cannot create monetary identity. | PD6-01; RW-22–24 |
| AC-02 | Missing proof, INCOMPLETE proof or unconfirmed/stale positive finding permits investigation with warnings; B/READY/positive realization remain blocked. | PD6-01/02/05; RW-25/26/13 |
| AC-03 | Current V derives only from actual confirmation and currentness, never a typed number/derived UI label. B is an explicit commercial subset, not partial financial truth. | PD6-02; RW-11 |
| AC-04 | Case retry, proof reissue/schema revision, extraction rerun and close/reopen resolve same tenant/evaluation identity without new benefit. | PD6-03/09/20; RW-32/34 |
| AC-05 | All orthogonal axes and transitions preserve unrelated states; complete proof, acknowledgment, full B recovery and assignment cannot automatically close/confirm/realize. | PD6-04; RW-01/09/48 |
| AC-06 | Full/partial supported settled principal allocations retain exact amount/date/method and all R01–R10 pins; initiated payment/source-free note cannot qualify. | PD6-05/06/22; RW-01/02/27 |
| AC-07 | Cash, applied credit, payable reduction and other consideration remain distinct; unsupported barter/service-credit issue cannot become a new financial family. | PD6-07; RW-07/18 |
| AC-08 | Issued credit contributes only reconciled pending stock; application/cash redemption consume one root and cannot duplicate face value. | PD6-08/09; RW-03/04/17 |
| AC-09 | Partial/full cancellation before application changes only Kc; application reversal has linked negative R and evidenced restored balance. Expiry is not guessed. | PD6-08/10; RW-05 |
| AC-10 | Distinct supported refunds accumulate once; reference collision, missing namespace or uncertain duplicate blocks additional consumption, not automatic merging. | PD6-09/36; RW-16/34 |
| AC-11 | Correction/reversal preserves original money/source/actor/date; no DELETE/in-place UPDATE of approved history; reversal sum cannot exceed original outstanding budget. | PD6-10; RW-31/56 |
| AC-12 | Closed/stale/dismissed case permits authorized corrective negatives with evidence, while blocking ordinary positives; correction does not fabricate bank cash return. | PD6-10/18–20; RW-31/56 |
| AC-13 | Vendor acknowledgment/dispute/conditional response preserves explicit partial coverage; unknown D is not automatically C−S/P−S. | PD6-11; RW-08–10 |
| AC-14 | Draft/follow-up/withdrawn/replaced claims are separate immutable action history; one effective C≤B, no repeated-claim summation or inferred external delivery. | PD6-12/25; RW-08/11 |
| AC-15 | Later verified corrected invoice remains a nonmonetary observation; rate-difference/counterfactual/forecast cannot enter R or gain-share. | PD6-13; RW-18–20 |
| AC-16 | Annualized prediction is attributed unapproved scenario, no monetary forecasting fields/KPI or unsupported twelve-month continuation. | PD6-14/24; RW-21 |
| AC-17 | Foreign-currency receipt/cost retains original denomination; no typed FX, label conversion, mixed sum or blended ratio. | PD6-15; RW-28/50 |
| AC-18 | Explicit and ambiguous bundled multi-finding settlements both remain unallocated under V1 A; no proportional/cap-first/fake-root splitting. | PD6-16; RW-29/30 |
| AC-19 | Excess payment requires explicit compatible principal/extras evidence; no min(receipt,P). Full raw amount is preserved while allocation remains within B. | PD6-17; RW-40 |
| AC-20 | Material staleness invalidates current authority without rewriting prior approval/evidence. Currentness UNKNOWN does not mean current. | PD6-18; RW-13 |
| AC-21 | Only an explicit supported same-scope successor relationship retires unused pursuit. Existing R blocks V1 monetary reallocation/overlapping successor recognition. | PD6-18; RW-14/39 |
| AC-22 | Dismissal moves recorded recovery to invalidated-basis exception category, not deletion/cash-return or active eligible ratio. | PD6-19; RW-12 |
| AC-23 | Closure preserves U/P/V/R and requires final authority/reason; reopening retains same case, does not restore old readiness or reversed amount. | PD6-20/32; RW-15/32/49 |
| AC-24 | Owner/admin final monetary authority, analyst preparation/workflow and viewer reads are enforced server-side, including same-role preparer approval policy and explicit lack of mandatory dual control. | PD6-21; RW-36/48 |
| AC-25 | Membership revocation/role change races against approval and source capture; independent transactions either serialize correctly or return safe stale/denied outcome with no benefit. | PD6-21/36; RW-35/55 |
| AC-26 | Actual captured bytes/hash/size plus method evidence are required; filename/stored hash/manual note alone is insufficient; unavailable/mismatch blocks new positives. | PD6-22/26; RW-27/38/55 |
| AC-27 | Report numerator/denominator use matching disjoint current confirmed currency/entity/basis population; methods/costs/coverage disclosed, no average-case ratio or funnel summation. | PD6-23; RW-02/08/12–14 |
| AC-28 | Null versus known zero, pending credit versus realized, N versus R, historical exceptions versus eligible population remain explicit in API concepts/UI/report references. | PD6-23/28/29; RW-03/42–44 |
| AC-29 | No gain-share field/accrual/invoice/payment block/public share/vendor contact/automated claim is introduced; existing proof JSON export rights remain unchanged. | PD6-24/25; RW-18/21 |
| AC-30 | Referenced recovery originals/history receive integrity/delete safeguards, while loss remains an honest overlay; no automatic erasure/universal retention/compliance claim. | PD6-26; RW-38 |
| AC-31 | Exact resource boundaries return explicit bounded/retry results without truncating evidence/amounts/totals; cross-worker tenant capacity and cross-tenant actor quota cannot multiply. | PD6-27; RW-55 |
| AC-32 | Inclusive 108000.00 credit with explicit 90000.00 principal/18000.00 tax permits only 90000.00 compatible R; unknown tax basis blocks allocation/ratio; no assumed tax recoverability. | PD6-28; RW-41/42 |
| AC-33 | Evidenced principal discharge 50000.00, bank fee 500.00 and net receipt 49500.00 produce qualified gross R=50000.00 and separate N/F; no automatic net metric. | PD6-29/33; RW-43 |
| AC-34 | Unresolved withholding/deductions cannot be treated as cash/tax benefit; independently supported net principal slice allowed, overall unresolved ratio/U remain null. | PD6-28/29; RW-44 |
| AC-35 | Parent/subsidiary, rename/acquisition, processor/intercompany and different payee require dated evidence-backed identity/authority/beneficiary; no fuzzy matching/group inference. | PD6-30; RW-45–47/53 |
| AC-36 | Assignment/priority/target/next action/follow-up/notes/escalation changes append history but cannot alter financial figures/evidence/roles or trigger sending. | PD6-31; RW-48 |
| AC-37 | Valid commercial not-pursued reasons preserve financial truth and unresolved pursuit; legal limitation concern and accounting write-off remain unclaimed. | PD6-32; RW-49 |
| AC-38 | Direct costs retain original currency, source, economic identity and incurred/paid history; shared costs not guessed, duplicates not counted, costs not subtracted from R/P/N again. | PD6-33; RW-43/50 |
| AC-39 | Economic claim/acknowledgment/issue/application/cash/reduction/reversal dates drive their own metrics; created_at/upload/approval date cannot substitute. | PD6-34; RW-51 |
| AC-40 | K/high-watermark/profile/coverage reproduces original as-known view and labeled later restatement; server-known time cannot be backdated; current is_stale alone cannot fabricate past eligibility. | PD6-34; RW-52 |
| AC-41 | Exact midnight/date-only/timezone/period boundaries and ambiguous source dates are explicit; precision ambiguity returns block, not guessed period attribution. | PD6-34/37; RW-51/52 |
| AC-42 | Manual uploaded evidence review suffices; no live bank/AP/ERP connector or new extraction requirement. Imported/source instructions are inert and never authority. | PD6-35; RW-27/47 |
| AC-43 | Identical concurrent requests, different-key semantic duplicates and same-key changed meaning preserve one economic identity/approval with safe conflicts and no duplicate creation audit. | PD6-36; RW-34/35 |
| AC-44 | Distinct payments compete against locked B/instrument budget; approval racing with B revision, case closure, finding revocation or credit consumption cannot over-allocate or truncate. | PD6-36; RW-54 |
| AC-45 | Approval races with governing facts, proof source, tax basis, counterparty revocation and source-byte changes use one consistent pinned context or abort/retry; no mixed financial finding/recovery. | PD6-36; RW-55 |
| AC-46 | Independent concurrent reversal requests share outstanding original budget; transaction/audit failure rolls back all authoritative event/allocation/consumption state. | PD6-10/36; RW-31/56 |
| AC-47 | Decimal exactness, one cent, maximum/excess scale/overflow, unsupported currency quantum and ratio display rounding preserve monetary results; no float/epsilon/hidden rounding. | PD6-37; RW-33 |
| AC-48 | Cross-tenant IDs/filters/history/attachment/error metadata and redacted proof envelopes cannot leak recovery data; internal account masking does not mutate canonical evidence. | PD6-21/22/26; RW-37/53 |
| AC-49 | Every financially authoritative success has trusted immutable who/when/what/reason/predecessor audit; forged journal origins, disabled guards and partial financial/audit commits fail. | PD6-10/21/36; RW-35/55 |
| AC-50 | Existing Phase 4 amounts/policy/rounding/credit bridge and Phase 5 canonical proof/fingerprint/C01–C10/export/redaction/immutability remain unchanged; no new family/aggregate finding or proof. | All decisions; RW-07/19/24/29/39 |

## 37. Structured self-review

This historical specification review identifies **approved policy mitigations, not deployed protections**. Each row refers to APPROVED Option A decisions; its original implementation-status column is now explicitly historical. Current review-branch implementation evidence and residual limitations are recorded in [implementation validation](phase6-validation.md). Where a capability is deferred, its exclusion is the approved V1 guard; it is not proof that later implementation is safe. Financial/legal/tax evidence remains human-reviewed within explicit limitations.

| ID | Risk reviewed | Approved policy guard / residual limitation | Trace | Policy / implementation status |
| --- | --- | --- | --- | --- |
| SR-01 | Recovery counted without evidence | R01–R10 and actual settled/applied/reduced source; no note/click alone. | PD6-05/22; RW-27 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-02 | Credit counted at issuance and again at application | Issuance stock versus consumption flow; one root budget. | PD6-08; RW-03/04 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-03 | Refund plus related credit double counted | Root consumed by slices; AP restoration required before reuse. | PD6-08/09; RW-17 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-04 | Avoided value mixed with cash | Monetary avoidance deferred; corrected-billing observation separate. | PD6-13; RW-18/19 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-05 | Forecast mixed with realized | Forecast-money metrics deferred; attributed scenario is not a benefit. | PD6-14; RW-20/21 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-06 | User-entered recovery treated as verified | Reviewed protected evidence plus owner/admin approval, no free-entry money authority. | PD6-05/22; RW-27 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-07 | Cross-tenant disclosure/association | Server authorization before existence, tenant-safe relationships and safe errors. | PD6-21/22/36; RW-37 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-08 | Analyst escalation to financial approver | Server final-role checks; assignment/escalation never grants RBAC. | PD6-21/31; RW-36/48 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-09 | Historical money/evidence mutated | Append-only events and revisions; new facts require Phase 4 evaluation. | PD6-10/18; RW-39 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-10 | Reversal deletes history or invents cash return | Linked signed event with economic/correction distinction and unreversed budget. | PD6-10; RW-31/56 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-11 | Stale finding ignored | Currentness gate and retained history/exception category; no COMPLETE override. | PD6-18; RW-13 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-12 | Successor double counts predecessor money | Explicit supported scope relation; existing-R reconciliation/overlapping recognition deferred. | PD6-18; RW-14/39 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-13 | Dismissed finding creates recovery ambiguity | Invalidated-basis history separate; no fabricated zero/return/current ratio. | PD6-19; RW-12 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-14 | Multi-finding settlement guessed allocation | Both explicit and ambiguous bundled allocations deferred; no proportional split. | PD6-16; RW-29/30 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-15 | Recovery exceeds finding | Evidence-based principal/extras, B cap after attribution; no min heuristic. | PD6-17; RW-40 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-16 | Mixed currency total or cost netting | Original currencies preserved; FX and cross-currency ratios deferred. | PD6-15/33; RW-28/50 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-17 | Closure implies full recovery | Explicit commercial strategy separate; U/P/R retained. | PD6-20/32; RW-15/49 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-18 | Vendor acknowledgment/dispute overrides truth | S/D are evidenced positions, separate Phase 4 confirmation/dismissal. | PD6-11; RW-09/10 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-19 | Claim amount becomes recovery | Actual action/source C versus completed economic method R; follow-ups not summed. | PD6-12; RW-08/09 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-20 | COMPLETE proof implies commercial validation | Actual confirmed decision, ready approval and realization are separate gates; human proof review optional. | PD6-01/02/05; RW-25/26 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-21 | Duplicate recovery upload/request | Stable economic root independent of hash/UUID/document, request plus semantic identity. | PD6-03/09/36; RW-34 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-22 | Concurrent approval race/mixed inputs | PostgreSQL fences, current roles, captured source identity and shared budget at commit. | PD6-36; RW-35/54/55 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-23 | Gain-share inflated by forecast/potential | Gain-share eligibility/billing wholly deferred pending commercial policy. | PD6-24; RW-21 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-24 | Legal debt/limitation/tax entitlement claimed | Internal evidence record only; no legal treatment or recoverability invention. | PD6-28/32; RW-41/49 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-25 | External communication accidentally in V1 | Record human action outside platform; no sending/share/recipient workflow. | PD6-25; RW-09/48 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-26 | Payment blocking/automatic bank action added | No firewall, pay controls, connector payment or autonomous pursuit. | PD6-25/35; RW-47 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-27 | Phase 4/5 policy contradiction | Byte-identical approved policies; no new family/evaluation edits/proof mutations. | PD6-18/22; RW-07/24/39 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-28 | Accounting/general-ledger terminology confusion | Qualified gross principal recovery, commercial closure; no statutory postings/net-savings/IFRS claim. | PD6-29/32/33; RW-43/49/50 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-29 | Created_at drives wrong year/period | Economic dates plus server K; stock/flow and corrections separated. | PD6-34; RW-51/52 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-30 | Irreversible evidence deletion or false permanence | Extend referenced-source safeguards; later compliance policy needed; availability overlay honest. | PD6-26; RW-38 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-31 | Inclusive VAT falsely exceeds exclusive finding | Explicit principal/tax mapping; compatible cap and ratio only; unknown blocks. | PD6-28; RW-41/42 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-32 | Gross settlement/gross receipt/net cash collapsed | Separate S, actual gross performance, deduction components, N and qualified R. | PD6-29; RW-43/44 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-33 | Withholding assumed recoverable/discharged | Independently supported net slice only; unresolved component excludes ratio. | PD6-28/29; RW-44 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-34 | Wrong legal entity/beneficiary by fuzzy names | Source-backed dated association/continuity, not name/group/processor inference. | PD6-30; RW-45–47/53 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-35 | Workflow edit changes money | Operational revision has no approval/recognition/evidence side effect. | PD6-31; RW-48 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-36 | Valid unpursued case labeled false positive | Owner/admin commercial closure separate from actual Phase 4 decision. | PD6-32; RW-49 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-37 | Recovery cost changes original leakage or is subtracted twice | Direct costs separate, incurred/paid/currency; no automatic net metric or guessed allocation. | PD6-33; RW-43/50 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-38 | Backdated approval/current correction rewrites past | Server K and immutable date correction lineage/high-watermark/report profile. | PD6-34; RW-52 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-39 | Small amounts or unsupported precision disappear | Exact Decimal/20,6 boundaries, one-cent preservation, explicit precision errors. | PD6-37; RW-33 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-40 | Resource limit hides valid money | Bounded failure/coverage, no financial/evidence truncation or cohort mislabeling. | PD6-27; RW-54/55 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-41 | Forged/missing audit success | Existing trusted origins extended later; event/allocation/audit atomic, no direct arbitrary audit INSERT. | PD6-21/36; RW-35/55 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-42 | New event proposed after closed/stale freeze blocks correction | Positive gates distinct from historical corrective-negative permission. | PD6-10/20; RW-31/56 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-43 | Pending credit/unallocated receipt hides unknown as zero | Explicit nullable compatible principal and coverage; known ledger zero not actual receipt zero. | PD6-08/23/28; RW-27/28/42 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |
| SR-44 | Hidden recovery data reappears in disclosure/export metadata | Recovery evidence not appended to canonical/redacted proof envelopes; no new recovery export, private role-scoped presentation. | PD6-22/25/26; RW-37/53 | POLICY APPROVED; HISTORICAL SPEC CHECKPOINT — SEE VALIDATION |

Product tradeoffs explicitly approved through Option A on 3 October 2026: investigation before confirmation; gross-principal rather than net-bank recovery metric; partial recognition with unresolved remainders; optional direct costs; owner/admin same-role preparer approval; deferral of monetary avoidance/forecasts, bundled settlements, recognized-history successor reconciliation, FX, exports/integrations and gain-share. These approvals do not authorize implementing any deferred capability. Counterparty/tax/legal interpretations, production load capacity, compliance retention and real-bank reconciliation remain external/future policy limitations.

**Approval dependency review, 3 October 2026:** the complete Option A profile was reviewed before approval/status wording was changed. No contradiction between approved Option A policies was found. The review covered every decision, all definitions/invariants/lifecycle gates, all 56 worked examples and all 50 future acceptance rows. The table records that consistency review; it adds no policy, capability or financial calculation.

| Review area | Approved decisions checked | Consistency result / worked examples |
| --- | --- | --- |
| Authority, identity and readiness | PD6-01, PD6-02, PD6-03, PD6-04, PD6-05, PD6-21, PD6-22 | Investigation is not READY; V derives from actual financial confirmation, B is commercial, and COMPLETE is not financial approval. Proof revisions do not duplicate a case. RW-22–27, RW-32, RW-36. |
| Completed methods and partial realization | PD6-05, PD6-06, PD6-07, PD6-08, PD6-09 | Cash performance, applied credit and unpaid-liability reduction remain separate; issuance/acknowledgment is not realization. Explicit partial slices retain their own evidence/budgets. RW-01–10, RW-16–17. |
| Claims and vendor positions | PD6-11, PD6-12 | Current C/S/D are evidenced positions, not an additive recovery funnel; unknown disputes are not inferred. A receipt does not require a fabricated prior claim. RW-01–02, RW-08–11. |
| Immutable history, stale basis and dismissal | PD6-10, PD6-18, PD6-19, PD6-20, PD6-26 | Authority loss freezes ordinary positive approvals without deleting bank/approval facts; explicit corrective negatives remain available, including after closure. RW-11–15, RW-31–32, RW-38–39, RW-56. |
| Forecast, avoidance and gain-share | PD6-13, PD6-14, PD6-24 | Actual corrected billing remains an observation; scenario arithmetic creates no recognized avoidance, annualized amount or billing base. RW-18–21. |
| Currency, allocations and excess | PD6-15, PD6-16, PD6-17, PD6-18, PD6-23 | No mixed-currency sum, guessed/cap-first attribution, shared V1 settlement allocation or duplicate successor budget. Explicit principal/extras preserve the full raw receipt. RW-14, RW-28–30, RW-39–40, RW-50, RW-54. |
| Tax, gross/net and direct costs | PD6-28, PD6-29, PD6-33 | 108000 inclusive credit contributes only evidenced 90000 principal when applied. Evidenced bank fees remain separate from gross principal performance and N. An independently supported net slice may be recognized while material withholding keeps U/overall ratio unknown. RW-41–44, RW-50. |
| Economic counterparty and beneficiary | PD6-30 | Dated source-backed agency/continuity/beneficiary relationships control attribution; names, group links, processors, acquisition and tenant membership alone do not. RW-45–47, RW-53. |
| Workflow and commercial closure | PD6-20, PD6-21, PD6-31, PD6-32 | Assignment/priority/follow-up/escalation has no financial side effect; partial/not-pursued closure preserves truth and unresolved money. RW-15, RW-32, RW-48–49. |
| Reporting dates, metrics and coverage | PD6-23, PD6-29, PD6-33, PD6-34 | Economic dates and server knowledge K remain separate. Stocks, flows, costs and eligible/exception populations are not added together; historical as-known views survive current restatements. RW-02–05, RW-08, RW-12–15, RW-38, RW-43–44, RW-50–52, RW-56. |
| Source integrity, isolation and scope boundaries | PD6-21, PD6-22, PD6-25, PD6-26, PD6-35 | Protected reviewed originals and current roles are required; source loss is an overlay, not invented cash loss. No sharing, vendor delivery, integrations or automatic recognition is enabled. RW-27, RW-37–38, RW-47, RW-53, RW-55. |
| Atomicity, limits and exactness | PD6-09, PD6-10, PD6-27, PD6-36, PD6-37 | Duplicate requests resolve one benefit; independent approvals/reversals share fenced budgets. Safe stale/resource errors neither truncate money nor commit partial audit state; exact cent/Decimal arithmetic remains unchanged. RW-33–35, RW-54–56. |

## 38. Product decision register — ALL APPROVED, OPTION A

Each decision below is **APPROVED — OPTION A**, by explicit user approval on 3 October 2026. Option A is authoritative Phase 6 V1 policy. Options B/C remain documented non-approved alternatives and must not be implemented as V1 choices. Cross-dependencies are material: PD6-01/02/05/21/22 control authority; PD6-03/08/09/10/16/17/18/36 control allocation identity; PD6-15/23/28/29/30/33/34/37 control comparable reporting. No new choice or alternative may be silently filled during implementation; implementation execution is separately authorized as recorded above; this approval register does not authorize deferred capabilities.

### PD6-01 — Eligibility to create a recovery case

- **Question:** When can investigation start, and when is it commercially actionable?
- **Option A — APPROVED V1 POLICY:** Positive existing finding permits investigation; READY requires current Phase 4 confirmation, COMPLETE exact proof, verified originals, owner/admin B and evidence-backed parties/basis; human proof review optional.
- **Option B — NON-APPROVED ALTERNATIVE:** No case until confirmed; all earlier investigation remains outside the ledger.
- **Option C — NON-APPROVED ALTERNATIVE:** Require COMPLETE proof and owner/admin permission even for investigation creation, with human proof review mandatory for action.
- **Approved decision:** Option A.
- **Rationale:** Early internal work is useful without granting money/claim authority.
- **Tradeoffs:** More visible gated axes; B/C simplify entry but lose early investigation history.
- **Implementation consequences:** Separate unique case creation from pinned readiness approval; block nonpositive/blocked assessments and dismissed new entry.
- **Financial integrity consequences:** CASE CREATED cannot validate P, claim C or recognize R. COMPLETE is not commercial approval.
- **Security/audit consequences:** Analyst preparation only; creation/readiness have separate attributed histories and role checks.
- **Status:** APPROVED — OPTION A.

### PD6-02 — Definition of internally validated leakage

- **Question:** Does validation establish a new amount or reuse confirmation?
- **Option A — APPROVED V1 POLICY:** Reuse actual Phase 4 `confirmed` decision; V=P when eligible. Distinct B≤V is a commercial pursuit ceiling, not a new validated finding.
- **Option B — NON-APPROVED ALTERNATIVE:** Allow owner/admin to type a separate partial validated amount in Phase 6.
- **Option C — NON-APPROVED ALTERNATIVE:** Define validated as vendor acceptance.
- **Approved decision:** Option A.
- **Rationale:** It preserves existing financial authority and separates strategy from truth.
- **Tradeoffs:** Partial financial disagreement must return to Phase 4, rather than a quick recovery edit. B/C create competing meanings.
- **Implementation consequences:** Pin decision/fingerprint; readiness/B revisions with predecessors; B cannot drop below already outstanding R or change financial scope silently.
- **Financial integrity consequences:** No rewrite of P/V or double counting potential plus validated; vendor position stays S.
- **Security/audit consequences:** Owner/admin readiness, B reason/actor/time; analysts cannot validate money through a case badge.
- **Status:** APPROVED — OPTION A.

### PD6-03 — Recovery case identity / one finding vs grouping

- **Question:** What creates one stable case?
- **Option A — APPROVED V1 POLICY:** One tenant/evaluation case; several proof revisions and close/reopen events share it. Economic instruments separately deduplicate across the tenant.
- **Option B — NON-APPROVED ALTERNATIVE:** One case groups many findings/vendor scopes.
- **Option C — NON-APPROVED ALTERNATIVE:** One case per proof package or claim submission.
- **Approved decision:** Option A.
- **Rationale:** Matches the implemented immutable finding anchor.
- **Tradeoffs:** Users cannot consolidate a vendor dispute into a new aggregate financial case; commercial notes may cross-reference without summed authority.
- **Implementation consequences:** Separate case, evaluation, proof and instrument identities; no legacy LeakageCase promotion or schema redesign here.
- **Financial integrity consequences:** Reissued proof does not multiply recovery; grouping cannot create duplicate exposure.
- **Security/audit consequences:** All references tenant-bound; retry/reopen preserves original creation and history.
- **Status:** APPROVED — OPTION A.

### PD6-04 — Lifecycle/state model

- **Question:** Should one status represent workflow, validation and money?
- **Option A — APPROVED V1 POLICY:** Independent lifecycle OPEN/SUSPENDED/CLOSED, readiness, Phase 4 decision/currentness, claim, vendor position, realization, credit and evidence axes.
- **Option B — NON-APPROVED ALTERNATIVE:** Linear detected→claimed→accepted→recovered→closed workflow.
- **Option C — NON-APPROVED ALTERNATIVE:** Free-form case statuses without validated transitions.
- **Approved decision:** Option A.
- **Rationale:** Closure and vendor response can coexist with partial or reversed recovery.
- **Tradeoffs:** More model/display composition, fewer misleading automatic transitions.
- **Implementation consequences:** Section 7 transition matrix; derived realization, explicit owner/admin closure/reopen and historical corrective exception.
- **Financial integrity consequences:** CLOSED is not recovered; analyst workflow does not mutate any financial state.
- **Security/audit consequences:** Each authoritative transition has predecessor, role, reason and audit; conflicting final actions fail safely.
- **Status:** APPROVED — OPTION A.

### PD6-05 — When recovered value may be recognized

- **Question:** What admits an allocation into reported realization?
- **Option A — APPROVED V1 POLICY:** Completed method-specific economic event, evidence/party/tax/currency/deduction/precision compatibility, unused budgets, current readiness and owner/admin exact approval; R01–R10.
- **Option B — NON-APPROVED ALTERNATIVE:** Owner/admin declaration of recovery without independent event evidence.
- **Option C — NON-APPROVED ALTERNATIVE:** Vendor acknowledgment/agreement or approved credit issuance alone.
- **Approved decision:** Option A.
- **Rationale:** Approval controls reviewed evidence, not invention of a receipt.
- **Tradeoffs:** Manual review and delayed authority may lag economic cash; date/known-at views explain the delay.
- **Implementation consequences:** Observations/proposals separate from approval and immutable recognized allocations; no mutable recovered_amount.
- **Financial integrity consequences:** S, initiation, unsigned notes and entered numbers do not become R; corrective reversals use historical authority exception.
- **Security/audit consequences:** Atomic source capture/approval/audit; fresh final role and pinned context checked under PostgreSQL fence.
- **Status:** APPROVED — OPTION A.

### PD6-06 — Partial recovery

- **Question:** How are evidenced installments or realized subcomponents handled?
- **Option A — APPROVED V1 POLICY:** Exact explicit slices with their own complete evidence and allocation; preserve P/V and residual B−R.
- **Option B — NON-APPROVED ALTERNATIVE:** Only recognize after the entire case amount is realized.
- **Option C — NON-APPROVED ALTERNATIVE:** Estimate partial recovery from percentage completed or vendor acceptance.
- **Approved decision:** Option A.
- **Rationale:** Actual partial value matters even when pursuit continues.
- **Tradeoffs:** More granular evidence/reconciliation; partial coverage cannot imply full case completion.
- **Implementation consequences:** Positive allocation must fit case/instrument budget; no automatic truncation or proportional allocation.
- **Financial integrity consequences:** Preserve one-cent values; claimed/accepted remainder is not realized or automatically disputed.
- **Security/audit consequences:** Every slice independently authorized/audited; simultaneous installments share the remaining budget lock.
- **Status:** APPROVED — OPTION A.

### PD6-07 — Recovery methods

- **Question:** Which methods have recognizable V1 economics?
- **Option A — APPROVED V1 POLICY:** Evidenced settled cash performance, applied currency credits/offsets and effective unpaid-liability reductions; agreements/forward pricing/unsupported consideration remain separate observations.
- **Option B — NON-APPROVED ALTERNATIVE:** Cash-only V1.
- **Option C — NON-APPROVED ALTERNATIVE:** Any manual method/amount, including service promise, barter or fair-value estimate.
- **Approved decision:** Option A.
- **Rationale:** Supports common noncash remedies without equating them with cash or enabling new leakage families.
- **Tradeoffs:** More method-specific evidence gates than B; C has uncontrolled valuation risk.
- **Implementation consequences:** Section 9 evidence matrix, paid/unpaid replacement distinction, explicit supported-method validation.
- **Financial integrity consequences:** Actual credit/waiver differs from cash; unrelated SLA/goodwill is not finding principal.
- **Security/audit consequences:** Method cannot be a free-text authority bypass; immutable original classification and approval history.
- **Status:** APPROVED — OPTION A.

### PD6-08 — Credit issued vs applied

- **Question:** When does a credit count, and how are credit stages represented?
- **Option A — APPROVED V1 POLICY:** Issuance/availability is pending stock only; actual approved application or cash redemption consumes one root once. Preserve expiry/cancellation/reversal stages.
- **Option B — NON-APPROVED ALTERNATIVE:** Credit issued counts as realized noncash value immediately.
- **Option C — NON-APPROVED ALTERNATIVE:** Treat issued credit as recovered cash.
- **Approved decision:** Option A.
- **Rationale:** A restricted/unused/expired credit may never reduce expenditure.
- **Tradeoffs:** Slower recognition and extra AP application evidence; pending credit remains visible, not lost.
- **Implementation consequences:** Instrument budget, application/redemption/reversal linkage; no automatic guessed expiry or hidden credit subtraction.
- **Financial integrity consequences:** Issued+applied and refund+credit cannot double count; Phase 4 pre-existing allocated reductions are not new recovery.
- **Security/audit consequences:** Owner/admin reviewed validity/consumption; concurrent credit use serializes across related records.
- **Status:** APPROVED — OPTION A.

### PD6-09 — Multiple recovery events

- **Question:** Is recovery one editable total or an event-derived history?
- **Option A — APPROVED V1 POLICY:** Immutable individual economic events/approvals/allocations; totals are compatible projections, preserving instrument aliases and conflicting observations.
- **Option B — NON-APPROVED ALTERNATIVE:** Editable case recovered total with change log.
- **Option C — NON-APPROVED ALTERNATIVE:** Latest receipt overwrites previous receipts.
- **Approved decision:** Option A.
- **Rationale:** Installments and multiple evidence files remain attributable and reproducible.
- **Tradeoffs:** More event-level review than a total field; current projections need correct lineage.
- **Implementation consequences:** Stable economic identity independent of UUID/document hash; same semantic event resolves once.
- **Financial integrity consequences:** A new upload is not another payment; historical inflows and net-after-reversal remain distinguishable.
- **Security/audit consequences:** Tenant-wide deduplication and append-only trusted audit, not user-editable total history.
- **Status:** APPROVED — OPTION A.

### PD6-10 — Reversals/corrections

- **Question:** How do genuine reversals and recognition errors affect history?
- **Option A — APPROVED V1 POLICY:** Explicit linked partial/full economic reversal or corrective de-recognition/replacement; exact dates/reasons/evidence and outstanding original budget. Negative correction allowed even closed/stale.
- **Option B — NON-APPROVED ALTERNATIVE:** Edit/delete the original entry.
- **Option C — NON-APPROVED ALTERNATIVE:** Keep only original recognition and ignore later reversals.
- **Approved decision:** Option A.
- **Rationale:** Historical facts and current signed attributed totals remain defensible.
- **Tradeoffs:** More event types and distinct restatement/cash-flow interpretation; approval remains necessary.
- **Implementation consequences:** No reversal beyond unreversed approved amount; correction preserves real bank receipt and original known-at history.
- **Financial integrity consequences:** Cancelled unapplied credit changes Kc, not R; correcting attribution does not invent a cash return or alter P.
- **Security/audit consequences:** Expected original/predecessor/CAS and concurrent reversal-budget fencing; atomic corrective audit.
- **Status:** APPROVED — OPTION A.

### PD6-11 — Vendor acknowledgment/dispute

- **Question:** What authority does a vendor response have?
- **Option A — APPROVED V1 POLICY:** Evidence of that entity's scoped position, with explicit accepted/disputed/conditional amounts and coverage; separate from finding decision and R.
- **Option B — NON-APPROVED ALTERNATIVE:** Acceptance immediately confirms and recognizes recovery.
- **Option C — NON-APPROVED ALTERNATIVE:** Rejection automatically dismisses the finding.
- **Approved decision:** Option A.
- **Rationale:** Counterparties' positions do not replace financial evidence or settlement.
- **Tradeoffs:** Requires explicit coverage/authority review; incomplete response amounts stay null.
- **Implementation consequences:** Response revisions, responder association, source/date and clear conditional/unresolved meanings.
- **Financial integrity consequences:** No inferred D=P−S, vendor acknowledgment as debt, or automatic change of P/confirmed status.
- **Security/audit consequences:** Attributed response recorder and owner/admin monetary review; impersonation/name-only attribution fails.
- **Status:** APPROVED — OPTION A.

### PD6-12 — Claim/action value

- **Question:** Which amount represents what the company actually pursued?
- **Option A — APPROVED V1 POLICY:** Explicit evidenced actioned principal C≤B; draft, amendment, withdrawal and follow-up distinct; effective claim revision replaces, never adds to, prior C.
- **Option B — NON-APPROVED ALTERNATIVE:** Automatically claim all P at case creation.
- **Option C — NON-APPROVED ALTERNATIVE:** Sum every submitted/repeated claim as claimed value.
- **Approved decision:** Option A.
- **Rationale:** Actual commercial pursuit can be below validated exposure without revising it.
- **Tradeoffs:** Action evidence and versioned coverage needed; tax/extras require separate dimensions.
- **Implementation consequences:** Human outside-platform action date, claim scope/source/predecessor and owner/admin final approval; direct refunds need not invent claims.
- **Financial integrity consequences:** C does not equal V or R; unexplained claims above B blocked rather than silently capped.
- **Security/audit consequences:** Analysts prepare, owner/admin authorize recorded actioned meaning; no implied email send or legal demand.
- **Status:** APPROVED — OPTION A.

### PD6-13 — Avoided future leakage

- **Question:** Can corrected future pricing create a V1 monetary savings claim?
- **Option A — APPROVED V1 POLICY:** Record evidenced corrective action and actual later invoices as nonmonetary observed corrected billing; monetary avoided realization deferred.
- **Option B — NON-APPROVED ALTERNATIVE:** Recognize monetary avoided value only under a separately approved counterfactual baseline and complete actual future scope profile.
- **Option C — NON-APPROVED ALTERNATIVE:** Recognize avoided spend from a correction promise or prior monthly discrepancy alone.
- **Approved decision:** Option A.
- **Rationale:** Actual invoice evidence is necessary for B but alone does not prove the counterfactual.
- **Tradeoffs:** No avoided-value KPI in V1; B could add useful value later but needs new financial semantics and causality/non-overlap policy.
- **Implementation consequences:** Observations link actual future evidence/Phase 4 assessment without a new avoided-money calculator.
- **Financial integrity consequences:** No rate-variance×future quantity savings rule, forecast→cash conversion or duplicate historical recovery.
- **Security/audit consequences:** Attributed corrective action; financial counterfactual cannot be granted through analyst notes.
- **Status:** APPROVED — OPTION A.

### PD6-14 — Annualized/forecast savings

- **Question:** Should V1 persist or report monetary projections?
- **Option A — APPROVED V1 POLICY:** Defer forecast/annualized monetary metrics; human scenarios are clearly unapproved assertions outside monetary KPIs.
- **Option B — NON-APPROVED ALTERNATIVE:** Separate versioned forecasts with approved baseline/quantity/horizon/end/expiry/revalidation policy, never realized.
- **Option C — NON-APPROVED ALTERNATIVE:** Annualize the latest observed discrepancy immediately as savings.
- **Approved decision:** Option A.
- **Rationale:** Sparse observations cannot justify committed volumes, recurring entitlement or a twelve-month horizon.
- **Tradeoffs:** No forecast sales headline; later B needs reviewed assumptions and operating maintenance.
- **Implementation consequences:** No forecast fields/calculator/KPI or expiry automation in approved V1.
- **Financial integrity consequences:** Annualized illustration never enters R or gain-share; contract end cannot be ignored.
- **Security/audit consequences:** Scenario authors attributed; no automated authority from confidence or unsourced growth assumptions.
- **Status:** APPROVED — OPTION A.

### PD6-15 — Currency policy

- **Question:** What happens when a remedy currency differs from the finding?
- **Option A — APPROVED V1 POLICY:** Preserve original-currency observation separately; require exact compatible currency for V1 finding allocation/ratio, no FX or mixed totals.
- **Option B — NON-APPROVED ALTERNATIVE:** Refuse to store foreign-currency observations at all.
- **Option C — NON-APPROVED ALTERNATIVE:** Allow manually approved FX rate/source/date and converted principal.
- **Approved decision:** Option A.
- **Rationale:** Preserve real transactions without inventing comparable financial meaning.
- **Tradeoffs:** Foreign-currency money remains unallocated to findings; C requires separately approved conversion/tax/gain-share rules.
- **Implementation consequences:** Currency/basis-specific stocks/flows; explicit incompatible allocation outcome.
- **Financial integrity consequences:** EUR receipt cannot be subtracted from USD P; dollar symbol is not resolved currency.
- **Security/audit consequences:** Source denomination/profile pinned; no external rate retrieval or client-side currency relabeling.
- **Status:** APPROVED — OPTION A.

### PD6-16 — Multiple-finding settlements/allocation

- **Question:** Can V1 attribute one bundled settlement to several findings?
- **Option A — APPROVED V1 POLICY:** Defer shared allocations; retain unallocated settlement observations/related case references, excluded from finding R.
- **Option B — NON-APPROVED ALTERNATIVE:** Permit explicit source-backed atomic shared allocations with global instrument and per-case budgets.
- **Option C — NON-APPROVED ALTERNATIVE:** Automatically allocate proportionally or to the largest finding.
- **Approved decision:** Option A.
- **Rationale:** Simplest safe V1 given cross-scope, successor, tax and reversal ambiguity.
- **Tradeoffs:** Large commercial settlements cannot yet produce per-finding realization even with an explicit split; raw evidence remains useful.
- **Implementation consequences:** Unsupported shared-attribution result; no fake separate roots/case grouping. B requires an approved shared-allocation profile before implementation.
- **Financial integrity consequences:** Unallocated 100000 against 40000/70000 findings inflates neither; no guessed allocation.
- **Security/audit consequences:** Related findings must all be same authorized tenant; observation references do not authorize monetary distribution.
- **Status:** APPROVED — OPTION A.

### PD6-17 — Recovery exceeding finding amount

- **Question:** How is excess payment separated from finding principal?
- **Option A — APPROVED V1 POLICY:** Approve only explicitly evidenced compatible principal within B≤V; preserve gross receipt/extras unallocated or separately classified, never auto-cap allocation.
- **Option B — NON-APPROVED ALTERNATIVE:** Permit unrestricted recovery above V on a case.
- **Option C — NON-APPROVED ALTERNATIVE:** Automatically apply min(receipt,P), labelling the residue goodwill.
- **Approved decision:** Option A.
- **Rationale:** Both amount and economic reason must be established before the cap.
- **Tradeoffs:** Bundled/unclear excess blocks recognition; other issues need their own separately approved basis.
- **Implementation consequences:** Reviewed principal/extras bridge and exact unused-budget check; reject overflow rather than truncate.
- **Financial integrity consequences:** 60000 receipt may map 50000 principal+10000 evidenced goodwill, not 60000 finding recovery or a guessed 50000 allocation.
- **Security/audit consequences:** Owner/admin approves source allocation; immutable residual/extras history and concurrent budget fence.
- **Status:** APPROVED — OPTION A.

### PD6-18 — Stale/superseded financial evaluations

- **Question:** How does changed financial basis affect pursuit and prior realization?
- **Option A — APPROVED V1 POLICY:** Freeze new positive attribution/action authority; retain old realization and explicit relationships. Zero-history predecessor may be retired/rebased explicitly; monetary transfer or overlapping successor recognition with recognized history deferred.
- **Option B — NON-APPROVED ALTERNATIVE:** Automatically transfer old R to the newest evaluation/case.
- **Option C — NON-APPROVED ALTERNATIVE:** Ignore staleness if an earlier proof was COMPLETE.
- **Approved decision:** Option A.
- **Rationale:** Changed P/scope cannot silently alter what a past payment remedied.
- **Tradeoffs:** Additional review and conservative successor blockage; a historical transaction remains visible in an exception population.
- **Implementation consequences:** Reuse real same-scope ProofSuccessor only where its identity rules permit; no artificial cross-currency/invoice links or timestamp inference.
- **Financial integrity consequences:** No sum of overlapping old/new exposure or duplicate recovery; reversal/correction remains possible.
- **Security/audit consequences:** Owner/admin explicit relationship and fresh gate checks, complete predecessor history and reasons.
- **Status:** APPROVED — OPTION A.

### PD6-19 — Dismissed finding after recovery starts

- **Question:** What happens to a case and receipts after false_positive?
- **Option A — APPROVED V1 POLICY:** Block new positive attribution/pursuit, exclude active eligible ratios; keep approved recorded money in an invalidated-basis historical bucket. Actual returns need evidenced reversals.
- **Option B — NON-APPROVED ALTERNATIVE:** Delete/zero the case/receipts.
- **Option C — NON-APPROVED ALTERNATIVE:** Continue reporting active recovered leakage against the dismissed finding.
- **Approved decision:** Option A.
- **Rationale:** A decision changes eligibility, not bank history.
- **Tradeoffs:** Executive reports need explicit exception categories rather than one unqualified recovery number.
- **Implementation consequences:** Read actual decision/currentness separately; no Recovery action can re-confirm or alter the finding.
- **Financial integrity consequences:** R history not erased; no invented return, legal debt or proof-driven reactivation.
- **Security/audit consequences:** Preserve decision/approval/receipt chronology and role checks; analysts cannot dismiss through workflow.
- **Status:** APPROVED — OPTION A.

### PD6-20 — Closure/reopening

- **Question:** Does closing resolve money, and who can reopen?
- **Option A — APPROVED V1 POLICY:** Explicit owner/admin reasoned closure and predecessor-checked reopening; amounts/history unchanged; new positive approvals require OPEN+fresh READY, corrections allowed closed.
- **Option B — NON-APPROVED ALTERNATIVE:** Auto-close at B, reject reopen or later reversals.
- **Option C — NON-APPROVED ALTERNATIVE:** Analyst closure/reopening changes recovered/residual values.
- **Approved decision:** Option A.
- **Rationale:** Operational closure is separate from truth and later economic events.
- **Tradeoffs:** Manual lifecycle work; late receipts require explicit reopening for positive attribution.
- **Implementation consequences:** Preserve closure/reopen history; derived AT_PURSUIT_CEILING does not equal CLOSED or full V recovery.
- **Financial integrity consequences:** Partial closure retains U; reopening never restores reversed money or creates another case.
- **Security/audit consequences:** Final role/reason/expected case head; closure and reversal races cannot lose history.
- **Status:** APPROVED — OPTION A.

### PD6-21 — Role authority

- **Question:** Which roles grant financial authority, and is two-person approval mandatory?
- **Option A — APPROVED V1 POLICY:** Analysts prepare/operate nonfinancial workflow; owner/admin finalizes readiness, monetary meaning, realization/reversal/costs and closure; viewers read. Same owner/admin may prepare/approve, both roles attributed.
- **Option B — NON-APPROVED ALTERNATIVE:** Mandatory distinct preparer and owner/admin approver for every monetary decision.
- **Option C — NON-APPROVED ALTERNATIVE:** Analysts may finalize small recoveries based on thresholds.
- **Approved decision:** Option A.
- **Rationale:** Matches current authority while honestly not claiming segregation-of-duties compliance.
- **Tradeoffs:** B offers stronger organizational control but needs explicit delegation/availability policy; A relies on review accountability.
- **Implementation consequences:** Server/DB permission matrix, current membership fence and proposal/final separation; no invented analyst threshold.
- **Financial integrity consequences:** No analyst-entered amount becomes recognized; Phase 4/5 role semantics stay unchanged.
- **Security/audit consequences:** Historical preparer/approver/role-at-action retained; removed members cannot act or download later.
- **Status:** APPROVED — OPTION A.

### PD6-22 — Evidence requirements

- **Question:** What provenance proves a recovery event without new extraction/integration?
- **Option A — APPROVED V1 POLICY:** Method-specific reviewed protected sources with identities/hashes/locators/support, actual settlement/application, party/tax/component/date reconciliation and bounded actual-byte verification at approval.
- **Option B — NON-APPROVED ALTERNATIVE:** Attached document present plus reviewer checkbox.
- **Option C — NON-APPROVED ALTERNATIVE:** User note or vendor statement without original source.
- **Approved decision:** Option A.
- **Rationale:** Manual assertions must be grounded and distinguish receipt from promise.
- **Tradeoffs:** Human review and current-byte availability required; precise PDF coordinates are not available and cannot be invented.
- **Implementation consequences:** Explicit manual/extracted lineage and reviewed source relationships; source loss after approval is overlay/history, not silent monetary mutation.
- **Financial integrity consequences:** Unknown/mismatch blocks new recognition; internal journals/emails cannot independently prove cash or tax recoverability.
- **Security/audit consequences:** Source access/private capture/delete guards, minimal logs, trusted review and integrity audit; no remote URLs.
- **Status:** APPROVED — OPTION A.

### PD6-23 — Aggregation/dashboard metrics

- **Question:** Which measures/ratios are defensible?
- **Option A — APPROVED V1 POLICY:** Separate compatible P/V/B/C/S/D/R/methods/N/Kc/U/cost views; R/V explicitly gross before costs only for matching current confirmed reconciled population; exception buckets and coverage, no Total Savings.
- **Option B — NON-APPROVED ALTERNATIVE:** Recovered/potential labelled recovery rate regardless of validation/currentness/basis.
- **Option C — NON-APPROVED ALTERNATIVE:** Sum potential, credits, forecast and cash into a savings tile.
- **Approved decision:** Option A.
- **Rationale:** Economic stages and methods must not be conflated.
- **Tradeoffs:** More clear labels and null/unavailable results; portfolio ratios require matched populations, not averaging case percentages.
- **Implementation consequences:** Time-aware bounded view projections, not new aggregate finding/proof persistence; component and non-overlap reconciliation.
- **Financial integrity consequences:** No cash+pending credit, undercharge/cost netting, mixed currency/basis or double successor totals.
- **Security/audit consequences:** Tenant-scoped population and reproducible report context/authorization; incomplete coverage explicitly flagged.
- **Status:** APPROVED — OPTION A.

### PD6-24 — Gain-share eligibility boundary

- **Question:** Does ledger recognition produce a billable commission base?
- **Option A — APPROVED V1 POLICY:** Defer all gain-share eligibility/calculation/billing; record factual approved realization only.
- **Option B — NON-APPROVED ALTERNATIVE:** Define a separate customer-contract-specific approved realized-method billing profile now.
- **Option C — NON-APPROVED ALTERNATIVE:** Apply a fixed percent to P, claimed value or annualized savings.
- **Approved decision:** Option A.
- **Rationale:** No commercial agreement/eligible-method/cost/tax/clawback policy is provided.
- **Tradeoffs:** V1 cannot bill gain-share from its ledger automatically; later policy needs customer-specific semantics.
- **Implementation consequences:** No gain-share fields, invoice creation or fee accrual workflow.
- **Financial integrity consequences:** Neither forecast, pending credit nor confirmed exposure becomes platform revenue.
- **Security/audit consequences:** No implicit payment action, vendor communication or customer billing authority.
- **Status:** APPROVED — OPTION A.

### PD6-25 — External/vendor communication boundary

- **Question:** Is V1 internal action tracking or a supplier communication product?
- **Option A — APPROVED V1 POLICY:** Internal-only recorded human actions/response evidence; external sending, vendor/public accounts/portals/tokens and delivery deferred.
- **Option B — NON-APPROVED ALTERNATIVE:** Owner/admin controlled supplier email/dispute delivery now.
- **Option C — NON-APPROVED ALTERNATIVE:** Automated disputes/contact/payment blocking.
- **Approved decision:** Option A.
- **Rationale:** Matches Phase 5's disclosure boundary without inventing recipient or legal-claim policy.
- **Tradeoffs:** Users communicate outside the platform; action evidence must honestly distinguish draft from actual contact.
- **Implementation consequences:** No sender/recipient/public access entities or APIs; existing internal JSON export authority unchanged.
- **Financial integrity consequences:** Platform claim recording is not legal service/acceptance or recovered value.
- **Security/audit consequences:** No accidental hidden-data delivery; manual external actions attributed without pretending delivery was platform-verified.
- **Status:** APPROVED — OPTION A.

### PD6-26 — Retention/history relationship

- **Question:** What protects authoritative recovery evidence without inventing compliance law?
- **Option A — APPROVED V1 POLICY:** Preserve referenced recovery evidence/history under ordinary existing integrity/delete safeguards; explicit availability states; duration/holds/erasure/offboarding/backups deferred to approved compliance/legal policy.
- **Option B — NON-APPROVED ALTERNATIVE:** Fixed universal retention duration/permanent archive claim.
- **Option C — NON-APPROVED ALTERNATIVE:** User deletion of approved events/evidence with no reconciliation history.
- **Approved decision:** Option A.
- **Rationale:** Inherited PD5-08 is preserved.
- **Tradeoffs:** Storage growth and compliance operating policy remain unresolved, honestly disclosed.
- **Implementation consequences:** Later extend compatible guards to recovery references, not a deletion scheduler or hidden shadow archive.
- **Financial integrity consequences:** Historical recognition/reversal remains visible; missing originals cannot be described as currently available.
- **Security/audit consequences:** Sensitive bank/actor/hash/excerpt data require lawful later retention analysis; no guaranteed regulatory-compliance claim.
- **Status:** APPROVED — OPTION A.

### PD6-27 — Operational safety limits

- **Question:** Which bounded V1 defaults can support safe synchronous operation?
- **Option A — APPROVED V1 POLICY:** Versioned section 32 engineering defaults with explicit resource errors and measured tuning within financial/security safeguards.
- **Option B — NON-APPROVED ALTERNATIVE:** Unbounded reads/approval/aggregation/export work.
- **Option C — NON-APPROVED ALTERNATIVE:** Silently truncate events/sources/totals to fit performance bounds.
- **Approved decision:** Option A.
- **Rationale:** Limits protect current architecture while retaining valid economic facts.
- **Tradeoffs:** Some valid large cases/projections unavailable synchronously; no enterprise load/deployment claim.
- **Implementation consequences:** Request/count/byte/time/admission/quota and complete-population bounds across workers; pages never substitute for full totals.
- **Financial integrity consequences:** No amount suppression, incomplete approval or partially counted total disguised as authoritative.
- **Security/audit consequences:** Tenant/actor shared limits, cancellation/retry/budget records; existing upload/proof limits not weakened.
- **Status:** APPROVED — OPTION A.

### PD6-28 — Recovery tax/VAT basis compatibility

- **Question:** How are tax-inclusive receipts compared with tax-exclusive findings?
- **Option A — APPROVED V1 POLICY:** Mandatory explicit compatible principal/tax breakdown; cap/allocate only tax-exclusive principal, preserve tax separately, no inferred tax treatment/recoverability. Unknown/incompatible basis blocks affected allocations/ratios.
- **Option B — NON-APPROVED ALTERNATIVE:** Include evidenced nonrecoverable tax in an additional separately approved economic-benefit profile.
- **Option C — NON-APPROVED ALTERNATIVE:** Compare full gross receipt with P or strip tax using an assumed jurisdiction rate.
- **Approved decision:** Option A.
- **Rationale:** P deliberately excludes tax, and tax deduction entitlement is not established by an invoice amount.
- **Tradeoffs:** Some otherwise real receipts remain unallocated; B needs customer/jurisdiction/legal policy beyond this task.
- **Implementation consequences:** Explicit observed basis/principal/tax/review mapping; 108000−18000=90000 against P=90000, not over-recovery.
- **Financial integrity consequences:** Tax unknown stays unknown; no VAT reclaim amount, tax leakage family or hidden inclusive/exclusive ratio.
- **Security/audit consequences:** Grounded private source tax components and owner/admin meaning approval; no checkbox invents tax entitlement.
- **Status:** APPROVED — OPTION A.

### PD6-29 — Gross settlement vs gross received vs net realized amount

- **Question:** Which amount is called recovery when fees/withholding reduce bank cash?
- **Option A — APPROVED V1 POLICY:** Record agreed S, actual gross receipt/performance, principal/tax, evidenced bank fees/withholding/deductions, N and other consideration separately. R is qualified gross verified compatible principal before separately evidenced costs; no generic net-savings metric. Unresolved deductions are excluded/unresolved and block a complete ratio.
- **Option B — NON-APPROVED ALTERNATIVE:** Define recovered value as approved tax-compatible net bank cash only; separately report noncash remedies.
- **Option C — NON-APPROVED ALTERNATIVE:** Treat settlement, gross receipt and net cash as one recovered number.
- **Approved decision:** Option A.
- **Rationale:** Disclose actual bank cash and vendor principal performance without automatically netting unrelated pursuit costs.
- **Tradeoffs:** Gross-before-cost labels require care; B is simpler cash reporting but understates independently evidenced principal discharge/noncash remedies.
- **Implementation consequences:** Source-supported component bridge; no unknown component backsolving; only verified discharged bank-fee principal included above N.
- **Financial integrity consequences:** At evidenced bank-fee case S/gross/R=50000, fee=500, N=49500; withholding recoverability/discharge never assumed.
- **Security/audit consequences:** Private beneficiary/deduction sources and exact approvals; no metadata label can override raw amounts/basis.
- **Status:** APPROVED — OPTION A.

### PD6-30 — Counterparty / legal-entity attribution

- **Question:** How does a payment from/to another entity support the finding?
- **Option A — APPROVED V1 POLICY:** Exact reviewed entity/identifier evidence and scoped dated agency/assignment/discharge/beneficiary association; no fuzzy name/parent-subsidiary/processor inference.
- **Option B — NON-APPROVED ALTERNATIVE:** Strictly same legal payer/payee only; reject cross-entity attribution even with evidence.
- **Option C — NON-APPROVED ALTERNATIVE:** Match brands/names/group companies or processor references automatically.
- **Approved decision:** Option A.
- **Rationale:** Supports genuine renamed/agency arrangements without inventing economic ownership.
- **Tradeoffs:** Additional relationship review; B unnecessarily rejects demonstrably authorized payments, C risks false attribution.
- **Implementation consequences:** Scoped reviewed association concept; preserve vendor ID namespaces/continuity evidence, no global legal-entity master schema now.
- **Financial integrity consequences:** Parent cash or intercompany settlement is not vendor remedy until the correct principal/customer benefit is evidenced.
- **Security/audit consequences:** Owner/admin association approval/revocation/lineage; tenant membership does not establish corporate entitlement.
- **Status:** APPROVED — OPTION A.

### PD6-31 — Recovery case ownership and operational workflow metadata

- **Question:** Which operational fields belong in V1 without changing money?
- **Option A — APPROVED V1 POLICY:** Attributed assignment/owner, priority, target/follow-up dates, next action, notes and internal escalation; analyst operational edits, owner/admin final lifecycle authority; no financial side effect.
- **Option B — NON-APPROVED ALTERNATIVE:** Only case lifecycle and monetary events, no assignment/follow-up.
- **Option C — NON-APPROVED ALTERNATIVE:** Workflow statuses/targets automatically confirm claims or recognition.
- **Approved decision:** Option A.
- **Rationale:** Useful pursuit management stays distinct from financial truth.
- **Tradeoffs:** More revisioned operational history; it must not create notification/sending/automation scope.
- **Implementation consequences:** Tenant-member assignees, explicit history; removed assignee retained historically without active permission.
- **Financial integrity consequences:** Changing priority/target/owner/notes never changes P/V/B/C/S/R/evidence/recognition.
- **Security/audit consequences:** Inert bounded notes, attributed revisions/retractions and current membership; operational owner field grants no RBAC role.
- **Status:** APPROVED — OPTION A.

### PD6-32 — Write-off / not-pursued semantics

- **Question:** Can a valid finding close without recovery, and what does written off mean?
- **Option A — APPROVED V1 POLICY:** Owner/admin commercial closure with explicit economics/relationship/immateriality/evidence/time-bar-concern/management/operational reason; retain truth and U, no accounting/legal write-off or false-positive inference.
- **Option B — NON-APPROVED ALTERNATIVE:** Any unrecovered closure automatically dismisses the finding.
- **Option C — NON-APPROVED ALTERNATIVE:** Treat closure as zero liability and zero remaining exposure.
- **Approved decision:** Option A.
- **Rationale:** Strategy is separate from a supported historical assessment.
- **Tradeoffs:** Commercially closed unresolved exposure stays visible; legal limitation concerns need outside review.
- **Implementation consequences:** Separate closure reason/effective date/rationale from finding decision; explicit reopen path.
- **Financial integrity consequences:** No erasure of V/P or fabricated recovery, debt waiver, bad-debt expense or statutory bar.
- **Security/audit consequences:** Final role/reason/predecessor audit; analysts propose rather than finalize abandonment.
- **Status:** APPROVED — OPTION A.

### PD6-33 — Recovery-cost treatment

- **Question:** Should attributable costs be tracked and netted?
- **Option A — APPROVED V1 POLICY:** Optional reviewed costs with exact incurred/paid states, own currency/source/economic identity, direct case allocation; keep gross R and F separate, no automatic net-savings metric.
- **Option B — NON-APPROVED ALTERNATIVE:** Defer all cost tracking.
- **Option C — NON-APPROVED ALTERNATIVE:** Automatically subtract legal/collection/bank costs from R and original leakage.
- **Approved decision:** Option A.
- **Rationale:** Costs inform management without changing what the vendor actually remedied.
- **Tradeoffs:** Additional evidence/approval/duplicate controls; shared/unallocated cost allocation remains conservative.
- **Implementation consequences:** Explicit bank-fee linkage avoids subtracting already-net N twice; no guessed shared legal-fee proportions.
- **Financial integrity consequences:** P unchanged, R not reduced by cost; no tax-adjusted benefit/gain-share base or cross-currency netting.
- **Security/audit consequences:** Owner/admin cost authority and source/reversal history; a cost document cannot mutate recognized recovery.
- **Status:** APPROVED — OPTION A.

### PD6-34 — Reporting-period and economic cut-off rules

- **Question:** Which dates and knowledge cutoff reproduce a dashboard?
- **Option A — APPROVED V1 POLICY:** Economic event-specific dates plus immutable server known/approval time; `[start,end)` period, declared cutoff semantics, K/high-watermark/profile/coverage; distinguish original as-known and later restatement.
- **Option B — NON-APPROVED ALTERNATIVE:** Latest current totals attributed by database created_at.
- **Option C — NON-APPROVED ALTERNATIVE:** Backdate approval/correction and rewrite earlier recorded event history.
- **Approved decision:** Option A.
- **Rationale:** Issued credit, application, cash settlement and reversal are different temporal facts.
- **Tradeoffs:** Two temporal axes and retained state observations; current Phase 4 `is_stale` alone cannot reproduce past eligibility.
- **Implementation consequences:** Report context/projected history, source timezone precision and date correction lineage; no general-ledger period posting subsystem.
- **Financial integrity consequences:** 31 December credit/10 January application means December stock, January R; late approval affects K, not original bank date.
- **Security/audit consequences:** Server-known time not user-set; pinned history/coverage and immutable corrections prevent backdating fraud.
- **Status:** APPROVED — OPTION A.

### PD6-35 — Integrations / evidence arrival boundary

- **Question:** Does V1 require live ERP/AP/bank connectors?
- **Option A — APPROVED V1 POLICY:** Manual protected upload and reviewed evidence; integration/import/auto-reconciliation/recognition deferred.
- **Option B — NON-APPROVED ALTERNATIVE:** Read-only import connector produces proposals with upstream identity/version and manual final approval.
- **Option C — NON-APPROVED ALTERNATIVE:** Connector payment status automatically grants realized recovery.
- **Approved decision:** Option A.
- **Rationale:** Domain correctness can be validated without credentials or infrastructure scope.
- **Tradeoffs:** More manual evidence review; later B requires explicit upstream identity/correction/time/integrity semantics.
- **Implementation consequences:** No connector, ingestion worker, reconciliation engine or broadened extraction in V1; future imports must reuse gates/deduplication.
- **Financial integrity consequences:** ERP journal/import flag or initiated payment never independently means settled compatible principal.
- **Security/audit consequences:** No remote fetch, credentials or vendor-origin instructions become application authority.
- **Status:** APPROVED — OPTION A.

### PD6-36 — Atomic recognition / concurrency / idempotency

- **Question:** What protects authoritative approval against simultaneous changes?
- **Option A — APPROVED V1 POLICY:** Reuse PostgreSQL organization/role/evidence order, pin every material revision/budget, verify captured bytes and commit fences, atomic trusted audit, semantic plus request identity and safe stale/retry outcomes.
- **Option B — NON-APPROVED ALTERNATIVE:** Read independently then approve optimistic totals without revision fences.
- **Option C — NON-APPROVED ALTERNATIVE:** Serialize only within one application worker or trust request UUID uniqueness alone.
- **Approved decision:** Option A.
- **Rationale:** Approval/revocation, duplicate requests and independent payments can race across workers.
- **Tradeoffs:** Tenant serialization/bounded synchronous throughput; locks cannot guarantee filesystem transactions without consistent capture.
- **Implementation consequences:** Proposal/predecessor CAS, tenant-wide instrument and original reversal budgets, current decision/readiness/source/party/tax pin set; no database changes now.
- **Financial integrity consequences:** One semantic realization, no over-allocation, mixed approval context, lost reversal or duplicate request money.
- **Security/audit consequences:** Fresh membership held through capture/commit, independent transaction acceptance requirements; rollback leaves no recognized/audit orphan.
- **Status:** APPROVED — OPTION A.

### PD6-37 — Recovery precision and presentation rounding

- **Question:** How are exact money, small events and ratios represented?
- **Option A — APPROVED V1 POLICY:** Existing finite Decimal strings/NUMERIC(20,6) safeguards, source currency quantum/precision evidence, exact bounded sums/subtractions and no financial rounding fallback; two-decimal HALF_UP percentage display only with exact ratio inputs retained.
- **Option B — NON-APPROVED ALTERNATIVE:** Assume two-decimal money and a rounding tolerance for every currency/event.
- **Option C — NON-APPROVED ALTERNATIVE:** Float arithmetic/display numbers drive allocation/caps.
- **Approved decision:** Option A.
- **Rationale:** Reuse exact constraints without reopening Phase 4 rounding policy.
- **Tradeoffs:** Unknown quantum/excess scale can block affected recognition; display ratios may be visibly rounded and never authorize a cent allocation.
- **Implementation consequences:** Typed monetary components, explicit profile/version/context, safe overflow and unsupported precision outcomes, no data precision migration selected here.
- **Financial integrity consequences:** One cent retained, no epsilon/materiality suppression, rounded ratio never reconstructs or edits R/V/P.
- **Security/audit consequences:** Preserve original scale and reviewed profile; client formatting cannot bypass storage/approval limits.
- **Status:** APPROVED — OPTION A.

## 39. Reference basis and interpretation limits

The starting repository and the user-supplied scenarios are the financial/product basis. Recovery Ledger treatment is the approved V1 product policy, not universal legal/accounting treatment. Phase 4 PD-01–PD-07 and Phase 5 PD5-01–PD5-14 are inherited unchanged. The inspected exact model/service/UI links above distinguish implemented identity/audit from missing recovery concepts; no new SQL schema is chosen.

Primary context consulted 3 October 2026: [European Commission VAT deductions](https://taxation-customs.ec.europa.eu/archives/taxable-persons/deductions_en) describes conditions, restrictions and partial/full deduction in its EU context. It demonstrates why a tax component's presence does not establish this customer's recoverability; no EU or other jurisdiction's tax rule is imported into the product. [IFRS IAS 7 overview](https://www.ifrs.org/issued-standards/list-of-standards/ias-7-statement-of-cash-flows/) is an accounting-framework reference, not authority to call an internal recovery dashboard an IAS 7 statement or claim IFRS compliance. No extended quotations or jurisdictional tax conclusions are used.

## 40. Historical specification validation and current delivery boundary

**Historical specification-finalization validation instructions:** This was documentation validation, not a Phase 6 implementation/test/production claim. Before delivery verify exact starting ancestry; only this specification and minimal HANDOFF status metadata changed; entire Phase 4/5 policy files are byte-identical; all PD6-01–PD6-37 are APPROVED Option A with unchanged meaning and non-approved alternatives clearly labeled; all worked-example arithmetic is independently checked using exact Decimal; examples respect single economic benefit, tax/currency/entity compatibility and null unknowns; local Markdown links and git whitespace pass; observe automatic PR CI without unnecessary local implementation reruns. Existing historical 516 PostgreSQL backend / 86 frontend results remain Phase 5 facts, not new Phase 6 tests.

Historical specification/approval branch documentation checks, 3 October 2026 (preserved below; post-merge cleanup validation is reported separately):

| Check | Result |
| --- | --- |
| Starting ancestry | The original specification starts at `4e574e17ff7dbc69ed4b2b3a5ab0db1ab930f4f7`; approval finalization continues from validated specification head `6d032eb2ca5acb697869a20abbfe49294898306a` on the same branch. Main and branch ancestry verified before finalizing. |
| Structural coverage | 40 numbered sections; 56 worked examples, each with all eight requested fields; 37 individually explained decisions, all APPROVED Option A; 50 future acceptance requirements; 44 risk review rows distinguishing approved policy from unimplemented guards. |
| Approval finalization | Complete dependency review before status edits found no conflict between the 37 approved Option A policies. All 37 Option A texts and 74 alternative texts are preserved verbatim apart from approval/non-approved labels; all 22 invariant rows and 50 acceptance rows are unchanged. The 56 worked examples preserve their facts, amounts, evidence, actions and aggregation behavior; RW-21 only changes the profile wording from proposed to approved. |
| Independent arithmetic | 38 exact Decimal equations, 20 independently specified economic fixtures excluding stock/agreements/tax/costs/forecasts from R as appropriate, and two temporal fixtures passed. No application module or financial calculator invoked. |
| Semantic review | All examples reviewed for stock/flow separation, single economic benefit, explicit principal allocation, null unknowns, current versus historical authority, and compatible currency/tax/entity/reporting basis. Different-currency observations/costs are never summed. |
| Phase 4 policy | Entire file byte-identical to starting main; SHA-256 `1ee9eebf9ca81496f616c8bf55e64389341141762a501c3ec91fa654bb99fe09`. PD-01–PD-07 unchanged. |
| Phase 5 policy/report | Entire specification and validation report byte-identical; specification SHA-256 `1dac7eb8377322552e12cc0c87b49baaa60123e53938209bb7e98699415c6e2a`. PD5-01–PD5-14 unchanged. |
| Scope, links and whitespace | Only this specification and three minimal HANDOFF status paragraphs changed; 24 local link targets verified; git whitespace checks passed. No code/migration/API/frontend/test changes. |
| Secret scan | Existing bounded repository scan: 184 source files, zero findings. This is limited pattern coverage, not a comprehensive security certification. |
| CI | Original draft CI [run 37139016750](https://github.com/yasthekiller007-lang/financial-leakage-ai/actions/runs/37139016750) passed for historical draft head `6d032eb2ca5acb697869a20abbfe49294898306a`. Observe complete CI on the exact final approval/finalization commit and report its status separately; the earlier green draft is not its validation. No Phase 6 implementation suite exists or is claimed. |

**Current delivery boundary:** PR #9 and specification version 1.0 are merged. Separately authorized Phase 6 V1 implementation is on its review branch; the implementation PR must not be merged automatically. See the implementation validation report and complete exact-head CI. PD6-01–PD6-37 Option A remain authoritative and unchanged. Vendor contact, integrations, gain-share, recovery automation, payment controls, Firewall, Leakage DNA, later phases and new leakage families remain outside this implementation. No production deployment or accounting/legal/tax/regulatory compliance is claimed.
