# Phase 4 business specification — Leakage Compiler and Contract-to-Invoice Engine

**Document version:** 1.1 financial policy, finalized 2 October 2026; execution status updated 3 October 2026. **Policy status:** PD-01 through PD-07 are APPROVED PRODUCT POLICY, unchanged. **Specification merge status:** PR #4 merged into main. **Implementation authorization:** explicitly granted by the user; Phase 4 V1 implemented on `phase4/leakage-compiler-engine`, pending implementation PR review. No automatic implementation merge is authorized.

**Verified implementation baseline:** main commit `e1bdae347bfe6d9b8d7c9b92ec8efc3e723943a1`, containing merged Phases 1–3 and this specification in PR #4. The specification was originally authored as the sole change on `phase4/business-spec` against `c3c75fc8874ca4f990f326303a95c40d9a30aae9`; those documentation-only restrictions describe that historical task. Subsequent explicit user authorization permits the Phase 4 V1 implementation described in [Phase 4 architecture](phase4-architecture.md) and [Phase 4 validation](phase4-validation.md). Worked examples remain approved acceptance policy, not claims about customer findings. Proof Engine, Recovery Ledger and automatic merge remain unauthorized.

The product compares the amount contractually expected for an identified, applicable billing scope with the amount actually billed for that same scope. If an obligation, input, match, date, condition, allocation or evidence cannot be established safely, the monetary finding is **not assessed**, rather than invented or set to zero. A missed finding is preferable to a fabricated amount.

### Enterprise product principle

**SIMPLE ON THE SURFACE, RIGOROUS UNDERNEATH.** Financial Leakage AI serves large enterprises through financially rigorous, auditable, conservative and actionable results. The eventual executive summary should make the amount, reason, contractual comparison, status and next action easy to understand; detailed source provenance, amendments, approvals, rule versions and calculation inputs remain available to finance, legal and procurement reviewers. This is a product principle for later implementation, not a UI redesign in this task.

For F02, a future summary could present:

| Summary field | Example content |
| --- | --- |
| Potential leakage | 74,199.90 USD |
| Reason | Invoice unit price exceeds the applicable contracted price. |
| Contracted / billed | 18.40 USD/unit / 20.10 USD/unit |
| Billed quantity | 43,647 units |
| Status | Detected from approved inputs; finding confirmation pending. |
| Action | Review evidence. |

An executive-friendly label must retain the difference between approved calculation inputs, a detected discrepancy and a review-confirmed finding. It must not label detected amounts as recovered savings, guaranteed savings or a final audit conclusion. Reviewer detail preserves everything needed to reproduce the summary.

Differentiation comes from reliable document intelligence, approved facts, deterministic compilation and comparison, and traceable findings. Financial Leakage Firewall/pre-payment prevention, pre-contract simulation, Leakage DNA/root-cause intelligence, discovery across validated findings and recovery automation are future possibilities only. They are not Phase 4 requirements; Proof Engine and Recovery Ledger remain later phases.

## 1. Definitions and compatibility with Phase 3

| Concept | Definition and boundary |
| --- | --- |
| Extraction candidate | A Phase 3 value from a specific ExtractionRun and ExtractedField, with raw text, normalization, confidence and source location. It is not contractual authority. |
| Approved fact | An immutable, reviewed assertion about a source fact and its meaning for a bounded billing scope; it links back to the candidate and source. Approval is separate from extraction confidence. |
| Approved term | A supported contractual obligation assembled from approved facts: amount/rate, subject, unit/base, conditions, dates, applicable entities and source clauses. It is not created merely by recognizing a numeric price. |
| Governing packet | The reviewed master agreement, applicable amendments, schedules, exhibits and relevant authorized exceptions available for a named contract/scope and knowledge cutoff. Missing known material is a blocker. |
| Applicability snapshot | A frozen selection of governing terms, match, service/billing date or interval, and approval versions used for one evaluation. |
| Billing scope | A uniquely identified invoice line, contractual fee for one complete billing cycle, or explicitly defined discount/base set. Both expected and actual values must cover exactly this scope. |
| Expected amount, E | The supported contractual amount for the billing scope after applicable pricing, discounts, permitted fees and required rounding, excluding tax in V1. |
| Actual amount, A | The evidenced amount billed for the same scope and tax basis, after allocated discounts, credits and adjustments. It is not necessarily the whole invoice total or amount paid. |
| Signed discrepancy, Δ | A minus E, in one unambiguous currency and a compatible unit/basis. Negative values are informational undercharges, not negative leakage. |
| Potential leakage | A deterministic, evidence-backed positive contractual billing discrepancy produced by an approved versioned rule over a clearly defined billing scope, with all gates satisfied. It does not establish recovery, legal liability, vendor wrongdoing, guaranteed savings, cash already lost or a final audit conclusion. |
| Blocked evaluation | An inability to assess a scope. Its amount is unknown/null, not zero. It cannot be stored as a monetary finding with a fabricated zero. |
| Compiler | Deterministically validates and translates approved terms into supported, versioned calculation instructions and selectors. It does not autonomously interpret legal prose. |
| Engine | Matches a target scope, resolves applicable compiled terms, reconciles actual billing components and evaluates the approved rule bundle. |

Phase 3 processing statuses remain `pending`, `queued`, `processing`, `processed`, `needs_review`, `needs_ocr`, `failed`. `processed` does not mean approved. Field confidence remains `high`/`medium`/`low`; it is not a calibrated probability. No score is converted into legal or financial authority.

Existing foundation entities Contract, ContractVersion, Invoice and InvoiceLineItem are schemas, not populated financial truth. Phase 3 does not create them. ContractVersion has a single optional amount and version metadata; it cannot, by itself, describe term-level precedence, tier semantics or a full pricing program. Its version number is not legal priority. InvoiceLineItem requires positive quantity; credit/negative-quantity records must not be forced into that model by changing signs.

The existing LeakageRule is a protocol, not an implemented engine. The future implementation must preserve `NUMERIC(20,6)`, tenant-safe references and the existing CaseStatus meanings. This specification identifies data gaps without resolving their database design or creating new enums now.

The following invariants apply to every rule, table and example: **UNKNOWN ≠ ZERO; ABSENCE OF EVIDENCE ≠ PROHIBITION; IDENTITY MATCH ≠ ECONOMIC APPLICABILITY; HIGH EXTRACTION CONFIDENCE ≠ APPROVED FINANCIAL TRUTH; DOCUMENT PRESENT ≠ GOVERNING PACKET COMPLETE; CONTRACT FOUND ≠ PRICE APPLICABLE; NEGATIVE DISCREPANCY ≠ NEGATIVE LEAKAGE; POTENTIAL LEAKAGE ≠ RECOVERED VALUE, LEGAL LIABILITY OR GUARANTEED SAVINGS.**

## 2. Approved-fact policy

### 2.1 Conceptual approved-fact record

Each input to a financial calculation must carry:

| Required information | Meaning |
| --- | --- |
| Organization and fact identity | Tenant ownership and a stable identity for the assertion/revision. Cross-tenant approvals and source links are forbidden. |
| Source | Document ID, document SHA-256, document classification and source location: PDF page/span or spreadsheet sheet/cell/row/column. |
| Extraction lineage | ExtractionRun ID/version, ExtractedField ID/path where present, parser/extractor/schema versions and original field confidence/reason. |
| Original and approved value | Unchanged raw source, original normalized candidate, reviewed normalized value, semantic type, currency/unit and whether the reviewed value corrects the candidate. |
| Semantic role | Unit price versus total; percentage versus money discount; gross versus net; charge versus credit; invoice date versus service date. Same numeric value does not imply the same meaning. |
| Scope and validity | Contract/invoice/line/SKU/entity, applicable dates or explicit not-applicable status, conditions and exact source supporting that scope. |
| Approval | Decision, actor, tenant-scoped review permission, time, reason, approval revision and any predecessor/revocation record. |
| Uncertainty resolution | Original ambiguity/conflict and the evidence/reason resolving it. Clicking approve without resolving a material conflict is insufficient. |
| Knowledge cutoff | When the governing evidence and approval became available for this evaluation. Economic effective date and knowledge time are separate. |

Missing information is explicitly unknown. Not-applicable is an explicit semantic assertion, not an empty field interpreted as a default. A value with no source cannot become approved by manual entry alone. A correction preserves the machine value and records its own source and revision; it never overwrites Phase 3 history.

Approval also addresses material exceptions, scope, price basis and applicability. Confirming that a document contains “10.00” is insufficient to approve “10.00 USD per unit, tax-exclusive, for this SKU and service date.” Required meaning must be supported by reviewed source text.

### 2.2 Consumption decision table

| Fact condition | Can drive an authoritative potential-leakage amount? | Treatment |
| --- | --- | --- |
| Manually approved, fully grounded, valid for scope, no unresolved material conflict | Yes, subject to all remaining gates | Pin its approval revision. |
| Deterministic high-confidence candidate, not reviewed | No under APPROVED PRODUCT POLICY PD-01 | May support a clearly separated non-authoritative preview; excluded from authoritative findings and monetary totals. |
| Approved resolution of a low-confidence/corrected candidate, supported by the actual source | Yes | Use reviewed revision; preserve original uncertainty. |
| Unresolved, low-confidence, null or missing candidate | No | Insufficient evidence/needs review. |
| Conflicting facts without an evidenced approved resolution | No | Ambiguous contract or actual billing; no chosen number. |
| Revoked/superseded approval | Not for a new current finding | Retain for historical reproduction; mark affected current evaluation stale. |
| Relevant unreadable source or missing pricing schedule | No | Needs OCR/insufficient evidence; no inference from the readable subset. |

Conceptual approval descriptors (`unreviewed`, `approved`, `rejected`, `revoked`) belong to a future review decision concept, not ProcessingStatus or CaseStatus. They are not existing database enum values. Under **APPROVED PRODUCT POLICY PD-01**, every fact and semantic mapping that can directly influence an authoritative amount requires manual approval. Owner/admin may approve and revoke calculation-driving facts and mappings; analysts may review, propose, annotate and suggest corrections but cannot grant final monetary authority; viewers are read-only. Preview extraction confidence never substitutes for approval. Every decision preserves source provenance, semantic meaning, actor, timestamp, tenant ownership and the complete approval/revocation revision history.

### 2.3 Packet coverage and factual promotion

A bounded, versioned, scope-specific governing-packet attestation is mandatory before authoritative calculation under **APPROVED PRODUCT POLICY PD-04**. Record the master agreement, relevant amendments, schedules, exhibits/addenda, applicable scope and period, included document identities/hashes, known missing material, incorporation/precedence clauses, relevant approved waivers/change orders, reviewer, timestamp and attestation revision. Approval follows PD-01. A complete extraction of one uploaded table does not demonstrate a complete contract packet. Known missing incorporated or otherwise relevant material blocks its affected scope; a missing amendment cannot be treated as irrelevant merely because its new price is unavailable.

Coverage is a bounded, documented review assertion, not a guarantee that no unknown document exists anywhere. Findings must identify that evidence boundary; uploaded documents are never assumed exhaustive. Later material evidence requires a new reviewed attestation and evaluation snapshot; it never silently rewrites history.

A future approval workflow may promote complete records to existing Contract/Invoice entities, but must not force incomplete candidates into required columns or create a duplicate entity on reapproval. Exact promotion/storage design is deferred to separately authorized implementation planning. An approved source packet and stable target scope must remain identifiable regardless of storage choice.

## 3. Leakage Compiler contract

The compiler consumes approved facts, approved clause-to-term mappings and the governing packet, never arbitrary document instructions or unsupported natural-language obligations. It produces either a supported compiled term or a blocked term with a reason.

Every compiled term must identify its master agreement, source clause/document/run, approved fact revisions, term identity and target (SKU/service/fee), legal parties, currency, unit, tax basis, rate/amount, quantity/discount/surcharge base, conditions, interval, amendment relationship, rounding requirements and rule/policy version. A percentage is a rate, quantity is a quantity, and money is money; do not represent all inputs as Money merely because the existing draft CalculationTrace has money-only inputs.

Missing base, billing frequency, tier method, fee exhaustiveness or replacement target must block compilation of the affected rule. Free-text clauses stay free-text evidence until a supported, evidenced semantic mapping is approved. No compiler may introduce a missing obligation, use an LLM confidence as approval, or infer that every new document overrides all earlier terms.

Phase 3 lacks several required semantics: tier method and aggregation boundaries, typed discount/base meaning, unit-price tax basis, recurring billing cycle/proration, precise clause replacement edges, explicit fee exclusion/exhaustiveness, entity equivalences, review decisions and completeness attestations. These are future approved inputs; they must not be presumed to exist in the current candidate schema.

The engine evaluates only terms successfully compiled for the exact target scope. Unknown material terms affecting that scope block evaluation; unrelated reviewed scopes may still be evaluated. Invoice reports must show assessed and unassessed coverage and must not describe a partially assessed invoice as fully clean.

## 4. Contract-to-invoice matching

### 4.1 Authoritative evidence hierarchy

1. **Explicit approved contract/agreement reference**, uniquely resolving within the tenant and relevant legal-entity namespace, with approved supplier and buyer identities or source-grounded approved equivalences, compatible scope and no contradictory identifier.
2. **Approved PO-to-contract relationship**, with an explicit invoice/line PO reference and an unambiguous reviewed link to that master agreement, satisfying the same entity/scope checks. V1 does not extract sophisticated PO terms or create this link from name similarity.
3. **Approved manual association**, supported by a documented reason and evidence tying the specific invoice/line to the contract; review can resolve a candidate, but a user selection without supporting evidence is insufficient.
4. **Candidate signals only:** same vendor, buyer, account, SKU, service period, currency and unique active contract. These assist review; their uniqueness is not proof of a contractual association.

Exact supplier legal entity is a consistency gate, not a substitute for a contract link. Supplier names may describe brands, trading names or different group companies. An approved alias must be grounded in legal/entity evidence. A matching vendor ID with a conflicting legal entity is a conflict, not a weighted-score win.

Preserve identifiers and their namespace. Do not discard leading zeros, punctuation or meaningful case; case-insensitive equivalence requires an approved namespace convention. Whitespace normalization from extraction is not permission to merge distinct IDs. Multiple contracts with the same reference or competing PO mappings are ambiguous.

### 4.2 Outcomes and scope

| Match outcome | Meaning | Financial calculation |
| --- | --- | --- |
| MATCHED | Approved authoritative association with entity and subject checks passed | Only after term/date/currency/approval gates also pass. |
| HIGH-CONFIDENCE CANDIDATE / CANDIDATE | One plausible reviewed-data candidate without sufficient authoritative association | Blocked until evidenced association approval. “High” is not a probability. |
| AMBIGUOUS | Multiple plausible associations or conflicting strong links | Blocked. |
| UNMATCHED / NO MATCH | No supported link, or no applicable contract scope after known validity checks | Blocked. |
| NEEDS REVIEW | Explicit link exists but identity, renewal, date or scope is unresolved | Blocked with a reason. |

These are conceptual matching outcomes, not changes to document or finding status enums. Identity association and economic applicability are separate: a reference can identify an expired contract without authorizing its price for current service.

One master agreement may support many invoices and many pricing entries. An invoice may have many lines. Header references may be inherited only where the line does not contradict them and the approved scope covers it. An explicit conflicting line reference must not be ignored. Within one master, line/SKU schedules can differ if uniquely mapped.

Under **APPROVED PRODUCT POLICY PD-02**, V1 uses exactly one master agreement per invoice evaluation, with distinct line pricing scopes under that master. Multiple possible masters, unallocated bundled services, conflicting header/line references or unresolved shared invoice discounts/credits block authoritative evaluation and require review. Independent multi-master line evaluation requires separate future scope approval. Candidate signals and weighted/fuzzy scores never override conflicting explicit identifiers or create monetary authority.

## 5. Relevant economic dates and intervals

The **approved contractual date basis comes first**. A delivery-priced contract requires delivery evidence; a service-priced contract requires service evidence; an invoice-date price requires an explicit invoice-date binding. The following hierarchy applies only after that semantic basis is approved:

1. Explicit matching line-item service/delivery date for the contractual basis.
2. Explicit matching line-item service/billing interval.
3. Invoice-level interval that is approved to cover that line without contradictory line evidence.
4. Invoice date only if approved governing text expressly permits this basis/fallback.

A convenient available date cannot replace the contractual basis. Due date, upload date, signature date and extraction time are not price-selection defaults. A line date more specific than a header interval can refine it; a contradiction requiring interpretation blocks evaluation.

Use date-only values where the source has dates. Conceptual normalized intervals are start-inclusive/end-exclusive, compatible with existing effective_from/effective_to constraints. Convert an explicitly inclusive end date to the following date only with a recorded, approved boundary interpretation. A source’s ambiguous end boundary is not silently normalized into legal meaning. A price expressly effective July 1 applies on July 1; the preceding price ends before July 1 if an approved supersession establishes that boundary.

If all units in a reviewed service interval have one applicable price, compare normally. If the interval crosses a price/scope/discount change, require evidenced allocation of quantity and billed amounts to each interval. Do not prorate by days, choose the invoice-date price or take an average. An unallocated aggregate has no single authoritative expected amount. With explicit independent allocations, each segment can be assessed and the non-overlapping results reconciled.

For recurring fees, require an identified complete contractual billing cycle, cadence and applicable fee. A monthly fee is not automatically a calendar-month fee, a 30-day fee or a daily rate. Partial-cycle proration is outside the core; complex arrears/advance rules require express semantics and separate support. Under **APPROVED PRODUCT POLICY PD-05**, no date substitution or automatic daily proration is allowed. Contractually supported invoice-date pricing/fallback and individually approved retroactive applicability are permitted; a price-changing interval requires explicit quantity and amount allocations, as in F32.

## 6. Amendment and document precedence

| Document/relationship | Approved interpretation |
| --- | --- |
| Original/master agreement | Initial term set, subject to evidenced incorporation, conditions and applicable amendments. |
| Amendment | Changes only expressly identified terms/scopes under an approved relationship to the master/affected term. |
| Addendum | Adds or modifies provisions as the governing text says; its title alone creates no priority. |
| Pricing schedule/exhibit | Governs the incorporated scope only; priority over conflicting master text requires express reviewed support. |
| Superseded term | Inactive for the specified future interval/scope under an evidenced approved replacement, retained for past periods. |
| Unchanged term | Continues only where the reviewed packet supports its continued applicability and no material unresolved modification affects it. |

An explicit replacement such as “Section 4.2 is deleted and replaced” needs the exact section, affected subject, new content, applicable parties and effective date. An explicit price modification from 18.40 to 19.10 needs the affected unit/SKU/date scope. An additive 2% fuel surcharge needs its base, scope, dates and conditions; it does not replace the base price. A missing referenced pricing schedule blocks the affected pricing even if the master price is readable.

Build a term-specific approved predecessor/supersession relationship. Dates can select terms within that relationship; they cannot invent the relationship. Never choose solely by latest upload, extraction version, signature timestamp, amendment number or maximum version number. Different amendments can coexist for different SKUs or fee components.

| Problem | Required outcome |
| --- | --- |
| Missing effective date | Needs review unless governing text provides an explicit, approved deterministic trigger/date. No default to signature date. |
| Missing amendment number | Not inherently blocking if unique identity, parent, scope, date and replacement relationship are established. Never assign priority by filename. |
| Two amendments conflict for the same scope/date | Ambiguous contract; require an evidenced approved resolution. No “newest wins” guess. |
| Several documents claim replacement of one term | Resolve explicit governing precedence and scope; otherwise block. |
| Missing referenced schedule/exhibit/waiver | Insufficient evidence for all scopes it may change; do not fall back to an old price. |
| Signature occurs after service but text expressly states a prior effective date | Retroactive applicability needs explicit authorized review of effectiveness and governing conditions (PD-05); no automatic legal inference. |
| Amendment effective after service, invoice issued later | Select the service-period term when service is the approved basis; later invoice issuance does not move the service. |
| New material evidence after a finding | Retain the historical snapshot; flag current applicability stale and require a new evaluation/approval. |

For an approved retroactive amendment signed August 1 but expressly effective July 1, a July 15 service can use the amended price in a later evaluation **only after** the retroactive application and its conditions are explicitly approved. Before that review, evaluation is blocked. A July 15 knowledge snapshot must not claim it had an August 1 document. Historical results identify the evidence available then; later approval creates a new evaluation without rewriting history. This is approved product policy, not a universal legal rule.

## 7. Expected versus actual: common financial gates

All compared inputs must be approved, tenant-consistent, source-grounded, applicable to the same entities, economic period, SKU/service, unit, tax basis and currency. Contract exceptions, credits and conditions materially affecting the scope must be resolved. A finding cannot be based on a price field alone while ignoring an applicable discount or a billed credit.

For a simple billed merchandise/service scope:

**Expected net = expected priced base − contractual discounts + applicable contractual charges.**

**Actual net = evidenced billed base − applied discounts − allocated credit reductions + billed charges/positive adjustments.**

Components outside that billing scope are excluded from both sides. No empty discount/fee/credit cell means zero: absence/zero must be established by approved review and a reconciled component set. Preserve signed source entries and their charge/credit/adjustment classification. A credit appears once in the bridge, not again in a later subtotal.

The invoice must reconcile its disclosed units/prices, discount/fee components, line amounts and relevant totals under the approved rounding profile or the documented invariant-result exception in section 11. A contradictory line total blocks automatic monetary calculation. Do not infer missing quantity by dividing a total by unit price, backsolve an unexplained discount, or distribute a residual across lines. Invoice quantity can support **price** assessment as the billed quantity; that does not verify physical delivery or prove quantity overbilling.

### 7.1 No double counting

The same cost scope has one monetary comparison result for the complete applicable pricing bundle. Rule violations may be labels/diagnostics on that result, not independent additive claims against the same billed money.

For 100 units, contract gross price 10 with a mandatory 10% discount on that contractual gross base, invoice gross price 12 with no discount: E = 100 × 10 × 0.90 = 900; A = 1,200; potential discrepancy = 300. A price diagnostic of 200 plus a discount diagnostic on the corrected base of 100 explains 300. Adding an inflated-base missing discount of 120 to 200 would falsely produce 320.

An invoice-wide discount overlaps the line bases it covers. Either evaluate the reconciled common scope with its full term bundle or block the unsupported allocation; never add an invoice discount finding to line findings that already include it. Separate fee comparisons may be additive only when they concern disjoint billed components and there are no unresolved shared credits/adjustments. No sum of overlapping rule labels is a “total leakage” metric.

Under **APPROVED PRODUCT POLICY PD-07**, directly allocated, evidenced credits reduce actual amounts for their own scope exactly once. Relevant unallocated credits or adjustments that could materially change the result block its authoritative amount. Unrelated undercharges remain separate informational diagnostics and never automatically offset positive findings. Cross-invoice credit reconciliation, cross-period netting and arbitrary invoice-level netting are excluded from V1.

An aggregate may sum only non-overlapping, independently supported, current compatible findings in the same currency/comparison basis, with coverage and period clearly stated. It is a view, not an additional finding. Superseded results, overlapping rule labels and informational undercharges are excluded from that positive-finding sum. A partial sum of assessed findings must not imply full invoice coverage or assess an unresolved scope. For independent deviations +200 and −200, supported positive findings total 200 and the −200 diagnostic stays separate; no automatic net-zero claim is made.

## 8. Pricing rules and calculation definitions

Each rule definition below is conditional on the common gates. “No finding” with a zero discrepancy means the scope was assessed; blocked/unsupported outcomes have a null monetary result.

### R1 — PRICE_MISMATCH_V1: fixed unit-price overcharge

Inputs: approved expected price Pₑ, comparable actual price Pₐ, billed quantity Q > 0, identical approved unit/currency/basis, economic applicability and a reconciled net billing scope. For the simple undiscounted/no-adjustment case:

Before required contractual rounding: Eraw = Q × Pₑ; Araw = Q × Pₐ; Δraw = (Pₐ − Pₑ) × Q. Apply the approved component/line/settlement profile to obtain comparable E and A, then calculate Δ = A − E. Potential leakage equals Δ only when Δ > 0. Do not independently round Δraw as a shortcut where separate required rounding of E/A would change the result. The invariant-result exception in section 11 may apply when no mode selection affects the outcome.

Equal prices produce no finding. A lower actual price produces an informational negative discrepancy and no positive finding. Missing quantity permits a unit-price diagnostic only; it cannot produce a total amount. Missing/conflicting expected price, incompatible units/currencies, known incomplete amendment coverage or unreconciled actual billing block the amount. Do not extrapolate a unit variance to unknown volumes.

If discounts or credits apply, the complete net comparison governs, not this isolated gross formula. Example: contractual net cost 1,000, billed gross 1,200 and explicitly allocated credit 200 yields A = 1,000 and no monetary overcharge. Gross unit-price variance remains a diagnostic.

### R2 — FIXED_FEE_OVERCHARGE_V1: recurring or one-time fixed fee

Inputs: approved fixed amount F for an exact supported billing cycle or one-time event, event/cycle identity, eligibility/conditions and the reconciled actual fee component A. E = F; Δ = A − F. An applicable monthly F = 5,000 versus A = 5,400 for the same full month yields 400.

Handling fees, recurring fees and fixed one-time fees share this mathematical family but preserve their distinct event/scope semantics. Do not compare one month’s fee to a three-month charge, generate extra periods, assume proration, or treat a contractual usage estimate as a fixed fee. Billings for several complete cycles may be handled only with explicit cycle allocation, without duplicating a cycle’s comparison.

### R3 — DISCOUNT_MISSING_V1: explicit unconditional percentage discount mismatch

The approved core supports an explicit unconditional contractual percentage only where its base and eligibility are explicit, approval-complete and compatible with the supported priced base. For percentage r, approved base B: D = B × r / 100; E = B − D. Actual is the reconciled net billed amount for the identical eligible scope. A positive A − E captures a missing or insufficient applied discount; a larger-than-required actual discount does not create negative leakage. A fixed-money contractual discount is outside this approved family and requires separate future scope approval, even though subtracting it would be mathematically simple.

Use the **contract-specified base**: line, identified SKU subset, or a complete explicitly eligible tax-exclusive invoice subtotal. Include/exclude supported fixed fees exactly as the term states. An 8% discount on an approved 50,000 eligible base produces 4,000 expected discount and 46,000 expected net. Do not include tax or unrelated freight. A tax-inclusive/tax-dependent discount base is outside the tax-exclusive V1 profile; do not silently reinterpret it as a pre-tax discount.

Simple line, full-subtotal or identified-SKU-subset cases require complete scope reconciliation under one master. Use one unconditional percentage for an eligible scope; do not compound discounts. Multiple-master invoices, threshold-conditioned discounts, period-level cumulative volumes, early-payment discounts and unsupported allocation are outside this core family. Complete condition evidence does not enable those deferred rules. Never infer a missing discount from invoice total alone.

If an inflated fixed unit price and a missing unconditional percentage discount both affect a base, the common pricing bundle produces one result as in section 7.1. This is composition of the two approved core families, not authorization for compound discounts or additional pricing families. PD-03 approves bounded, explicit scopes with no unresolved allocations.

### R4 — TIER_PRICE_MISMATCH_V1: explicit all-units or graduated tiers (conditional extension)

**OPTIONAL FUTURE PROFILE — NOT APPROVED FOR V1 CORE.** Every tier-based monetary scope returns UNSUPPORTED_RULE and a null finding in V1, even if its facts and method are approved. The definitions and examples here preserve future architectural support only; enabling a profile needs separate product approval and implementation authorization.

Required future approved semantics: method, quantity unit, aggregation scope/window, included transactions/SKUs, every threshold/price, boundary inclusivity, completeness of the schedule, treatment at zero and above the highest tier, eligible billed quantity and rounding. These illustrations use nonnegative whole-unit bands within one target scope. Fractional thresholds, cross-period aggregation and missing transaction coverage require additional data/support and are not authorized by these examples.

All-units: select the evidenced band containing Q and apply its unit price to all Q. Graduated: apply each band’s price only to quantity within that band; sum the disjoint segments. The band labels alone do not establish the method. Overlap/gap/conflicting tiers or a missing schedule block calculation. No average price or “most generous tier” guess.

For Q = 6,000, bands first 1,000 at 10, next 4,000 at 9, remaining at 8: all-units E = 48,000; graduated E = 54,000. Ambiguous semantics could turn the same 54,000 invoice into either no discrepancy or 6,000 potential discrepancy, so no authoritative choice is allowed.

### R5 — CONTRACTUAL_CHARGE_MISMATCH_V1: percentage surcharge or explicit excluded fee (conditional extension)

**OPTIONAL FUTURE PROFILE — NOT APPROVED FOR V1 CORE.** Percentage surcharges and explicit excluded-fee comparisons return UNSUPPORTED_RULE and a null finding in V1 even with complete evidence. A permitted fixed fee remains R2; that does not enable the separate R5 family. The following formulas are future mathematical specifications only.

For a permitted percentage surcharge s on an approved base B: Efee = B × s / 100, subject to explicit caps/floors/conditions only if supported. Compare the isolated actual fee for the same scope, then reconcile it within the non-overlapping full billing comparison. At B = 10,000 and s = 2%, Efee = 200; actual 300 gives 100 under the supported extension.

Prohibited fee: Efee = 0 only with explicit exclusion or an approved exhaustive applicable fee schedule that excludes that fee, with all material exceptions/waivers resolved and coverage attested. A fee absent from one extracted table is **UNVERIFIED FEE**, not unauthorized. Contractual zero here is evidenced prohibition, not a default for missing data. Generic caps/rate escalation/conditional surcharges require explicit additional semantics.

### Minimum commitments and quantity discrepancies

A mathematically explicit complete-period spend floor M on a known priced base G could define E = max(M, G), but only where the text establishes that exact relationship, cycle, credits, inclusion rules and conditions. An amount labeled “minimum commitment” alone does not establish a billing obligation. Minimum/take-or-pay and true-up logic are deferred from initial core; section 22 gives a counterfactual example, not permission to implement.

Quantity overbilling is also deferred. An invoice quantity exceeding a forecast/estimate is not proof of leakage. Even a stated maximum needs evidence of scope, approvals/change orders and whether it caps delivery, contractual commitment or payable quantity. Accepted delivery/PO quantities or an express fixed payable quantity could support a later separate rule. They must not be invented or confused with the billed quantity used by R1.

## 9. Currency and unit rules

Expected and actual must use the same explicitly resolved currency code, and that code must identify the same monetary unit for the evaluated period. A bare dollar symbol is insufficient. USD and EUR cannot be subtracted; there is no FX conversion, inferred exchange rate or multi-currency total. A different-currency contract/invoice pair is needs review/CURRENCY_MISMATCH even if numeric values coincide.

Version the currency metadata used for settlement/display precision. Do not impose two fractional digits universally, assume today’s code metadata reproduces all past documents, or equate numeric precision with currency settlement precision. Undefined/fund-code minor-unit conventions require an approved profile. Contractual settlement conventions and legal tender/cash rules are not inferred from ISO metadata.

The approved unit must match price denominator and billed quantity: item versus box, hour versus day, kg versus tonne, or price per 1 versus per 1,000. Initial core uses directly compatible units; no inferred conversion factors or silently changed price denominator. Explicit conversion profiles need separate supported scope/approval before expansion. Unit mismatch blocks arithmetic just as currency mismatch does.

## 10. Tax treatment

Initial V1 assesses **tax-exclusive contractual and billed components**. Tax itself is excluded from asserted leakage and monetary aggregation. If contract prices exclude tax and invoice states base 100 plus tax 15, compare 100 to 100, not 115 to 100. Do not infer a tax rate from jurisdiction, validate tax law or report the 15 as overcharge.

A tax-inclusive amount may be separated only using an explicitly approved source breakdown that establishes the comparable pre-tax component. An unitemized tax-inclusive invoice cannot be divided by an assumed tax rate. Contractual tax reimbursement wording is retained but unsupported tax interpretation remains blocked/deferred. Tax effects, recoverable VAT and cash recovery are outside Phase 4 findings.

## 11. Decimal precision, rounding and materiality

Preserve source precision and finite Decimal inputs; never introduce binary floats. Existing financial storage and Money accept at most 20 digits/6 fractional places and reject overflow/excess scale. Preserve those safeguards. Intermediate products may require more than 6 fractional places: retain them exactly in the conceptual calculation trace and do not truncate to fit a monetary column before required rounding.

Under **APPROVED PRODUCT POLICY PD-06**, the calculation record identifies rounding mode where established, quantum, stage, component/line versus invoice aggregation and currency metadata version. Required contractual rounding governs. No generic commercial-rounding fallback, ambient Python mode, hidden epsilon or hidden tolerance is allowed. If plausible unresolved rounding alternatives change whether a discrepancy exists or its amount, authoritative calculation is blocked until an applicable rounding profile is approved.

If the monetary result is invariant across the unresolved plausible methods, calculation may proceed with the uncertainty retained. Record the reviewed plausible alternatives, known quantum/stages, exact intermediates, comparison under each alternative and an invariance justification in the approval/evaluation snapshot; do not record a guessed mode as contractual truth. The reviewed evidence must bound the plausible alternatives sufficiently to establish invariance. An incomplete set or unknown precision/stage that could change the result blocks the amount. For simple exact values already aligned to every applicable quantum, invariance can be demonstrated without assigning a mode. All other fact, approval and applicability gates still apply.

If comparable E/A alternatives differ but all supported comparisons yield the same discrepancy and finding eligibility, preserve every alternative rather than publishing a guessed E or A. Only the invariant result may be asserted. Posted actual amounts and their precision remain evidence; invariance is not permission to change billed values, infer missing facts or hide uncertainty.

| Rounding condition | Authoritative V1 treatment |
| --- | --- |
| Applicable mode, quantum and stage approved | Apply that profile; preserve exact intermediates. |
| Exact E = 1,000.00 and A = 1,200.00, one line, known 0.01 quantum; unresolved mode cannot change either aligned amount | Allow Δ = 200.00, preserving the unresolved mode and invariance evidence. |
| Exact E = 10.005 and A = 10.01; half-up versus half-even changes Δ from 0.00 to 0.01 | Block; null finding until the profile is approved. |
| Two expected lines of 0.005; half-up known but line versus aggregate stage unresolved | Block: expected 0.02 versus 0.01 can change the result. |
| All gates passed and positive Δ = 0.01 | Retain the supported finding; no engine-level materiality suppression. |

The future execution requirement is an explicit Decimal context sized for the bounded expression and source digits, trapping unintended inexact operations. A candidate 80-significant-digit context must be justified against the actual expression/sum bounds during technical design; it is not an approved contractual rounding fallback. Unspecified nonterminating proration/division is unsupported. Store the arithmetic context and profile/invariance-record version so historical results do not depend on process settings.

Rounding sequence:

1. Retain unit prices and quantity exactly unless an explicit contract unit-rounding step exists.
2. Compute base and required discount/fee components at full available precision.
3. Apply only required component/line rounding steps, then sum according to the approved contractual stage.
4. Apply settlement rounding at its approved stage, or establish the invariant-result exception without guessing a mode; compare equivalent expected/actual amounts. Preserve posted actual precision; do not round away an unexplained invoice inconsistency.
5. Format display separately. Display formatting must never change finding eligibility or produce an apparent one-cent claim from an unknown rounding convention.

Example: exact expected 10.005, actual 10.01, quantum 0.01. Half-up yields expected 10.01 and zero discrepancy; half-even yields expected 10.00 and discrepancy 0.01. Without an approved applicable mode, the amount is blocked. Two lines of 0.005 under half-up can total 0.02 when rounded by line or 0.01 when rounded after summing; the stage is as material as the mode.

No engine-level materiality threshold may delete a genuine supported finding or change E, A or Δ. Every supported positive discrepancy survives calculation regardless of size. Later UI/reporting may group, sort, filter by amount or highlight material items while preserving underlying findings, amounts and explicit filter/coverage information. An express contractual exception remains subject to approved semantic mapping and supported core scope; it cannot be simulated by an engine tolerance. A computed output outside NUMERIC(20,6) is unsupported/reviewable, not silently rounded/truncated or stored via a precision migration in this task.

## 12. Charges, credits and adjustments

Classify each relevant signed source entry as CHARGE, CREDIT or ADJUSTMENT using approved source meaning, not the numeric sign alone. Retain the signed raw amount. Positive charge increases the billed scope; explicitly allocated negative credit decreases it. A negative unit/quantity must not be multiplied into a fake positive liability or coerced to satisfy the foundation’s positive-quantity constraint.

The approved core can account for explicit, approved **within-invoice allocated credits/rebates/adjustments** in the actual bridge when their economic relationship is unambiguous. A credit correcting the same charge reduces residual potential leakage once; it is not recovered money and does not create negative leakage. A relevant unallocated rebate, negative adjustment or refund that could materially change the result blocks the affected scope. Do not assign it to the largest overcharge or spread it proportionately without source-supported allocation.

Standalone credit notes, cross-invoice credit reconciliation, cross-period netting and unrelated undercharge offsets are excluded by PD-07. A known relevant unresolved credit note blocks a residual current finding rather than being ignored. Any extension requires separate future approval. Payment/refund confirmation and later recovery are outside this phase. Each credit/adjustment identity may reduce actual billing only once in a given comparison; overlapping rule evaluations cannot consume it twice. Compatible positive findings may be summed only as the non-overlapping view defined in section 7.1.

## 13. Terminology and finding lifecycle

| Business label | Meaning | Existing CaseStatus alignment |
| --- | --- | --- |
| Potential leakage detected | Supported positive scoped discrepancy from approved inputs; human monetary confirmation pending | `detected` |
| Needs review | A finding needs review, or an existing finding’s applicability changed | `needs_review` for existing findings; blocked evaluation remains a separate nonmonetary result |
| Validated leakage | Authorized reviewer confirmed the calculation and its scope | `confirmed` |
| Dismissed finding | Reviewed as inapplicable/false positive with a reason | `false_positive` |
| Recovered value | Cash or credited value actually recovered and reconciled later | Not produced/tracked by Phase 4 |
| Avoided value | Future expense prevented with an evidenced baseline later | Not produced/tracked by Phase 4 |

Do not create competing finding enums named candidate/validated/dismissed where existing meanings suffice. Extraction review decisions and matching/evaluation outcomes remain separate concepts. `investigating` and `resolved` exist in the foundation but their workflows are deferred; Phase 4 must not reinterpret `resolved` as recovered or zero out a validated case.

Conceptual transitions: detected → confirmed, false_positive or needs_review; needs_review → confirmed or false_positive after resolution. Final monetary confirmation follows PD-01 authority: owner/admin authorize; analysts may propose and annotate; viewers are read-only. Reopening a confirmed/dismissed case requires an authorized, audited review event and a pinned recalculation if inputs changed. Confirmation does not authorize manually rewriting a calculated number. A revised amount needs new approved facts/policy inputs and a new immutable result linked to its predecessor.

Potential exposure is positive; validated exposure is unknown until confirmation, then equals the specifically confirmed current calculation. Do not sum potential and validated values. The foundation’s recovered_amount default of zero is not evidence of a recovery outcome; Phase 4 does not display it as tracked recovery or populate it with detected amounts. Confidence_score remains null unless a later calibrated policy exists. High extraction certainty is not “99% recoverable.”

## 14. Finding invariants and rule versioning

Every monetary finding must preserve: tenant; approved invoice and target scope/line; master agreement and applicable term/version snapshot; entity match and supporting links; economic dates and knowledge cutoff; approved fact identities/revisions; source hashes/run versions/raw locations; quantity/unit/currency; full expected/actual component bridge; signed discrepancy; nonnegative positive output; rounding profile or invariant-result evidence and retained uncertainty; completeness/exception decisions; expression, intermediate values and result; exact rule/program/policy versions; and non-overlap/currentness information.

All material dependencies need traceable evidence, including a supported discount base, fee prohibition or retroactive applicability. The engine must reproduce the number from this frozen data without today’s mutable “latest extraction.” These are minimum Phase 4 calculation records, not a Proof Engine implementation or legal evidence-package generator.

The approved core identities are `PRICE_MISMATCH_V1`, `FIXED_FEE_OVERCHARGE_V1` and `DISCOUNT_MISSING_V1` (unconditional percentages only). `TIER_PRICE_MISMATCH_V1` and `CONTRACTUAL_CHARGE_MISMATCH_V1` identify documented optional future families, not active V1 support. The full compiled pricing program and supporting policy profiles are versioned too. A category label is not a sufficient version identity. Changes to bases, ordering, selection, rounding, conditions or supported scope require a new immutable version and reevaluation; past records retain their original behavior.

Do not claim all versions are simultaneously additive/current. Old snapshots stay auditable; current views must identify the approved active calculation for a scope and exclude superseded duplicates from current totals.

## 15. Determinism and idempotency

Same tenant, approved input revisions, target scope, source versions, applicability snapshot and rule/policy versions must produce the same outcome and amount, including blocked outcomes. Execution time or random UUIDs must not change the calculation identity.

Conceptual evaluation fingerprint: SHA-256 of a versioned canonical representation containing organization, stable invoice/line/scope identity, sorted approved fact IDs/revisions and semantic values/types, document hashes/run versions, approved match/link revision, applicable term/precedence snapshot, economic interval/knowledge snapshot, program/rule versions, supported-scope profile, rounding profile or invariant-result record, aggregation policy and relevant credit allocations. Normalize decimal numeric equivalence for this key under an explicit canonical format, preserve semantic roles/units, and do not collapse null with zero, unknown with not-applicable, or missing with an empty list. Source raw values and source identities remain in the immutable record even if numeric strings are canonically equal. UI filters/materiality preferences do not change calculation identity or delete findings.

Sort unordered sets; preserve ordered contractual operations. Fingerprint rules themselves have a version. No current-time field belongs in the key unless it is the explicitly pinned knowledge/as-of input. Repeating an identical request returns the existing outcome/finding; it must not reopen a dismissal, recreate a monetary case or double-count a credit. A later approval revision creates a distinct fingerprint and predecessor relationship, not a duplicate to add to the old amount. Reprocessing Phase 3 candidates does not automatically revoke approvals pinned to an earlier run; material changes trigger review rather than silent replacement.

## 16. Uncertainty decision table

Evaluation labels below are conceptual reasoned outcomes. They do not modify document status or introduce database enums now.

| Condition | Outcome/reason | Monetary amount |
| --- | --- | --- |
| All required approvals, unique applicable match, supported term, currency/unit/base, quantity and reconciliation present | ASSESSABLE | Compute; positive becomes detected, nonpositive becomes NO_OVERCHARGE. |
| High-confidence price only, approval absent | NEEDS_REVIEW / FACT_NOT_APPROVED | Null. |
| Conflicting contractual price or amendment priority | AMBIGUOUS_CONTRACT | Null. |
| Missing quantity for a unit rule | INSUFFICIENT_EVIDENCE / QUANTITY_MISSING | Null; optional unit variance diagnostic, no estimated volume. |
| Missing expected price/base/condition | INSUFFICIENT_EVIDENCE | Null. |
| Two equally plausible contracts | AMBIGUOUS_MATCH | Null. |
| Explicit contract reference, conflicting legal party | NEEDS_REVIEW / ENTITY_CONFLICT | Null. |
| Expiry known, service outside, no applicable continuation | UNMATCHED_APPLICABILITY | Null, not zero. |
| Renewal/continuation unknown | NEEDS_REVIEW / RENEWAL_UNRESOLVED | Null. |
| Price-changing service interval without allocations | NEEDS_REVIEW / ALLOCATION_REQUIRED | Null. |
| Dollar currency unresolved or currency mismatch | NEEDS_REVIEW / CURRENCY_UNRESOLVED or CURRENCY_MISMATCH | Null. |
| Unit/price denominator incompatible | NEEDS_REVIEW / UNIT_MISMATCH | Null. |
| Unsupported tier, conditional obligation, tax or FX interpretation | UNSUPPORTED_RULE | Null. |
| Tax-inclusive amount without approved comparable breakdown | INSUFFICIENT_EVIDENCE / TAX_BASIS_UNKNOWN | Null. |
| Unexplained credits, adjustments or line-total contradiction | NEEDS_REVIEW / ACTUAL_RECONCILIATION_REQUIRED | Null. |
| Required rounding convention materially changes outcome | NEEDS_REVIEW / ROUNDING_UNRESOLVED | Null. |
| Unresolved plausible rounding methods provably leave the monetary result invariant; all other gates pass | ASSESSABLE / ROUNDING_UNCERTAINTY_RETAINED | Compute with frozen invariance evidence; no guessed mode. |
| Relevant schedule/amendment unreadable or unavailable | INSUFFICIENT_EVIDENCE / GOVERNING_PACKET_INCOMPLETE | Null. |
| Computed output cannot be represented safely | UNSUPPORTED_RULE / NUMERIC_RANGE | Null; no truncation. |

Record all material blockers, even if one is displayed first. A known-zero assessed amount and an unassessed null result are distinct in reports and totals. With partial invoice coverage, report which scopes/rules were assessed; do not extrapolate findings to unassessed scopes.

## 17. False-positive safeguards

The following are unconditional stops for an affected monetary scope: unapproved or ungrounded inputs; unresolved material conflict; weak-only match; entity mismatch; unidentified applicable term; incomplete known governing packet; unsupported condition/base; unknown economic date where needed; unallocated changes across periods; ambiguous currency/unit; contradictory actual billing; relevant unallocated credit; unknown material tax/rounding semantics; numeric overflow; or overlap without an approved reconciliation plan.

Additional controls:

- Absence of a fee in a table is not a prohibition. Explicit exclusion/exhaustiveness is necessary.
- Supplier similarity, document title, invoice date convenience and amendment numbering are not legal/economic precedence.
- A missing referenced amendment/schedule does not preserve an old price by default.
- Contract quantity estimates do not prove delivered quantity; a lower actual price is not positive leakage.
- Unreadable or unmapped content may govern a price; high confidence in extracted numbers does not cure missing coverage.
- A known credit or discount must not be ignored to inflate an overcharge. An amount already netted must not be deducted twice.
- Positive diagnostics from multiple rules on one charge are not additive monetary findings.
- Tax-inclusive invoices and FX/unit differences do not create a comparable difference by numerical subtraction.
- Approval timestamps, access rights and organization scope remain auditable. A source cannot grant its own permissions or redefine a rule.
- No legal entitlement, recovered savings, paid loss or future avoided value is inferred from a billing discrepancy.

## 18. Approved Phase 4 V1 core and deferred categories

**APPROVED PRODUCT POLICY PD-03: exactly three authoritative core families**, conditioned on complete manually approved facts and mappings, a scope-specific governing-packet attestation, authoritative matching and all common financial gates:

1. Fixed unit-price overcharge — `PRICE_MISMATCH_V1`.
2. Fixed recurring/fixed-fee overcharge — `FIXED_FEE_OVERCHARGE_V1`.
3. Explicit unconditional percentage discount mismatch — `DISCOUNT_MISSING_V1`.

This approval defines business scope only; implementation remains unauthorized. The compiler’s semantic mapping/approval and complete financial bridge are prerequisites. The architecture must be able to represent unsupported terms and future families without silently enabling them.

| Rule/category | Classification | Factual reason |
| --- | --- | --- |
| Fixed unit-price overcharge | APPROVED CORE V1 after common gates | One comparable price and billed quantity; no external dataset. |
| Fixed recurring/one-time fee overcharge | APPROVED CORE V1 for complete identified cycles/events | Explicit amount and billing scope; partial-cycle semantics excluded. |
| Explicit unconditional percentage discount mismatch | APPROVED CORE V1 for explicit line/subset/subtotal bases | One percentage on an evidenced eligible base; no missing conditions, compounding, period accumulation or allocation. |
| Fixed-money contractual discount | DEFERRED; outside approved R3 | PD-03 approves percentages only. An actual allocated credit can enter the billing bridge without enabling a fixed-money contractual-discount rule. |
| Explicit all-units/graduated tier mismatch | OPTIONAL FUTURE; additional approval/data required; not V1 | Phase 3 does not establish method, complete bands/boundaries or aggregation coverage; complete facts alone do not enable this family. |
| Explicit percentage surcharge or excluded-fee mismatch | OPTIONAL FUTURE; additional approval/data required; not V1 | Exact base/conditions or exhaustive exclusion/exception coverage required; permitted fixed amounts remain the distinct R2 core family. |
| Simple spend-floor/minimum commitment | Defer from initial core | Labels do not establish max/floor versus take-or-pay/true-up semantics or credit treatment. |
| Quantity overbilling | Requires additional authoritative delivery/PO/fixed-payable-quantity data; defer | Billed quantity or a forecast alone is insufficient. |
| Cross-period/cross-invoice volume rebates | Requires complete population/period and allocation; defer | Missing invoices can change tier or rebate entitlement. |
| Threshold-conditioned/cumulative-volume discounts, early-payment discounts | DEFERRED; not unconditional R3 | Entitlement depends on quantity/period/payment conditions, not solely a supported unconditional percentage. |
| Complex SLA/service credits | Defer | Performance measurement, notice, caps, exclusions and remedies must be evidenced. |
| Index/CPI escalation | Defer | Requires external series/version/basis date, lag, cap/floor and adjustment semantics. |
| FX conversion | Defer | Needs contractual rate source/date/spread conventions and a separate comparable-currency policy. |
| Tax-law interpretation/tax leakage | Defer | Contract text and invoice breakdown do not establish legal tax liability. |
| Retroactive true-up programs | Defer | Cross-period entitlements, billing population and credits require a reconciliation model. A single expressly approved retroactive fixed price is separately gated. |
| Natural-language conditional legal obligations | Defer until supported factual conditions and mapping exist | An extracted sentence does not prove enforceability or condition satisfaction. |
| Partial-period proration, complex compounded discounts | Defer from initial core | Missing denominator, boundary or ordering can change the result. |
| Standalone credit-note/payment/refund recovery reconciliation | Defer | Phase 3 secondary documents lack sophisticated extraction; cash receipt/recovery tracking is a later phase. |
| Fuzzy duplicate invoices, enterprise integrations, Proof Engine, Recovery Ledger | Outside Phase 4 specification’s implementation scope | Separate product phases/data and workflows. |

Cases using OPTIONAL FUTURE/DEFERRED rules provide mathematical illustrations and blocking behavior. The approved V1 core must return UNSUPPORTED_RULE and a null finding for those features even when their factual inputs are complete. No optional profile is authorized by this document. Separate later product approval, data support and implementation authorization are all required to enable one.

A supported core rule may not bypass a material unsupported term that changes its own scope’s expected or actual value. Do not flatten a tier into a chosen fixed price, omit a conditional discount, or ignore a minimum/surcharge to create a core finding. Other independently supported disjoint scopes may be assessed only where the reviewed packet establishes that unsupported terms do not affect them; coverage stays explicit.

## 19. Matching test matrix

Assume same tenant and source-approved identities unless a row states otherwise. MATCH means authoritative association, not automatic calculation readiness.

| Case | Source evidence | Outcome | Why/calculation gate |
| --- | --- | --- | --- |
| M01 | Exact ABC-001; approved matching vendor/buyer; one unique contract | MATCH | Strong reference plus identities; terms/date still checked. |
| M02 | Exact ABC-001; vendor legal entity conflicts | NEEDS REVIEW | Identifier does not defeat an entity contradiction. |
| M03 | No ID; unique vendor/buyer and one active contract with plausible SKU | CANDIDATE | Uniqueness is not proof; needs evidenced manual association. |
| M04 | No ID; three active same-vendor contracts | AMBIGUOUS | Names/active status cannot select the contractual arrangement. |
| M05 | Explicit PO-7; approved PO-7 uniquely linked to ABC-001; identities agree | MATCH | Approved link is authoritative; PO pricing terms not inferred. |
| M06 | Exact ID; service after explicit expiry; reviewed packet shows no applicable continuation | NO MATCH to applicable terms | Retain identity link; no price for the service. Unknown renewal changes this to NEEDS REVIEW. |
| M07 | Exact ID and entities; service date inside applicable interval | MATCH | Date applicability satisfied, other gates remain. |
| M08 | Invoice date within contract; explicit service outside it | NO MATCH to applicable terms / NEEDS REVIEW if continuation unknown | Contract-approved service basis prevails over invoice date. |
| M09 | Exact ID; amendment exists and its parent/scope/precedence/dates are approved | MATCH | Match the master, resolve amended terms individually. Ambiguous amendment blocks calculation. |
| M10 | Exact ID/entities; service-priced term but no service date/period | NEEDS REVIEW | Association known; pricing date unknown. No invoice-date fallback without governing support. |
| M11 | Exact legal supplier name alone, no approved IDs/association, multiple agreements | AMBIGUOUS | Legal-name text alone cannot establish the contract or choose among agreements. |
| M12 | Header ABC-001, line XYZ-002 with shared unallocated discount | NEEDS REVIEW | Multiple/conflicting master scopes block authoritative invoice evaluation under PD-02; no automatic allocation. |
| M13 | Exact ABC-001 but two contracts share reference within eligible namespace | AMBIGUOUS | Reference is not unique. |

## 20. Effective-date and amendment test matrix

2026 date examples use explicitly approved date boundaries and service basis except D01’s stated invoice-date condition.

| Case | Facts | Applicable expected unit price/outcome |
| --- | --- | --- |
| D01 | Contract effective Jan 1 at 10; invoice Feb 1; contract expressly prices on invoice date | 10. If that date basis is absent and service date unknown, NEEDS REVIEW instead. |
| D02 | Master 10; approved modification to 12 effective July 1; service June 15 | 10; later invoice issuance is irrelevant. |
| D03 | Same; service July 15 | 12. |
| D04 | Same; service interval June 15–July 15; only aggregate quantity | ALLOCATION REQUIRED; no single expected amount. |
| D05 | Amendment signed Aug 1, expressly effective July 1; service July 15 | Pending retroactive approval: NEEDS REVIEW. With approved applicability and later knowledge snapshot: 12. No automatic legal interpretation. |
| D06 | Amendment price 12, no effective date or deterministic governing trigger | NEEDS REVIEW; do not use signature date. |
| D07 | Same-day competing prices 12 and 13, no approved precedence | AMBIGUOUS CONTRACT; no chosen price. |
| D08 | Amendment modifies SKU A only; SKU B price 10 is reviewed as unchanged | SKU A uses approved new term; SKU B may use 10 if its complete scope is established. |
| D09 | New schedule referenced as governing but unavailable | INSUFFICIENT EVIDENCE; master price is not a fallback. |
| D10 | Amendment number missing, parent/target/effective date/replacement explicit and approved | Use amended term; numbering is not required for priority. |
| D11 | Price change effective July 1; service July 1 | New price 12 under explicit inclusive effective boundary. |
| D12 | 400 units before change at 18.40; 600 after at 19.10; independent approved allocations | E = 7,360 + 11,460 = 18,820; no daily allocation inferred. |
| D13 | Fee monthly 5,000; partial billing interval; no proration convention | UNSUPPORTED/NEEDS REVIEW; no automatic daily rate. |
| D14 | Master fee 250; approved additive 2% surcharge on named base from Aug 1 | Precedence preserves base/fee terms. V1 blocks the surcharge-dependent scope as UNSUPPORTED_RULE; an OPTIONAL FUTURE profile could add it only after separate authorization. |

## 21. Pricing decision tables

### 21.1 Tier arithmetic and boundaries

Synthetic schedule: up to 1,000 whole units at 10; 1,001–5,000 at 9; 5,001+ at 8. Method and unit/aggregation scope must be explicit and approved. In the graduated interpretation, lengths are first 1,000, next 4,000, remainder; the table is not a universal reading of vague range labels.

**Every tier/surcharge/excluded-fee formula below is OPTIONAL FUTURE and outside the approved V1 core.** The matrix demonstrates method sensitivity; it does not authorize a V1 tier finding.

| Quantity | All-units expected | Graduated expected |
| --- | --- | --- |
| 1,000 | 1,000 × 10 = 10,000 | 1,000 × 10 = 10,000 |
| 1,001 | 1,001 × 9 = 9,009 | 1,000 × 10 + 1 × 9 = 10,009 |
| 5,000 | 5,000 × 9 = 45,000 | 1,000 × 10 + 4,000 × 9 = 46,000 |
| 5,001 | 5,001 × 8 = 40,008 | 10,000 + 36,000 + 1 × 8 = 46,008 |
| 6,000 | 6,000 × 8 = 48,000 | 10,000 + 36,000 + 1,000 × 8 = 54,000 |

An all-units total can fall at a threshold under an explicit valid schedule; the engine must not “repair” it into marginal pricing. For 11,000 units under the alternative 1–10,000 at 20 / 10,001–50,000 at 18 / 50,001+ at 16 schedule: all-units = 198,000; graduated = 218,000. Ambiguous method blocks both schedules.

| Pricing condition | Decision |
| --- | --- |
| Explicit all-units method, full schedule, approved in-scope volume | V1: UNSUPPORTED_RULE/null. Separately authorized future profile could select one band. |
| Explicit graduated method, contiguous full bands | V1: UNSUPPORTED_RULE/null. Separately authorized future profile could sum segments. |
| Method absent, overlapping/gapped bands, missing upper treatment | Block; no closest-price or lowest-price heuristic. |
| Aggregate depends on all month’s invoices, incomplete month/population | DEFERRED from V1 even with a full population; missing coverage is an additional blocker. |
| Percentage fee with exact approved base, scope and conditions | V1: UNSUPPORTED_RULE/null. Calculation belongs to an OPTIONAL FUTURE charge profile. |
| Fee absent from extracted schedule, no exclusion/exhaustiveness | UNVERIFIED FEE, no amount asserted. |
| Explicit fee exclusion, complete approved exception coverage | V1: UNSUPPORTED_RULE/null. OPTIONAL FUTURE charge profile could use source-supported expected zero. |
| Full recurring cycle/event and fixed amount | Core fixed-fee rule eligible. |
| Unsupported partial cycle, quantity estimate or minimum label only | Block/defer. |

### 21.2 Discount basis

| Contract wording/approved mapping | Permitted base | Stop condition |
| --- | --- | --- |
| 8% of a named line’s pre-tax contractual gross | Approved line base | Unknown gross/net or charge/credit allocation. |
| 10% of SKUs A/B only | Complete priced base for approved A/B set | Unidentified SKU or missing allocation. |
| 8% of complete invoice subtotal, tax/fees excluded | Reconciled approved eligible subtotal | Total substituted for subtotal, mixed-contract terms or missing components. |
| One unconditional percentage on a base explicitly including a permitted fixed fee | Approved reconciled eligible base including that fee | Fee eligibility or base ordering unresolved; percentage surcharge-dependent bases remain unsupported. |
| Discount after another discount | Future explicit ordered base only | Compound discounts are DEFERRED from V1 even if order is explicit. |
| Volume-threshold/period-level discount | Future exact eligible volume for that window only | DEFERRED from V1; incomplete population/conditions additionally block. |
| Early-payment discount | Future supported condition plus evidenced timely payment only | DEFERRED from V1 even if payment is known; due date alone is not payment evidence. |
| Fixed-money contractual discount | Future explicit monetary reduction/base only | DEFERRED from V1; not part of the approved percentage family. |

## 22. Worked financial acceptance examples

The vectors below are synthetic. Unless noted otherwise, all calculation-driving facts, party identities, match, scope, governing packet, dates and within-invoice allocations are approved and conflict-free; amounts are USD, tax-exclusive, directly compatible units, with an expressly approved settlement profile rounding monetary outputs half-up to 0.01 at the stated line/component stage. No hidden credit/fee/discount exists for the assessed scope. These assumptions are **test inputs**, not defaults inferred for real invoices.

**CORE** means one of the three approved initial families, subject to every gate. **OPTIONAL FUTURE** means mathematical behavior if a separate future tier/charge profile were authorized with all required facts approved; these profiles are not approved or implemented. V1 always returns UNSUPPORTED_RULE and a null finding for them. **DEFERRED** remains unsupported. Approval of a synthetic input in an illustration does not change rule eligibility. Calculated illustrations for blocked cases are alternatives/diagnostics and must not become monetary findings. All lifecycle statuses below describe future expected outputs; no case is created by this specification task.

### F01 — Correct unit-price invoice

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Approved contract price 10.00/unit; billed quantity 100; invoice price 10.00/unit; line amount 1,000.00. |
| APPLICABLE RULE | CORE R1, PRICE_MISMATCH_V1. |
| EXPECTED AMOUNT | 1,000.00 USD. |
| ACTUAL AMOUNT | 1,000.00 USD. |
| CALCULATION | E = 100 × 10.00; A = 100 × 10.00; Δ = 0.00. |
| RESULT | Assessed; no positive leakage and no monetary finding. |
| STATUS | Evaluation: NO_OVERCHARGE; no CaseStatus created. |
| WHY | Identical approved price, quantity and basis reconcile. This conclusion covers only this assessed scope. |

### F02 — Unit-price overcharge at material volume

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Contract 18.40/unit; invoice 20.10/unit; billed quantity 43,647; reconciled line amount 877,304.70. |
| APPLICABLE RULE | CORE R1, PRICE_MISMATCH_V1. |
| EXPECTED AMOUNT | 803,104.80 USD. |
| ACTUAL AMOUNT | 877,304.70 USD. |
| CALCULATION | E = 43,647 × 18.40; A = 43,647 × 20.10; Δ = 43,647 × 1.70 = 74,199.90. |
| RESULT | Potential leakage 74,199.90 USD; one scoped finding. |
| STATUS | CaseStatus `detected`; validated amount remains unknown. |
| WHY | Approved comparable prices and billed quantity produce a reproducible positive discrepancy. No recovery is asserted. |

### F03 — Invoice cheaper than contract

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Contract 10.00/unit; quantity 100; invoice 9.00/unit; line amount 900.00. |
| APPLICABLE RULE | CORE R1, PRICE_MISMATCH_V1. |
| EXPECTED AMOUNT | 1,000.00 USD. |
| ACTUAL AMOUNT | 900.00 USD. |
| CALCULATION | Δ = 900.00 − 1,000.00 = −100.00. |
| RESULT | Informational undercharge 100.00; no positive leakage and no negative leakage finding. |
| STATUS | Evaluation: NO_OVERCHARGE; no CaseStatus created. |
| WHY | A negative discrepancy is not a monetary claim by the buyer and is not automatically netted against unrelated findings. |

### F04 — Required discount missing

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Approved eligible contractual gross base 50,000.00; unconditional 8% discount on that base; invoice applies zero discount and bills 50,000.00. |
| APPLICABLE RULE | CORE R3, DISCOUNT_MISSING_V1. |
| EXPECTED AMOUNT | 46,000.00 USD. |
| ACTUAL AMOUNT | 50,000.00 USD. |
| CALCULATION | D = 50,000.00 × 0.08 = 4,000.00; E = 50,000.00 − 4,000.00; Δ = 4,000.00. |
| RESULT | Potential leakage 4,000.00 USD. |
| STATUS | CaseStatus `detected`. |
| WHY | The exact eligible base, percentage and unconditional applicability are established; no other price discrepancy overlaps it. |

### F05 — Required discount correctly applied

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Same 50,000.00 eligible base and required 8%; invoice separately applies 4,000.00 discount and bills 46,000.00. |
| APPLICABLE RULE | CORE R3, DISCOUNT_MISSING_V1. |
| EXPECTED AMOUNT | 46,000.00 USD. |
| ACTUAL AMOUNT | 46,000.00 USD. |
| CALCULATION | E = 50,000.00 × 0.92; A = 50,000.00 − 4,000.00; Δ = 0.00. |
| RESULT | No positive leakage. |
| STATUS | Evaluation: NO_OVERCHARGE; no CaseStatus created. |
| WHY | Actual reduction satisfies the approved obligation on the same base; the gross invoice amount is not compared with expected net. |

### F06 — Fixed recurring fee overcharge

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Contract specifies 5,000.00 for a complete identified July billing cycle; invoice covers exactly that cycle and bills 5,400.00. |
| APPLICABLE RULE | CORE R2, FIXED_FEE_OVERCHARGE_V1. |
| EXPECTED AMOUNT | 5,000.00 USD. |
| ACTUAL AMOUNT | 5,400.00 USD. |
| CALCULATION | Δ = 5,400.00 − 5,000.00 = 400.00. |
| RESULT | Potential leakage 400.00 USD. |
| STATUS | CaseStatus `detected`. |
| WHY | Amount and complete contractual cycle match; no daily proration or inferred calendar convention is used. |

### F07 — Legitimate fixed handling fee

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Applicable approved clause permits handling fee 250.00 for one identified complete monthly cycle; invoice bills that fee once at 250.00. |
| APPLICABLE RULE | CORE R2, FIXED_FEE_OVERCHARGE_V1. |
| EXPECTED AMOUNT | 250.00 USD. |
| ACTUAL AMOUNT | 250.00 USD. |
| CALCULATION | Δ = 250.00 − 250.00 = 0.00. |
| RESULT | No positive leakage. |
| STATUS | Evaluation: NO_OVERCHARGE; no CaseStatus created. |
| WHY | A separately named fee is legitimate where its amount, event and conditions are expressly approved. |

### F08 — Unverifiable fee in incomplete packet

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Invoice handling charge 250.00; extracted pricing table does not mention it; no approved exclusion or exhaustive fee schedule; referenced addendum unavailable. |
| APPLICABLE RULE | R5 eligibility/coverage gate; no approved fee obligation or prohibition. |
| EXPECTED AMOUNT | Unknown; null. Absence from one table does not establish zero. |
| ACTUAL AMOUNT | Identified billed charge 250.00 USD. |
| CALCULATION | A − E cannot be calculated because E is unknown. |
| RESULT | V1: UNSUPPORTED_RULE, with UNVERIFIED_FEE / INSUFFICIENT_EVIDENCE retained; monetary finding null. |
| STATUS | Evaluation: NEEDS_REVIEW; no monetary CaseStatus created. |
| WHY | Coverage is incomplete. Calling this 250.00 unauthorized leakage would invent a prohibition. |

### F09 — Explicit all-units tier (OPTIONAL FUTURE)

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Approved all-units schedule: 1–1,000 at 10; 1,001–5,000 at 9; 5,001+ at 8; scoped whole-unit quantity 6,000; invoice bills 54,000.00. |
| APPLICABLE RULE | OPTIONAL FUTURE R4, TIER_PRICE_MISMATCH_V1; hypothetical separately authorized all-units profile, never core V1. |
| EXPECTED AMOUNT | 48,000.00 USD under that profile. |
| ACTUAL AMOUNT | 54,000.00 USD. |
| CALCULATION | Q selects final band; E = 6,000 × 8 = 48,000; Δ = 6,000.00. |
| RESULT | Enabled optional profile: potential leakage 6,000.00. Initial core: UNSUPPORTED_RULE, finding null. |
| STATUS | Optional profile: CaseStatus `detected`; initial core: blocked evaluation only. |
| WHY | All units receive the selected rate because the approved clause says so; graduated pricing is not substituted. |

### F10 — Explicit graduated tier (OPTIONAL FUTURE)

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Approved graduated method: first 1,000 at 10, next 4,000 at 9, remainder at 8; scoped quantity 6,000; invoice bills 54,000.00. |
| APPLICABLE RULE | OPTIONAL FUTURE R4, TIER_PRICE_MISMATCH_V1; hypothetical separately authorized graduated profile, never core V1. |
| EXPECTED AMOUNT | 54,000.00 USD under that profile. |
| ACTUAL AMOUNT | 54,000.00 USD. |
| CALCULATION | E = 1,000 × 10 + 4,000 × 9 + 1,000 × 8 = 54,000; Δ = 0.00. |
| RESULT | Optional profile: no positive leakage. Initial core: UNSUPPORTED_RULE, finding null; not a cleared scope. |
| STATUS | Optional profile: NO_OVERCHARGE; initial core: blocked evaluation; no CaseStatus created. |
| WHY | Segment prices apply only to their own units. Method changes the answer despite identical bands and invoice. |

### F11 — Ambiguous tier method

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Schedule gives the same three ranges/prices but does not establish all-units versus graduated; quantity 6,000; invoice 54,000.00. |
| APPLICABLE RULE | R4 method gate, including any future tier profile. |
| EXPECTED AMOUNT | Unknown; alternatives are 48,000.00 or 54,000.00 USD, neither selected. |
| ACTUAL AMOUNT | 54,000.00 USD. |
| CALCULATION | Diagnostic alternatives: Δ = 6,000.00 or 0.00. No authoritative subtraction. |
| RESULT | V1: UNSUPPORTED_RULE plus TIER_METHOD_AMBIGUOUS; monetary finding null. Ambiguity also blocks any future tier profile. |
| STATUS | Evaluation: NEEDS_REVIEW; no monetary CaseStatus created. |
| WHY | Choosing the lower expected total would fabricate an entitlement; enabling a tier rule does not cure ambiguous terms. |

### F12 — Amendment effective before service

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Master 10.00/unit; approved explicit modification to 12.00 effective July 1; service July 15; quantity 100; invoice 13.00/unit. |
| APPLICABLE RULE | CORE R1 with approved service-date and term-replacement selectors. |
| EXPECTED AMOUNT | 1,200.00 USD. |
| ACTUAL AMOUNT | 1,300.00 USD. |
| CALCULATION | Service selects 12.00; E = 100 × 12; A = 100 × 13; Δ = 100.00. |
| RESULT | Potential leakage 100.00 USD. |
| STATUS | CaseStatus `detected`. |
| WHY | The scoped amendment governs this service; the master price cannot be retained to inflate the finding to 300.00. |

### F13 — Amendment effective after service

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Same master 10.00 and July 1 modification to 12.00; service June 15; invoice issued August 15 at 12.00/unit; quantity 100. |
| APPLICABLE RULE | CORE R1 with approved service-date selector. |
| EXPECTED AMOUNT | 1,000.00 USD. |
| ACTUAL AMOUNT | 1,200.00 USD. |
| CALCULATION | June service selects 10.00; Δ = 100 × (12 − 10) = 200.00. |
| RESULT | Potential leakage 200.00 USD. |
| STATUS | CaseStatus `detected`. |
| WHY | Invoice issuance after the amendment does not change a service-priced obligation for June. |

### F14 — Service interval crossing amendment without allocation

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Price 10.00 before July 1, 12.00 from July 1; service June 15–July 15; only aggregate quantity 100 and billed amount 1,200.00 available. |
| APPLICABLE RULE | CORE R1 applicability/allocation gate. |
| EXPECTED AMOUNT | Unknown; null because units before/after the change are not evidenced. |
| ACTUAL AMOUNT | Aggregate 1,200.00 USD; period allocation unknown. |
| CALCULATION | E would require Qold × 10 + Qnew × 12, with Qold + Qnew = 100; the individual quantities are unknown. |
| RESULT | ALLOCATION_REQUIRED; monetary finding null. |
| STATUS | Evaluation: NEEDS_REVIEW; no monetary CaseStatus created. |
| WHY | Days, invoice date and an average price cannot establish the distribution of delivered/billed units. |

### F15 — Currency mismatch

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Contract 10.00 USD/unit; quantity 100; invoice 12.00 EUR/unit and line total 1,200.00 EUR. |
| APPLICABLE RULE | R1 currency-comparability gate. |
| EXPECTED AMOUNT | 1,000.00 USD for the contractual scope. |
| ACTUAL AMOUNT | 1,200.00 EUR. |
| CALCULATION | Within-currency products are known; 1,200 EUR − 1,000 USD is prohibited. |
| RESULT | CURRENCY_MISMATCH; monetary finding null. |
| STATUS | Evaluation: NEEDS_REVIEW; no monetary CaseStatus created. |
| WHY | A numeric difference of 200 is not a monetary discrepancy without comparable currencies. FX conversion is excluded. |

### F16 — Missing billed quantity

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Approved contract price 18.40/unit; invoice price 20.10/unit and posted total 2,010.00; billed quantity absent. |
| APPLICABLE RULE | CORE R1 quantity gate. |
| EXPECTED AMOUNT | Unknown; null. |
| ACTUAL AMOUNT | Posted total 2,010.00 USD, not sufficient to establish its quantity composition. |
| CALCULATION | Unit diagnostic = 20.10 − 18.40 = 1.70/unit; total Δ = Q × 1.70 cannot be calculated. |
| RESULT | QUANTITY_MISSING; monetary finding null. |
| STATUS | Evaluation: NEEDS_REVIEW; no monetary CaseStatus created. |
| WHY | Dividing total by unit price to infer 100 units would hide discounts, fees or source omissions and violates the no-backsolving gate. |

### F17 — Conflicting contractual prices

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Two source-supported prices, 10.00 and 12.00, claim the same SKU/date scope with no established precedence; quantity 100; invoice 1,200.00. |
| APPLICABLE RULE | R1 approved-term/conflict gate. |
| EXPECTED AMOUNT | Unknown; possible 1,000.00 or 1,200.00 USD is not authoritative. |
| ACTUAL AMOUNT | 1,200.00 USD. |
| CALCULATION | Diagnostic alternatives Δ = 200.00 or 0.00; neither selected. |
| RESULT | AMBIGUOUS_CONTRACT; monetary finding null. |
| STATUS | Evaluation: NEEDS_REVIEW; no monetary CaseStatus created. |
| WHY | Source approval alone does not resolve contradictory contractual meaning. No newest-document or lowest-price heuristic is allowed. |

### F18 — Standalone credit note

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Separate document is a −500.00 credit note referencing an earlier invoice; approved cross-invoice/line allocation and reconciliation are unavailable. |
| APPLICABLE RULE | DEFERRED standalone/cross-invoice credit reconciliation; credit classification gate. |
| EXPECTED AMOUNT | Not established for a matched comparable charge; null. |
| ACTUAL AMOUNT | Signed source credit −500.00 USD; not an independently assessed charge. |
| CALCULATION | No A − E calculation or absolute-value conversion. Linked residual exposure cannot be assessed without allocation. |
| RESULT | UNSUPPORTED_RULE / CREDIT_ALLOCATION_UNRESOLVED; monetary finding null. |
| STATUS | Blocked evaluation; any affected existing finding requires `needs_review`. |
| WHY | A credit is neither fake negative leakage nor proof of recovered cash. A known relevant note cannot simply be ignored. |

### F19 — Allocated negative adjustment on the invoice

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Expected fixed fee 100.00 for one complete cycle; invoice charge 150.00 plus explicit −50.00 adjustment allocated to that fee; net 100.00. |
| APPLICABLE RULE | CORE R2 with approved within-invoice actual bridge. |
| EXPECTED AMOUNT | 100.00 USD. |
| ACTUAL AMOUNT | 100.00 USD net. |
| CALCULATION | A = 150.00 + (−50.00) = 100.00; Δ = 0.00. |
| RESULT | No positive leakage; adjustment used once. |
| STATUS | Evaluation: NO_OVERCHARGE; no CaseStatus created. |
| WHY | Preserve the signed adjustment rather than forcing negative quantity into InvoiceLineItem or claiming the gross 50.00 discrepancy. |

### F20 — Ambiguous contract match

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Invoice has no contract/PO reference; supplier has two plausible active agreements, prices 10.00 and 12.00; quantity 100; invoice 1,200.00. |
| APPLICABLE RULE | Matching hierarchy before R1. |
| EXPECTED AMOUNT | Unknown; no authoritative governing agreement. |
| ACTUAL AMOUNT | 1,200.00 USD. |
| CALCULATION | Choosing agreements gives E = 1,000.00 or 1,200.00 and Δ = 200.00 or 0.00; diagnostic alternatives only. |
| RESULT | AMBIGUOUS_MATCH; monetary finding null. |
| STATUS | Match: AMBIGUOUS; evaluation: NEEDS_REVIEW; no monetary CaseStatus created. |
| WHY | Same supplier/SKU and a plausible price cannot select a contract. Source-grounded association must resolve the choice. |

### F21 — Gross overcharge fully offset by allocated credit

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Contract 10.00/unit; quantity 100; billed 12.00/unit, gross 1,200.00; explicit same-line credit 200.00; reconciled net 1,000.00. |
| APPLICABLE RULE | CORE R1 and full net comparison; credit allocation approved. |
| EXPECTED AMOUNT | 1,000.00 USD. |
| ACTUAL AMOUNT | 1,000.00 USD net. |
| CALCULATION | E = 100 × 10; A = 100 × 12 − 200; Δ = 0.00. |
| RESULT | No positive leakage; gross unit variance 2.00/unit is informational. |
| STATUS | Evaluation: NO_OVERCHARGE; no CaseStatus created. |
| WHY | The credit addresses the same charge. Reporting 200.00 potential leakage would double count a correction already present in actual billing. |

### F22 — Explicitly excluded fee (OPTIONAL FUTURE)

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Approved governing clause expressly excludes handling charges; complete applicable exceptions/waivers reviewed with none permitting this charge; invoice handling fee 250.00. |
| APPLICABLE RULE | OPTIONAL FUTURE R5, CONTRACTUAL_CHARGE_MISMATCH_V1; hypothetical separately authorized exclusion profile, never core V1. |
| EXPECTED AMOUNT | 0.00 USD, supported by explicit exclusion. |
| ACTUAL AMOUNT | 250.00 USD. |
| CALCULATION | Δ = 250.00 − 0.00 = 250.00. |
| RESULT | Optional profile: potential leakage 250.00. Initial core: UNSUPPORTED_RULE, finding null. |
| STATUS | Optional profile: CaseStatus `detected`; initial core: blocked evaluation only. |
| WHY | Zero is a source-supported obligation here, unlike F08. The label is contractual excluded-fee discrepancy, not an independent legal conclusion. |

### F23 — Percentage surcharge above agreed amount (OPTIONAL FUTURE)

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Approved surcharge 2% on the named pre-tax base of 10,000.00, excluding handling/tax; invoice surcharge 300.00; no disputed conditions. |
| APPLICABLE RULE | OPTIONAL FUTURE R5, CONTRACTUAL_CHARGE_MISMATCH_V1; hypothetical separately authorized percentage-charge profile, never core V1. |
| EXPECTED AMOUNT | Surcharge 200.00 USD. |
| ACTUAL AMOUNT | Surcharge 300.00 USD. |
| CALCULATION | Efee = 10,000.00 × 0.02 = 200.00; Δfee = 300.00 − 200.00 = 100.00. |
| RESULT | Optional profile: potential leakage 100.00. Initial core: UNSUPPORTED_RULE, finding null. |
| STATUS | Optional profile: CaseStatus `detected`; initial core: blocked evaluation only. |
| WHY | Only the isolated surcharge component is compared; its base is not replaced with a subtotal including excluded fees or tax. |

### F24 — Tax is not a pre-tax overcharge

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Contract tax-exclusive price 100.00/unit; quantity 1; invoice expressly itemizes base 100.00, tax 15.00 and total 115.00. |
| APPLICABLE RULE | CORE R1 with tax-exclusive comparison gate. |
| EXPECTED AMOUNT | Pre-tax 100.00 USD. |
| ACTUAL AMOUNT | Comparable pre-tax 100.00 USD; total 115.00 is outside this comparison. |
| CALCULATION | Δ = 100.00 − 100.00 = 0.00; itemized tax 15.00 is excluded. |
| RESULT | No positive price leakage; no opinion on tax liability. |
| STATUS | Evaluation: NO_OVERCHARGE for the price scope; tax category unassessed. |
| WHY | Source breakdown establishes the comparable base without assuming or interpreting a tax rate. |

### F25 — Retroactive amendment not yet approved for applicability

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Master 10.00; amendment signed Aug 1 expressly effective July 1 at 12.00; July 15 service, quantity 100, invoice 13.00/unit; retroactive conditions/applicability unresolved. |
| APPLICABLE RULE | R1 with retroactivity/knowledge-cutoff gate under approved PD-05; this invoice’s retroactive-applicability review is unresolved. |
| EXPECTED AMOUNT | Unknown until applicability approval; neither 1,000.00 nor 1,200.00 selected. |
| ACTUAL AMOUNT | 1,300.00 USD. |
| CALCULATION | Blocked now. A later approved amended-price snapshot would yield E = 1,200.00 and Δ = 100.00; old-price scenario would yield 300.00. |
| RESULT | RETROACTIVE_APPLICABILITY_UNRESOLVED; monetary finding null now. |
| STATUS | Evaluation: NEEDS_REVIEW; no monetary CaseStatus created. |
| WHY | Explicit dates are evidence to review, not automatic legal priority. Later approval preserves the original knowledge snapshot and creates a new evaluation. |

### F26 — Material rounding ambiguity

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Overrides the general test rounding assumption: exact expected calculation 10.005; posted actual 10.01; currency quantum 0.01; applicable rounding mode not established. |
| APPLICABLE RULE | Core monetary comparison rounding gate; PD-06. |
| EXPECTED AMOUNT | Exact pre-settlement 10.005 USD known; authoritative settled E unknown. |
| ACTUAL AMOUNT | 10.01 USD. |
| CALCULATION | Half-up: E = 10.01, Δ = 0.00. Half-even: E = 10.00, Δ = 0.01. Alternatives only. |
| RESULT | ROUNDING_UNRESOLVED; monetary finding null. |
| STATUS | Evaluation: NEEDS_REVIEW; no monetary CaseStatus created. |
| WHY | Python’s default mode or a hidden tolerance must not decide whether a one-cent obligation exists. |

### F27 — Price and missing discount share one finding

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Quantity 100; contractual gross 10.00/unit and unconditional 10% reduction on that contractual gross; invoice 12.00/unit, zero discount, total 1,200.00. |
| APPLICABLE RULE | CORE R1 + R3 as one complete pricing bundle. |
| EXPECTED AMOUNT | 900.00 USD. |
| ACTUAL AMOUNT | 1,200.00 USD. |
| CALCULATION | E = 100 × 10 × 0.90 = 900; Δ = 1,200 − 900 = 300. Diagnostics: gross variance 200 + corrected-base discount 100. |
| RESULT | One potential-leakage finding of 300.00 USD; two violation labels, not two overlapping claims. |
| STATUS | One CaseStatus `detected`. |
| WHY | Using invoice-inflated base for the discount would produce 200 + 120 = 320, exceeding the actual expected-versus-billed discrepancy. |

### F28 — Conditional early-payment discount without payment evidence

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Base 10,000.00; 2% discount only for payment within ten days; invoice bills 10,000.00; actual payment date unknown. |
| APPLICABLE RULE | DEFERRED conditional-payment discount, not unconditional R3. |
| EXPECTED AMOUNT | Unknown: 9,800.00 if the condition is satisfied, otherwise 10,000.00. |
| ACTUAL AMOUNT | Billed 10,000.00 USD; payment is not inferred from this amount or due date. |
| CALCULATION | Conditional illustration: 10,000 × 0.98 = 9,800 and Δ = 200; absent condition evidence, no authoritative Δ. |
| RESULT | UNSUPPORTED_RULE / CONDITION_UNPROVEN; monetary finding null. |
| STATUS | Blocked evaluation; review may request payment evidence, but core remains unsupported. |
| WHY | A conditional entitlement must not be treated as an unconditional contractual discount. |

### F29 — Identified contract expired before service

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Exact contract reference and approved entities; price 10.00; validity ends June 30 inclusive; service July 15; quantity 100; invoice 1,100.00; reviewed packet establishes no applicable continuation. |
| APPLICABLE RULE | Identity/applicability gate before R1. |
| EXPECTED AMOUNT | Unknown for July service; expired price is not an applicable E. |
| ACTUAL AMOUNT | 1,100.00 USD. |
| CALCULATION | Do not compute 1,100 − 100 × 10 = 100 using an inapplicable term. |
| RESULT | NO_APPLICABLE_TERMS; monetary finding null. |
| STATUS | Identity association retained; NO MATCH to applicable terms; no monetary CaseStatus created. |
| WHY | Contract identity does not prove economic applicability. If renewal status were unknown instead, the outcome would be NEEDS_REVIEW. |

### F30 — Incompatible units

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Contract 10.00 USD/box; invoice 100 individual units at 2.00 USD/unit, total 200.00; box-to-unit conversion not evidenced. |
| APPLICABLE RULE | R1 unit-comparability gate. |
| EXPECTED AMOUNT | Unknown for 100 individual units. |
| ACTUAL AMOUNT | 200.00 USD. |
| CALCULATION | 100 × 10 is invalid because the quantity is units while the contractual denominator is boxes. |
| RESULT | UNIT_MISMATCH; monetary finding null. |
| STATUS | Evaluation: NEEDS_REVIEW; no monetary CaseStatus created. |
| WHY | Sharing a currency is insufficient. No assumed pack size or unit conversion is permitted. |

### F31 — Explicit minimum floor, mathematically clear but deferred

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Synthetic complete-period clause explicitly requires the greater of 1,000.00 and Q × 8.00, with no credit/condition uncertainty; Q = 80; invoice bills 1,000.00. |
| APPLICABLE RULE | DEFERRED minimum-commitment rule; mathematical illustration only. |
| EXPECTED AMOUNT | Hypothetical supported floor profile: max(1,000, 640) = 1,000.00 USD. Initial core: unassessed. |
| ACTUAL AMOUNT | 1,000.00 USD. |
| CALCULATION | Priced usage 80 × 8 = 640; explicit floor selects 1,000; hypothetical Δ = 0.00. |
| RESULT | Initial core: UNSUPPORTED_RULE, monetary finding null; no inferred 360.00 unit-price overcharge. |
| STATUS | Blocked evaluation until a separate minimum profile is authorized and supported. |
| WHY | The floor changes expected billing. A clear example does not authorize broader take-or-pay or true-up implementation. |

### F32 — Crossing amendment with explicit independent allocations

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Approved split: 400 units before July 1 at contractual 18.40; 600 from July 1 at 19.10; invoice bills both segments at 19.20, explicitly allocated 7,680.00 and 11,520.00. |
| APPLICABLE RULE | CORE R1 on two disjoint approved segment scopes. |
| EXPECTED AMOUNT | Old segment 7,360.00; new segment 11,460.00; total 18,820.00 USD. |
| ACTUAL AMOUNT | Old segment 7,680.00; new segment 11,520.00; total 19,200.00 USD. |
| CALCULATION | Old Δ = 400 × 0.80 = 320; new Δ = 600 × 0.10 = 60; disjoint total Δ = 380.00. |
| RESULT | Scoped potential leakage 320.00 and 60.00; reconciled non-overlapping total 380.00 USD. |
| STATUS | Each scoped finding CaseStatus `detected`; aggregate is a view, not a third duplicate finding. |
| WHY | Source allocation resolves the crossing interval. The findings are disjoint, independently supported and compatible; PD-07 permits their sum as a view and prohibits a third duplicate finding. |

### F33 — Discount applies to eligible SKU only

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Approved eligible SKU A base 2,000.00, required 10% discount; separately approved unaffected handling fee 300.00; invoice bills base 2,000.00 and fee 300.00, with zero discount. |
| APPLICABLE RULE | CORE R3 on SKU A; R2 confirms disjoint fee; bounded subset scope. |
| EXPECTED AMOUNT | SKU A net 1,800.00; fee 300.00; reconciled invoice net 2,100.00 USD. |
| ACTUAL AMOUNT | SKU A 2,000.00; fee 300.00; total 2,300.00 USD. |
| CALCULATION | Eligible D = 2,000 × 0.10 = 200; SKU Δ = 200; fee Δ = 0; total Δ = 200.00. |
| RESULT | One potential-leakage finding 200.00 USD for the eligible scope. |
| STATUS | SKU finding CaseStatus `detected`; fee assessment NO_OVERCHARGE. |
| WHY | Applying 10% to total 2,300 would invent a 30.00 discount on excluded handling. The invoice view must not duplicate the SKU finding. |

### F34 — Invoice inputs do not reconcile

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Contract 10.00/unit; invoice quantity 100 and unit price 10.00, but stated line amount 1,100.00; no disclosed fee, adjustment or rounding explanation. |
| APPLICABLE RULE | CORE R1 actual-billing reconciliation gate. |
| EXPECTED AMOUNT | Supported priced base 1,000.00 USD. |
| ACTUAL AMOUNT | Unresolved: quantity × price gives 1,000.00 while posted line says 1,100.00. |
| CALCULATION | Diagnostic residual = 1,100 − 100 × 10 = 100; unexplained residual is not an approved overcharge calculation. |
| RESULT | ACTUAL_BILLING_CONFLICT; monetary finding null. |
| STATUS | Evaluation: NEEDS_REVIEW; no monetary CaseStatus created. |
| WHY | The engine must not invent a fee, quantity or contractual interpretation to explain inconsistent actual inputs. |

### F35 — Quantity above forecast does not prove overbilling

| Field | Acceptance vector |
| --- | --- |
| SOURCE FACTS | Contract price 10.00/unit and nonbinding forecast 100 units; invoice bills 150 units at 10.00, total 1,500.00; accepted delivery quantity unavailable. |
| APPLICABLE RULE | CORE R1 for billed-unit price only; quantity-overbilling category DEFERRED. |
| EXPECTED AMOUNT | Price assessment: 150 × 10 = 1,500.00 USD; no expected delivered-quantity amount established. |
| ACTUAL AMOUNT | 1,500.00 USD. |
| CALCULATION | Price Δ = 1,500 − 1,500 = 0; (150 − forecast 100) × 10 = 500 is not an authoritative quantity claim. |
| RESULT | No positive price leakage; quantity coverage unassessed/UNSUPPORTED_RULE, finding null for that category. |
| STATUS | Price evaluation NO_OVERCHARGE; quantity evaluation blocked; no CaseStatus created. |
| WHY | Billed quantity permits a price comparison without verifying physical delivery. A forecast is not a payable maximum. |

## 23. Approved product policy register and remaining decisions

### 23.1 PD-01 through PD-07 — APPROVED PRODUCT POLICY

The product owner explicitly approved these policies in the final specification-pass instruction on 2 October 2026. The register supersedes the alternatives in draft 1.0. Approval establishes business policy; it neither approves facts from real documents nor implements a rule. Missing case-specific evidence still blocks calculation.

| ID | Status | Approved policy | Financial consequence preserved by the policy |
| --- | --- | --- | --- |
| PD-01 | APPROVED PRODUCT POLICY | Manual review approval for every calculation-driving fact and semantic mapping. Owner/admin approve/revoke; analysts review/propose/annotate/correct without final monetary authority; viewers read-only. High-confidence extraction supports separate preview only. Preserve provenance, meaning, actor, time, revisions and tenant ownership. | Confusing expected 18.40 with 20.10 for 43,647 units can change a 74,199.90 discrepancy to zero. Extraction confidence cannot authorize that choice. |
| PD-02 | APPROVED PRODUCT POLICY | Authoritative association only from approved explicit reference, explicit approved PO-to-contract link, or evidence-backed manual association. One master per invoice evaluation; multiple line scopes permitted within it. Candidate signals/scores never authorize or defeat explicit conflicts. Multiple masters or unsafe shared allocations block evaluation. | Q=100, contract prices 10 and 12, billed 1,200 yields 200 or zero depending on the governing agreement. Weak association cannot select either. |
| PD-03 | APPROVED PRODUCT POLICY | Exactly three core families: fixed unit-price overcharge; fixed recurring/fixed-fee overcharge; explicit unconditional percentage discount mismatch. Tier/charge profiles remain OPTIONAL FUTURE. Fixed-money, compound/conditional/cumulative discounts, proration, minima and other deferred categories remain outside core until separately approved. | At Q=6,000, tier methods yield 48,000 versus 54,000; a 2% surcharge on 10,000 versus 10,200 yields 200 versus 204. Neither family is enabled in V1 by a plausible formula or complete facts. |
| PD-04 | APPROVED PRODUCT POLICY | Mandatory bounded, versioned scope/period governing-packet attestation identifying master, amendments, schedules, exhibits/addenda, document identities/hashes, known gaps, reviewer and revision. Known relevant missing material blocks the affected calculation. Later evidence requires a new review/evaluation snapshot. | A missing amendment from price 10 to 12, Q=100, billed 1,200 can turn a supposed 200 overcharge into zero. Uploaded or fully extracted documents are not assumed exhaustive. |
| PD-05 | APPROVED PRODUCT POLICY | Establish contractual economic-date semantics first, then line date, line interval, applicable invoice interval, and invoice date only with express contractual support. Retroactive applicability requires explicit review; before approval block, after approval create a new reproducible snapshot. Price-changing periods require explicit quantity/amount allocations; no automatic daily proration. | July service, Q=100, billed 1,300: amended 12 gives 100 versus master 10 giving 300. June service billed at 12 under an applicable old price 10 gives 200; a convenient invoice date must not erase it. |
| PD-06 | APPROVED PRODUCT POLICY | Exact Decimal/source precision; no guessed mode, hidden epsilon/tolerance or engine materiality deletion. Material unresolved rounding blocks until an approved profile exists. An invariant result may proceed with documented plausible-method comparison and retained uncertainty. Later reporting filters do not change underlying findings. | Expected 10.005, actual 10.01 yields zero with half-up versus 0.01 with half-even; block. Exact aligned E=1,000 and A=1,200 stays Δ=200 across unresolved modes; allow with uncertainty. Ten thousand supported one-cent findings remain 100 in underlying data. |
| PD-07 | APPROVED PRODUCT POLICY | Evidence-backed credits/rebates/adjustments apply once only with unambiguous allocation to scope. Relevant unallocated reductions block. No cross-invoice credit reconciliation, cross-period netting, unrelated undercharge offsets or arbitrary invoice netting. Sum only compatible, independently supported, non-overlapping current findings as a view. | Gross overcharge 500 with directly allocated credit 300 leaves 200; no recovery claim. Separate +200 and −200 deviations retain 200 positive findings and a separate undercharge diagnostic; no automatic cancellation or duplicate aggregate finding. |

### 23.2 Remaining product decisions

**NO MATERIAL PRODUCT DECISIONS REMAIN FOR THE APPROVED PHASE 4 V1 CORE.**

No PRODUCT DECISION REQUIRED item blocks the approved core specification. Real-document approvals, missing evidence and unsupported scope still block individual evaluations; those are operational gates, not unresolved product policy. Future excluded profiles need separate approval when proposed, and do not delay this core.

The subsequently authorized technical implementation selects storage/promotion, APIs, concurrency controls and review interfaces as documented in [Phase 4 architecture](phase4-architecture.md). Existing single-amount/version fields cannot represent the approved pricing program; the implementation uses stable reviewed financial sources and immutable revisions. These technical choices do not reopen the approved financial policy.

## 24. Acceptance, handoff and stop boundary

PD-01 through PD-07 and the three-family V1 business scope are approved. Specification PR #4 is merged into main; the user explicitly authorized Phase 4 V1 implementation against `e1bdae347bfe6d9b8d7c9b92ec8efc3e723943a1`. Implementation is complete on the dedicated branch pending PR review, with validation recorded separately. The optional/deferred formulas do not authorize their implementation. Each real source’s semantic mappings and facts still need the operational review required by PD-01. No automatic merge or later-phase implementation is authorized.

Future acceptance must establish: unknowns cannot generate amounts; complete approved monetary inputs reproduce every CORE vector; OPTIONAL FUTURE/DEFERRED vectors always block in the approved V1 profile; matching/date boundaries and future mathematical tier illustrations remain distinct; currencies/units/tax bases cannot be mixed; credits and overlaps cannot be double counted; unrelated undercharges never offset findings; aggregates remain views; same inputs/policies return the same fingerprint/result; changed approvals retain historical snapshots; material rounding ambiguity blocks while demonstrably invariant results retain uncertainty; supported positive amounts are not deleted by materiality; tenants cannot cross-reference facts/evidence; and existing Phase 1–3 safeguards remain intact. New database-sensitive implementation, when separately authorized, requires full PostgreSQL CI rather than SQLite substitution.

Historical specification-only verification covered arithmetic, decision-table consistency, requested-topic coverage and a documentation-only Git diff; application tests were not rerun for that historical task. The previous 273 backend/46 frontend results remain historical Phase 3 validation. Authorized Phase 4 implementation validation now passes 386 backend and 62 frontend tests with PostgreSQL 17, migrations/schema drift, lint, formatting, TypeScript, production build, benchmark and secret scan; see [Phase 4 validation](phase4-validation.md) for exact checkpoint and CI evidence.

Final specification validation: all 35 vectors retain their source facts, expected/actual amounts and calculation rows from draft 1.0. All eight requested fields remain present. Exact Decimal recalculation passed 116 case-value checks plus 27 matrix/policy/rounding checks, including the five tier boundaries, both rounding-sensitive alternatives, line-versus-aggregate rounding and eight Decimal modes for the invariant example. The 13 matching rows, 14 effective-date rows, seven APPROVED PRODUCT POLICY records, null blocked outcomes and OPTIONAL FUTURE/DEFERRED exclusion from core were checked. This is documentation validation, not an implemented-engine regression-test claim.

HANDOFF.md now records the merged Phase 3/specification baseline, authorized Phase 4 implementation, validation evidence and implementation PR review as the next step. Financial policy, worked vectors, PD-01 through PD-07 and deferred-rule boundaries in this specification remain unchanged.

**CURRENT STOP:** report the completed Phase 4 V1 implementation and open its review PR against main. Do not merge automatically or begin Phase 5 Proof Engine, Phase 6 Recovery Ledger or other deferred profiles. Further phases and implementation merge require a new explicit instruction. The earlier specification-only stop boundary has been superseded by the user's implementation authorization.

## Reference basis

The core financial selection/control rules are approved product policy derived from the supplied decisions and scenarios. OPTIONAL FUTURE/DEFERRED formulas are documented mathematical illustrations only. None is a quotation of universal contract or tax law. Actual contractual applicability requires approved governing source facts.

- Project sources inspected: HANDOFF.md; `app/intelligence/schema.py` and Phase 3 architecture; `app/domain/types.py`; Money/ExactNumeric; Contract/ContractVersion/Invoice/InvoiceLineItem/LeakageCase models; LeakageRule and evidence/confidence protocols at the verified baseline.
- [Python 3.12 Decimal documentation](https://docs.python.org/3.12/library/decimal.html), consulted 2 October 2026: exact decimal representation, explicit context/rounding controls and signals. This supports the arithmetic mechanism, not selection of a contractual rounding mode.
- [ISO 4217 currency-code overview](https://www.iso.org/iso-4217-currency-codes.html) and [SIX currency standards maintenance](https://www.six-group.com/en/products-services/financial-information/market-reference-data/data-standards.html), consulted 2 October 2026: currency identifiers and currency-specific minor-unit metadata. Future implementation must pin the relevant metadata; no FX rate, tax rule or universal two-decimal convention is inferred.
