# Phase 5 — Leakage Proof Engine: business, product and domain specification

**Version:** 1.0, finalized 3 October 2026; approved policy unchanged. **Policy status:** APPROVED PHASE 5 PRODUCT SPECIFICATION; PD5-01 through PD5-14 approved by the user on 3 October 2026, Option A for each, with the PD5-14 clarification recorded below. **Implementation authorization:** explicitly authorized by the subsequent implementation instruction. **Implementation branch:** `phase5/leakage-proof-engine`. **Merge status:** specification PR #6 is merged; Phase 5 V1 implementation is on the review branch and must not be merged automatically. **Implementation starting main:** `f5e779b68cd8449ec94fabc50a34ca134c6a0f87`. Original specification baseline was `ecc0364cc7462d5257e210c26a97117d2d58eb5d`, completed Phase 4 V1. This document and its approved decision register remain authoritative Phase 5 product policy. See [implementation validation](phase5-validation.md) for actual enforcement, evidence and remaining operational limits. Phase 6 is not authorized and has not started.

[Phase 4 business specification](phase4-business-spec.md), PD-01 through PD-07, remains authoritative for financial truth. Its baseline SHA-256 is `1ee9eebf9ca81496f616c8bf55e64389341141762a501c3ec91fa654bb99fe09`. [Phase 4 architecture](phase4-architecture.md) and [validation](phase4-validation.md) describe the implemented foundation. Historical pre-merge/authorization wording describes its original checkpoint and does not override the subsequent explicit Phase 5 implementation authorization. Phase 6 remains unauthorized.

**SIMPLE ON THE SURFACE, RIGOROUS UNDERNEATH.** An executive must understand how much, why, compared to what, evidence completeness and review state within one summary. An authorized reviewer must be able to trace the same result through approved meanings to source evidence and reproduce its arithmetic independently.

## 1. Purpose, authority and approved V1 boundary

The Proof Engine answers: “For this exact historical evaluation, which approved meanings, source evidence, applicability decisions and calculation produced this conclusion, and what limitations remain?” It assembles an explanation of an existing Phase 4 result. It does not decide contractual correctness, select a different price, resolve a new amendment, calculate a new authoritative amount, or overwrite an evaluation.

Approved V1: internal tenant-authorized proof views; one canonical machine-readable manifest per proof content revision; controlled owner/admin JSON download; nonfinancial annotations; explicit historical/current context; three existing financial rule families and their combined bundle; and separate evidence packages for nonpositive and blocked assessments. External/vendor/public sharing, public share tokens, vendor accounts, supplier dispute communications, external delivery workflows, PDF generation/dependencies and aggregate proof/report persistence are out of scope. Section 22 records the approved choices; section 14 defines deferred PDF requirements for a separately authorized future release.

An independent reviewer may reproduce arithmetic using the recorded values, expression, rounding alternatives and versioned Phase 4 behavior. Such reproduction is a verification exercise, not a Phase 5 financial decision. Phase 5 must not invoke today's match, compile or evaluate operation to fill historical gaps. If a required binding is unavailable, report a proof gap. If stored records contradict each other, return a controlled integrity failure and require investigation; do not “repair” the amount.

| Invariant | Required product behavior |
| --- | --- |
| SOURCE EVIDENCE ≠ APPROVED FINANCIAL TRUTH | Show raw candidate, normalized candidate and reviewed meaning separately. Source visibility or confidence grants no authority. |
| APPROVED FINANCIAL TRUTH ≠ FINDING | Approved revisions are inputs; the immutable evaluation is the output. |
| FINDING ≠ PROOF | A proof explains a conclusion and its dependencies; generating one creates no new leakage finding. |
| PROOF ≠ LEGAL JUDGMENT | Completeness does not establish enforceability, wrongdoing, payment, recovery or legal liability. |
| CURRENT DATA ≠ HISTORICAL TRUTH | Historical proof reads pinned IDs and snapshots, never a latest extraction or latest approval as a substitute. |
| MISSING EVIDENCE ≠ ZERO | Gaps remain explicit; missing money is null, not zero or a cleared scope. |
| ABSENCE OF EVIDENCE ≠ PROHIBITION | Missing contractual text does not prove a fee was forbidden. |
| HIGH EXTRACTION CONFIDENCE ≠ APPROVED PROOF | No AI score or extraction confidence becomes a completeness/approval threshold. |
| NEW EVIDENCE DOES NOT REWRITE OLD PROOF | Material financial changes go through Phase 4 revisions and a new evaluation. |
| PROOF IS REPRODUCIBLE | Typed exact values, identities, source hashes, historical approvals, trace and limitations remain accessible to authorized reviewers. |

## 2. Actual architecture inspected and reuse decision

The following observations describe the merged Phase 4 code inspected for specification PR #6, before Phase 5 implementation. They are historical architecture observations, not current implementation-status claims. See [implementation validation](phase5-validation.md) for the Phase 5 branch's actual additions. No financial-behavior contradiction requiring a policy change was identified in this review.

| Existing asset | Observed behavior | Phase 5 attachment/reuse and limitation |
| --- | --- | --- |
| `Document` / private `ObjectStorage` | Tenant-owned ID, SHA-256, size and private key. Financially referenced metadata/content identity cannot be changed/deleted through database operations. Filenames can change. | Reference ID + pinned hash; filename is a presentation label. Storage is not a versioned immutable archive and database guards do not prevent an outside writer changing disk bytes. |
| `ExtractionRun` / `ExtractedField` | Versioned candidate identity, input hash, raw/normalized values, confidence, parser/extractor/schema versions and source dictionary. | Preserve exact historical lineage when present. Reruns neither replace approved facts nor become business identity. |
| `ReviewedFinancialSource` | Stable contract/invoice identity anchored to a Document, unique per tenant/document/kind. | Reuse the stable invoice/master IDs. Do not duplicate Contract/Invoice entities or use ExtractionRun as their identity. |
| `FinancialRevision` | Immutable kind/key/number/predecessor; actor/time/cutoff; typed reviewed payload; provenance; prepared/approved/revoked states and request identity. | Reuse exact revisions. Prepared/revoked guard inputs may explain a blocked result but must not be labeled approved monetary inputs. |
| `FinancialRevisionEvidence` | Normalized tenant-safe Document/run/field links plus frozen detail; composite FK isolation. | Reuse as evidence edges and compare with frozen evaluation provenance. The `supports` mappings are reviewed assertions, not automated legal interpretation. |
| `FinancialEvaluation` | Immutable numeric columns, outcome/reason, fingerprint and snapshot. Snapshot includes all fenced context, `calculation_driving_revision_ids`, billed scope, match outcome and calculation trace. | Natural proof anchor. Include the driving/guard subset and necessary source dependencies; do not export unrelated contextual reviews indiscriminately. |
| Monetary finding | A positive `FinancialEvaluation.potential` represents a Phase 4 finding. The engine does not populate legacy `LeakageCase`. | For current V1, `finding_id = evaluation_id` when outcome is POTENTIAL_LEAKAGE; otherwise finding_id is null. Do not manufacture a second case/finding ID. |
| `FinancialFindingDecision` | Append-only `confirmed`, `false_positive`, `needs_review`; predecessor checks use the last decision ID. Current API status may be overridden by derived staleness. | Read actual decision records separately from current/stale presentation. Preserve all actor/time/reason history; do not mistake an API `needs_review` overlay for a historical human decision. |
| Financial audit / migration 0004 | Trigger-generated journal, actor/time/role/reason/target; immutable journal; direct forged inserts rejected. Tenant-row serialization and membership share locks. | Reuse journal architecture and lock order. Later proof events require an explicit compatible extension of registered trigger origins; ordinary direct audit INSERT is not permitted. No second incompatible journal. |
| Pure financial engine | `reviewed-compiler/1`, `core-bundle/1`, `financial-snapshot/1`; exact 80-digit Decimal context; approved trace and alternatives. | Copy identifiers/trace. Rule families are `unit_price`, `fixed_fee`, `percentage_discount`; map them to existing R1/R2/R3 labels without minting replacement financial versions. |
| Historical calculation trace | Formula, expected raw amount, actual bridge, alternatives, invariance, precision, selected term economic dates; complete approved inputs are in snapshot. | Bind typed inputs to the recorded operation. Not every intermediate has its own trace row. Do not claim an unrecorded step was captured at evaluation time or invent a deployment digest. |
| Legacy `modules/evidence.py` | Protocol/drafts only; its `CalculationTrace.inputs` are all `Money`. No deployed Proof Engine. | Do not treat that protocol as the authoritative proof schema: quantities and percentages need distinct types. Later engineering may adapt it or add an explicit typed representation. |
| Existing financial API/UI | Protected historical evaluation detail, review/history/audit, source evidence, trace and finding decisions; server-only token proxy. | Extend conceptual drill-down later; existing routes are not proof-generation/export contracts. No route is created in this task. |

Phase 3 provides PDF page/line/extracted-text start/end where available; CSV row/column/header; XLSX sheet/cell/row/column. It has no PDF bounding boxes, OCR coordinates, visual table guarantee or original PDF-byte text offsets. Manual evidence has a reviewer-supplied location and citation. A quote field must not be described as machine-verified verbatim text solely because a reviewer entered it. Raw extracted source text and reviewer citation remain distinct.

The current original-download handler streams private bytes without rehashing them. Phase 4 commit fencing checks stored Document hashes against pinned provenance, rather than independently hashing storage bytes during each financial evaluation. Future Phase 5 proof-integrity verification therefore needs a bounded read of the actual source bytes against the historical hash. This adds proof integrity, not new financial calculation. Other debt: no explicit evaluation-successor relation, no proof persistence/rendering/export registry, no evaluation-time deployment digest, and bounded summary/source selectors. These must be addressed by later proof design, not silently assumed to exist.

## 3. Conceptual domain and identities

These concepts specify meaning, not a table-per-concept database plan.

| Concept | Identity and semantics |
| --- | --- |
| Source document | Tenant-owned Document UUID; private original content. |
| Source version/hash | Pinned lowercase SHA-256 of exact original bytes and known size/type. Different bytes require a different source/revision relationship; filename is not a version. |
| Extracted candidate | Exact run UUID/version + field UUID/path and raw/normalized machine meaning; optional for explicit manual source review. |
| Reviewed financial source | Stable contract or invoice UUID; creating a source is not financial approval. |
| Approved financial revision | Tenant/source/kind/key + revision UUID/number, actor/time, cutoff, typed meaning and predecessor. |
| Governing packet | Approved packet revision with one master, included role/document hashes, scopes, interval, attestation and known gaps. |
| Association | Exact approved association/reference revisions identifying why one master governs this invoice. |
| Financial evaluation | Immutable evaluation UUID, semantic fingerprint, scoped outputs, snapshot and behavior versions. |
| Financial finding | Positive scoped result of that evaluation; zero/negative/blocked assessments are not monetary findings. |
| Proof family | Stable logical identity `(tenant, evaluation_id, package_kind)`; never shared across tenants/evaluations. |
| Proof package/content revision | Immutable issued content, monotonically numbered within its proof family, unique package UUID, core manifest/fingerprint and issuance envelope. |
| Proof artifact | A rendering or exported byte object of a specified package revision; its own UUID, format/profile/version, creation metadata and byte SHA-256. Not a financial result. |
| Proof evidence item | Typed binding between one historical assertion/value and its pinned review/source/lineage/location. A reference may support several leaves; each binding remains explicit. |
| Proof calculation | Recorded Phase 4 expression, typed operand bindings, exact trace, rounding alternatives and unchanged outputs. |
| Proof manifest | Canonical machine-readable core + issuance envelope; section 9 defines hashing and required groups. |
| Proof status | Orthogonal evidence-completeness, financial currentness, replacement, review and access/integrity states; not a new CaseStatus. |
| Proof provenance | Directional chain input → revision → reviewed evidence → Document/hash and optional machine run/field. |
| Proof annotation | Separate nonfinancial actor/time/reason/text record, anchored to a package or evidence item; cannot patch core values. |
| Proof access/redaction state | Current server-authorized visibility and separately versioned disclosed presentation; never a modified internal truth. |
| Supersession relationship | Explicit relationship between packages/evaluations with documented scope and reason; not inference from latest timestamp. |

Approved `package_kind` mapping:

| Phase 4 outcome | Kind | Required headline |
| --- | --- | --- |
| POTENTIAL_LEAKAGE | MONETARY_FINDING_PROOF | “Potential leakage”, exact currency/amount, historical/current context |
| NO_OVERCHARGE | ASSESSED_COMPARISON_EVIDENCE | “No overcharge in this assessed scope”; discrepancy zero, potential null |
| UNDERCHARGE | ASSESSED_COMPARISON_EVIDENCE | “Informational undercharge”; signed negative discrepancy, potential null |
| NEEDS_REVIEW | BLOCKED_ASSESSMENT_EVIDENCE | “Unable to calculate / assessment blocked”; monetary comparison unknown |

Preserve the actual stored outcome. Historical specification labels do not authorize changing an engine outcome. No-overcharge is scoped, not a statement that an entire invoice/payment population is correct. A blocked package can explain recorded source amounts in different currencies without treating them as a comparable actual/expected financial result.

## 4. Required package content and input-to-evidence graph

Each package must contain the following groups, or explicit gap/not-applicable entries. Missing keys cannot silently mean absence, zero or not-applicable.

| Group | Required content |
| --- | --- |
| Identity | Tenant, package/family/revision IDs; evaluation and nullable finding ID; stable invoice source and scope key/members; package kind; evaluation time; issuance time/actor; financial rule/compiler/snapshot IDs and proof schema/assembly IDs. |
| Executive summary | Unchanged potential/currency/outcome, short plain-language reason, expected and comparable actual when established, quantity/base where applicable, evidence-completeness label, finding decision, financial currentness and limitations. |
| Contractual basis | Master/source ID; packet revision and role/document hashes; selected term keys/revisions; applicable amendments, replacement edges, scope/parties/unit/currency/tax basis, interval, source-backed date selector and rounding profile. |
| Actual billing | Pinned invoice/billing revision and scope/members; billed price/quantity, gross/applied discount/posted amount; explicitly allocated signed credits; invoice/service/event dates and complete-cycle/base facts when applicable. |
| Match/applicability | Pinned association and relevant reference revisions/method/rationale; recorded match outcome; selected economic dates; explicit term supersession and approved retroactive applicability. Identity and economic applicability are separate assertions. |
| Calculation | Recorded formula/trace, typed bindings, exact raw/rounded values, profile/alternatives, expected, actual, discrepancy, potential, credit bridge and one combined bundle where applicable. No overlapping additive money claims. |
| Provenance | Revision identities, historical approval state/actor/time/reason/cutoff, original uncertainty and resolution, source hashes, run/field/version/location data, reviewed values versus machine values, evaluation fingerprint and relevant review request identities. |
| Limitations | Bounded packet/scope/knowledge context, retained uncertainty, missing proof material, recorded financial blocker, source-location precision, current availability/integrity, human review and currentness/replacement labels. |
| Lifecycle/audit | Issuance context plus separately sourced decision/annotation/review/replacement/export events with actor/time/reason. Current overlays carry an explicit observed-at timestamp and are not frozen financial inputs. |

For every calculation-driving quantity, monetary amount, unit price, percentage, currency/unit, scope and applicability selector, create an explicit binding with: semantic role/type; unchanged value; pointer into the frozen evaluation/revision; revision UUID and reviewed state; evidence-item references; source Document/hash; applicable support pointers; actor/time/cutoff and uncertainty. Keep zero and null distinct. An empty approved credit list is a reviewed scope assertion, not a guess from an empty invoice cell.

Include all IDs in `calculation_driving_revision_ids`, distinguishing selected financial operands, applicability/identity/coverage inputs and guard/overlap/allocation inputs. That existing field also names guards; it does not mean every entry was an approved monetary operand. Selected term keys come from the recorded calculation's `economic_dates` and frozen typed values. If a key/binding is ambiguous or absent, record `PROOF_BINDING_MISSING`; do not choose today's applicable term. Preserve parent/sibling allocation and credit identities needed to explain non-overlap.

Unrelated fenced context is not a proof operand. Do not present every invoice line or every contract candidate as supporting the finding. A full frozen-snapshot digest may link the excluded context without exporting its contents. For blocked results, preserve the recorded first reason and available supporting guards/alternatives; do not invent a claim that the engine collected every possible blocker. Further missing-proof checks are explicitly Phase 5 evidence gaps, not new Phase 4 financial reasons.

## 5. Deterministic completeness and separate status axes

Approved issued completeness has two values: COMPLETE and INCOMPLETE. ABSENT means no package exists, and generation failure means no trusted package was issued; neither is a zero amount. “Needs review” is a human proof-review state or a Phase 4 outcome, not an ambiguous third completeness bucket. Under approved PD5-01/03, deterministic C01–C10 checks determine technical completeness automatically; optional owner/admin proof review is separate and audited. No numerical confidence score is used.

| Check | COMPLETE monetary/nonpositive evidence | COMPLETE blocked assessment evidence |
| --- | --- | --- |
| C01 Identity/isolation | Correct tenant, evaluation, scope and kind; finding ID only if positive | Same; no invented finding ID |
| C02 Frozen result | Outputs/outcome/fingerprint/trace copied exactly; no new financial result | Recorded null outputs and blocker copied exactly; source diagnostics labeled separately |
| C03 Historical dependencies | Every selected/guard revision is uniquely bound to snapshot and exact historical record | Every assertion used to explain the recorded blocker is bound; missing financial inputs explicitly described as missing |
| C04 Authority/provenance | Monetary/applicability inputs approved as evaluated, approval actor/time/cutoff/reason and source mappings available | Review states shown accurately, including unapproved/revoked guards; completion does not approve them |
| C05 Governing/matching basis | Recorded packet/master/association/selected dates/precedence are traceable | Existing basis and recorded uncertainty/missing attestation/association are explained without a fabricated resolution |
| C06 Exact reconstruction | Typed operands, expression, required recorded trace/profile and all material alternatives available | Recorded diagnostic alternatives may be included; no authoritative subtraction or guessed allocation |
| C07 Source integrity | Every cited original with an expected hash has been bounded-read and verified against that hash at issuance; reference metadata/provenance agree | Verify the existing sources supporting the blocking explanation. A known missing schedule has no fabricated ID/hash to verify |
| C08 Material uncertainty | All retained financial uncertainty/invariance and scope limitations disclosed | Recorded financial uncertainties/gaps are the subject of the package, not missing proof of a monetary claim |
| C09 Binding integrity | Snapshot, normalized revision evidence and source references agree; no cross-tenant/contradictory identity or hash | Same |
| C10 Issuance integrity | Manifest validates under pinned proof schema/assembly; deterministic hash and transactional generation audit exist | Same |

COMPLETE means these technical evidence/reconstruction conditions passed at issuance, not that a human agreed with the finding, all possible contracts were discovered, or source citations constitute legal certification. Current byte availability must also be visible. A blocked assessment may be COMPLETE as an explanation while its financial amount remains unknown. It must never show “complete monetary proof”.

| Missing detail | Effect |
| --- | --- |
| Financial source hash, driving revision, approval identity/time or material support binding | INCOMPLETE, or controlled failure if contradictory |
| Original file temporarily missing but pinned review/quote still available | INCOMPLETE with `PROOF_SOURCE_UNAVAILABLE`; preserve the recorded amount and expected hash |
| Source bytes conflict with expected hash | Integrity failure; never COMPLETE or substituted bytes |
| Exact PDF bounding box/OCR coordinate unavailable | Nonblocking limitation; neither exists in Phase 3 |
| Page/cell precision absent but exact Document/hash, reviewer citation and approved support mapping exist | Nonblocking location limitation if no binding ambiguity; label document-level/manual location honestly |
| Filename/title/display actor name/amendment number absent | Nonblocking when immutable identity, actor UUID, source scope/precedence and cited meaning are established |
| ExtractionRun/field absent on explicitly manual source review | Nonblocking; display manual review and citation, not invented extraction lineage |
| Known absent governing material caused Phase 4 blocker | Does not prevent complete explanation of that blocker if the approved gap assertion and available evidence are traceable |

Current status axes, outside immutable core:

| Axis | Values / rule |
| --- | --- |
| Financial currentness | CURRENT / STALE / UNKNOWN, obtained from Phase 4 scoped semantics as of an explicit read time. Cannot be inferred from age/filename alone. UNKNOWN if the check cannot run safely. |
| Replacement | NONE / EXPLICIT_SUCCESSOR. Record successor IDs/reason and whether the relation is proof-content revision or a new financial evaluation. No automatic newest-wins relation. |
| Finding decision | Existing detected/confirmed/false_positive/needs_review history. Current API staleness overlay and actual human decision are distinguishable. Nonfindings have no finding decision. |
| Proof review | UNREVIEWED / REVIEWED / NEEDS_REVIEW, with owner/admin actor/time/reason. REVIEWED is not financial confirmation or a replacement for C01–C10. |
| Evidence availability/integrity | VERIFIED_AT_ISSUE plus current AVAILABLE_VERIFIED / UNAVAILABLE / MISMATCH / UNCHECKED, observed-at time and gaps. A current mismatch quarantines the changed bytes. |
| Access | Authorized internal view, permitted download, or denied; redaction is a separate disclosure view, not a completeness mutation. |

Executive labels must combine relevant axes: “Historical evidence complete at issue; inputs now stale”; “Evidence complete; finding dismissed”; or “Assessment explanation complete; monetary amount unknown”. Never remove a stale/dismissed/unavailable badge merely because the core is COMPLETE.

## 6. Historical lifecycle and immutability

| Event | Historical package | Current interpretation / required action |
| --- | --- | --- |
| Approval correction/revocation or material prepared review | Original revision/value/output remains | Phase 4 determines staleness. Request new approved inputs/evaluation where required; never substitute latest review into old proof |
| Governing packet revision/new approved amendment | Original packet/hash/date choice retained | Material scope changes require new Phase 4 evaluation. Disjoint revisions must not reopen an unrelated proof/finding |
| New extraction run | Original raw/candidate lineage retained | Rerun alone does not revoke approval or revise proof |
| Filename/display-name change | Identity/hash/core retained | Cosmetic label may vary in a new presentation, explicitly presentation metadata |
| Source bytes missing/mismatched | Original manifest/hash/issued completeness retained | Current availability/integrity overlay warns; changed bytes cannot be substituted or downloaded as verified historical evidence |
| Finding dismissed/confirmed/needs-review | Core and amount retained | Append existing Phase 4 decision actor/time/reason; no rewriting evidence to fit the decision |
| Formatting change | Core/fingerprint retained | New rendering artifact/version, not a new financial assessment |
| Proof-only collection/schema correction | Old package/content hash retained | Explicit new proof content revision, with reason and predecessor; permitted only when no financial input/output is changed |
| New material financial result | Old evaluation and proof retained | New evaluation UUID/fingerprint, separate proof family and optional explicit replacement relationship |

A historical proof can remain COMPLETE at issue while its evaluation is now STALE or its finding dismissed. “Current proof” means proof of a Phase 4-current evaluation, not the last document exported. A proof family can also have a newer content revision for the same unchanged evaluation; that is a proof revision, not financial reevaluation. If a missing original is restored with exactly the original hash, a new proof content revision can demonstrate completeness without creating financial truth. The old incomplete package remains immutable. A different hash or revised approved meaning requires Phase 4 revision/evaluation, never this exception.

Financial replacement must be explicit: same tenant and stable invoice/scope relationship, predecessor/successor evaluation IDs, affected revisions, source-backed correction/reason and owner/admin recorded relationship. A changed scope/period/currency cannot be silently declared the same assessed money; a supported relation must explain its boundary. Relationship acknowledgment cannot override Phase 4 currentness/aggregation or change an amount. Cycles, cross-tenant links and replacement by a non-equivalent scope fail. Multiple possible successors remain unresolved, not arbitrarily “latest”. Existing Phase 4 has no such stored predecessor link; approved PD5-10 requires this explicit relationship in later authorized Phase 5 implementation.

## 7. Separate version dimensions

| Version | Meaning / change consequence |
| --- | --- |
| Financial rule/compiler/program/snapshot | Copy exact evaluation identifiers. Material behavior/input changes require Phase 4 evaluation; no Phase 5 upgrade substitutes current code |
| Financial evaluation identity | UUID + semantic fingerprint of one immutable result; not an incrementing proof-format number |
| Evidence revision | Exact approved revision/run/source hash, unchanged in old packages |
| Proof schema version | Meaning/validation of manifest fields; breaking change requires explicit new proof content revision/mapping |
| Proof assembly version | Deterministic collector/binding/completeness/canonicalization behavior, immutable once released |
| Proof content revision | New manifest content for the same evaluation, explicit predecessor/reason; no financial edit |
| Rendering/export version | Layout, labels, locale, page rules and artifact format; can change without altering core |
| Disclosure/redaction policy version | What was withheld, why and by whom; creates a separate view/artifact, never alters canonical proof |
| Operational safety profile version | Engineering size/work/concurrency/rate defaults and measured tuning under section 16; no change to financial calculations, completeness checks or historical proof content |

Specified V1 identifiers are `proof-manifest/1`, `proof-assembly/1`, `proof-disclosure/1` and the initial operational profile `proof-operations/1`; they are specification identifiers, not released code. Rerendering the same core produces the same manifest fingerprint. An assembly bug fix cannot silently change a published version's content. No cosmetic revision may contain a corrected price, quantity, date selector, source hash, discount/credit treatment or monetary output. Operational tuning alone does not revise a proof's financial/evidence core or promote incomplete evidence to complete.

## 8. Evidence locations, citations and typed calculation representation

An evidence item records: item identity, assertion/operand role, revision/support pointers, Document UUID/hash/type, available exact location dictionary, location kind/precision, reviewer citation, original candidate/source text where captured, manual versus extracted origin, run/field/path/version when present, approval metadata, cutoff, uncertainty and whether its source bytes were verified at issue.

| Location kind | Permitted representation | Must not claim |
| --- | --- | --- |
| PDF extracted text | 1-based page/line; start/end in extracted page text; recorded line/table row/column where available | Bounding box, visual clause highlighting, PDF byte offset or OCR coordinate |
| CSV | 1-based row/column/header and raw cell | Workbook cell or legal section inferred from row number |
| XLSX | Sheet, cell, 1-based row/column and raw cell | Formula execution or cached formula as approved evidence |
| Manual citation | Original reviewer location/quote and support mapping; document-level if no finer precision | Machine-located/verbatim-verified citation merely because it was typed |
| Structured pointer | Exact pointer into immutable reviewed payload/snapshot; escape `~` as `~0` and `/` as `~1` for new proof pointers | A pointer into today's mutable response as historical source authority |

Preserve existing source/support dictionaries verbatim alongside the normalized proof locator. Do not silently rewrite legacy locations or invent missing page/section numbers. A repeated quote or coarse locator with an unresolved binding is a proof gap; Phase 5 cannot solve the legal meaning. An authorized reviewer may inspect the original, but a new interpretation goes through Phase 4.

| Type | Required value metadata |
| --- | --- |
| Monetary amount | Decimal string + exact currency + comparable tax/scope role |
| Unit price | Decimal string + currency + denominator unit |
| Quantity | Decimal string + compatible unit; no money wrapper |
| Percentage | Decimal string representing percent (8 means 8%), approved eligibility/base/unconditional meaning |
| Date/interval | Date-only strings and approved start-inclusive/end-exclusive semantics; separate economic and knowledge times |
| Identity/boolean/null | Original namespace/value and meaning; do not collapse unknown, false, zero, empty or explicit non-applicability |

All financial strings are copied in ordinary decimal notation without conversion through binary float. Approved inputs retain their recorded scale; database output serialization retains six places; exact intermediate trace strings retain their original precision. `18.40`, `20.10`, `43647`, recorded expected `803104.800000`, actual `877304.700000` and potential `74199.900000` remain distinct typed fields. Human display may show `74,199.90 USD` or a clearly abbreviated `74.2K USD`, but exact detail/export must remain available. Display rounding never changes authority or hides a one-cent finding.

Copy the recorded expression and approved input bindings. Mark any unrecorded intermediate as not recorded; do not fabricate an evaluation-time trace. The F02 per-unit difference `1.70` illustrates independent reconstruction, not a claim that Phase 4 persisted that separate trace operand. Alternatives from PD-06 remain alternatives: when no unique comparable E/A was established but discrepancy is invariant, show those alternatives and the invariant result, not a guessed E/A or mode. Reconstruction instructions identify the recorded arithmetic precision, quantum, mode/set, stage, metadata version, sequence, actual bridge and allocated credits. No independent rounding of discrepancy replaces Phase 4 settlement.

## 9. Canonical manifest, fingerprints and trust

The machine-readable manifest has two explicit parts: immutable `core` and immutable issuance `envelope`. Current finding/review/availability overlays are separate read data, not added retroactively to either part. Artifact disclosure context can snapshot those overlays as of export time, explicitly separate from the financial evidence state.

| Core group | Required fields / content |
| --- | --- |
| `schema`, `assembly` | Proof schema/collector/canonical profile versions and completeness-requirement version |
| `identity` | Tenant, evaluation ID/fingerprint, nullable finding ID, package kind, invoice source, scope/members |
| `financial` | Copied outcome/reason/explanation/currency and unchanged expected/actual/discrepancy/potential; evaluation timestamp and evaluation actor UUID |
| `behavior` | Exact financial snapshot/compiler/rule bundle IDs; recorded selected families and trace context |
| `authority` | Driving/guard revision IDs, reviewed states/values, stable keys/numbers, approval actor/time/cutoff/reason/uncertainty, normalized source/evidence bindings and relevant immutable audit references |
| `governing`, `billing`, `matching` | Packet/association/references, scope/applicability/term relationships, complete base/credits/tax and overlap/allocation evidence |
| `calculation` | Original recorded trace plus typed bindings; no synthesized monetary conclusion |
| `sources` | Pinned Document/hash/size where known; available lineage/locations/citations; byte-verification result at issue; no storage key or public download URL |
| `completeness`, `limitations` | Issued COMPLETE/INCOMPLETE, named C01–C10 results/gaps and nonblocking limitations; recorded financial blocker distinguished from proof gaps |
| `evaluation_snapshot_digest` | SHA-256 of canonical exact frozen snapshot under an explicit digest profile; not a replacement for the existing financial semantic fingerprint |

Envelope: package/family UUIDs, content revision/predecessor/reason, creation actor/time, verified-read observation times, request identity and audit-event identity, and core `manifest_fingerprint`. Package identifiers/timestamps are returned from the first successful persisted issuance on retry. No credentials, sessions, emails, bank details, storage keys or unrelated full documents are default manifest fields. Necessary source citations/approved party identity can themselves be sensitive and stay tenant-private; section 13 controls their disclosure.

Approved canonical profile (PD5-11): UTF-8 JSON without BOM/trailing newline/insignificant whitespace; object keys sorted by Unicode scalar value; no Unicode normalization of source strings; required explicit keys/nulls; JSON numeric tokens are finite base-10 integers for schema-declared counts/indices, without plus signs/leading zeroes, and booleans are literal `true`/`false`; decimal/date/timestamp/UUID/hash data are strings. No binary float or exponent-form financial number is permitted. JSON string escaping: double quote uses `\"`, backslash uses `\\`, every U+0000–U+001F control uses lowercase-hex `\u00xx` rather than short escapes; slash and other valid Unicode, including U+2028/U+2029, are emitted unchanged as UTF-8. Reject duplicate keys, invalid surrogate data and nonfinite/unsupported numeric values. UUIDs/hashes in new identity fields use lowercase standard forms; captured source identifiers/text remain unmodified. New timestamp fields use UTC with six fractional digits and `Z`, while original timestamp text is retained where precision matters; no date becomes an invented timestamp.

Set arrays are sorted by defined identity: revisions by UUID, source references by `(document_id, hash)`, evidence bindings by revision/pointer/evidence identity, gaps by `(code, binding_id)`. Preserve ordered arithmetic operations, component stages, source excerpt text and approved precedence sequences. Currency/unit and null/zero distinctions survive canonicalization. Invariance alternatives are ordered by recorded mode identity without changing their values. Approved decimal strings retain scale in this proof-content hash; proof hashing does not redefine Phase 4's financial fingerprint algorithm.

Evidence/binding IDs inside core must be stable across assembly retries: reuse historical evidence identity where available; otherwise derive an ID by SHA-256 of the domain prefix `FLA-PROOF-BINDING/1` followed by one LF and the canonical tuple `[revision_id, input_pointer, document_id, source_hash, run_id_or_null, field_id_or_null, support_pointer, recorded_location_or_null]`. Conflicting content for one binding identity is an integrity failure. Fresh issuance/random UUIDs belong in envelope/artifacts, never these core identities. Named check IDs and gap ordering are likewise deterministic.

The `evaluation_snapshot_digest` profile is `evaluation-snapshot-digest/1`: SHA-256 of UTF-8 `FLA-EVALUATION-SNAPSHOT/1` followed by one LF and canonical JSON of the entire stored snapshot, preserving every original string/value and array order. It does not normalize historical timestamps/Decimals, sort snapshot arrays as proof sets, or remove contextual entries. Unsupported historical value types fail with a version/integrity reason rather than an approximate digest. This separate digest binds context not disclosed in the minimal core, without exporting it.

`manifest_fingerprint = SHA256(UTF8("FLA-PROOF-MANIFEST/1\n") || canonical_JSON(core))`, lowercase 64-hex. The fingerprint field itself and envelope are excluded. Evaluation/approval/cutoff timestamps and their actors inside core are included; proof-request time, random package/artifact UUIDs, filenames, locale/layout, signed access URLs, current decisions, annotations and redaction/rendering details are excluded. This separation prevents clock/format/request changes creating duplicate semantic proof.

The artifact checksum is separate: SHA-256 of exact complete exported bytes, including its envelope and disclosure context. It verifies that export, not financial meaning. Source hashes verify original bytes, not contract authenticity. Canonical fingerprint verifies content against a trusted stored fingerprint; an attacker can rehash a modified file, so a self-contained unsigned checksum is not issuer authentication. A reviewer compares it with the authorized application/audit record. No digital legal certification, trusted timestamp authority, blockchain or distributed ledger is claimed in V1.

Verification must distinguish: manifest-schema validity; core fingerprint matches trusted registry; captured revision/evaluation/source identity matches immutable records; original bytes match expected hashes; and availability/currentness as of verification time. Do not claim all those checks from one green checksum. Exported JSON must contain the profile/version and enough disclosed immutable core to recompute its own core fingerprint; redacted exports have different verification limits under section 13.

## 10. Rule-specific proof requirements and nonmonetary assessments

| Assessment | Additional required bindings and explanation |
| --- | --- |
| R1 fixed unit price | Selected contracted price revision; reconciled billed price/quantity/posted basis; currency and denominator unit; selected economic date and complete packet; pre-tax compatibility; approved discount/credit absence or allocations; expected raw/settled amount, actual bridge and unchanged signed discrepancy. Billed quantity does not prove delivered quantity. |
| R2 fixed fee | Selected fee revision; exactly one approved complete contractual cycle/event and its identity/date/scope; comparable billed fee/posted amount; allocated reductions; complete-cycle evidence and lack of inferred proration. A word “monthly” is not evidence of a calendar month or daily denominator. |
| R3 unconditional percentage | Percentage revision and explicit unconditional meaning; approved contractual base and eligibility; governing-source citation for contractual base; complete included/excluded components; actual applied discount and reconciled posted amount; exact percentage/rounding trace. No tax, unrelated fee or invoice-inflated base may silently enter. |
| Combined R1/R2 + R3 | One evaluation, one positive result and one package family; both source-backed labels explain one expected post-discount reality versus one actual comparable reality. Diagnostics are nonadditive unless explicitly part of the recorded comparison. No second price or discount claim is created. |
| NO_OVERCHARGE | Same applicable proof requirements as its recorded family; exact zero discrepancy, potential null; scoped “No overcharge” conclusion only. |
| UNDERCHARGE | Same bindings; signed negative discrepancy and informational language; potential null, no buyer claim or negative leakage; never offset another package. |
| NEEDS_REVIEW | Distinct BLOCKED_ASSESSMENT_EVIDENCE, recorded blocker and available historical inputs/source facts; financial amounts remain as stored null. Known source amounts/alternatives are diagnostics in their own currency/basis, not asserted E/A or a potential amount. |

For rounding-sensitive blocked results, preserve all recorded alternatives with labels such as “Diagnostic under HALF_UP” and “Diagnostic under HALF_EVEN”. No executive monetary headline is produced from either alternative. For unsupported rule families, explain the recorded unsupported scope; do not supply a tier/fee/rebate proof calculator or elevate future illustrative amounts to findings.

## 11. Atomic generation, idempotency and safe failures

Generation is a specified future business command, not an implemented API. Required request meaning: authenticated actor/tenant; exact evaluation UUID and expected stored fingerprint; explicit CURRENT or HISTORICAL mode; supported proof schema/assembly profile; UUID idempotency key. No client-supplied amount, source hash, role, arbitrary template, external URL or replacement approval can override server-pinned truth.

1. Authorize current membership and permitted generation role, then acquire the organization lock and membership share lock in Phase 4 order. Locate the evaluation within that tenant. Unknown/inaccessible IDs return the same controlled not-found result.
2. Pin the immutable evaluation, numeric columns, exact snapshot/digest, all driving/guard revisions, normalized evidence and packet/source hashes by historical IDs. Check duplicates, ownership, snapshot-to-record agreement and explicit source lineage. Do not read latest revisions to populate the core.
3. In CURRENT mode, require Phase 4's scoped currentness check to agree with this evaluation while holding the tenant fence; a stale request returns `PROOF_STALE_INPUT`. HISTORICAL is explicitly permitted for stale/dismissed evaluations and must be labeled accordingly. It never quietly substitutes a current evaluation. Current decisions/replacement context are separately observed under the same fence.
4. Resolve each source through private server-controlled storage. Read/hash within configured byte/time limits. Use an immutable bounded capture or a storage version that reproduces exactly the pinned hash; never assemble from one read and attach unverified bytes from a later read. No new extraction or interpretation is run to fill a gap. Record missing evidence as gaps; identity/hash contradiction aborts trusted generation.
5. Assemble the deterministic core, run C01–C10, compute its fingerprint and reread the pinned record/hash bindings at commit. Retain locks through commit. If an actual pinned dependency changed or cannot be verified, roll back/abort or return a safe stale/integrity outcome; no mixed package or partial trusted monetary proof is issued.
6. Return the existing `(tenant, proof family, schema, assembly, core fingerprint)` content revision if present. Otherwise insert the immutable package/content revision and trusted audit event in one transaction with uniqueness enforced. Failure rolls back both. The first successful issuance envelope remains the envelope returned on retries.

These semantics preserve evaluation amount from revision 5 with revision-5 source/approval metadata, never revision-6 source and revision-4 approvals. Concurrent approval/revocation/packet revision commits before generation, making CURRENT mode stale, or waits until issuance commits. HISTORICAL mode always uses original pinned meaning. Finding-decision/current-context changes cannot be blended into an old core. Concurrent same-scope generation with the same or different request keys returns one canonical content revision and one `proof.generated` event.

PostgreSQL locks do not make external disk writers transactional. Generation's verified immutable capture establishes which bytes were observed; source availability is not guaranteed forever. An adapter unable to supply a consistent hash-bound capture must fail safely. Subsequent source presentation/download must recheck the bytes it actually serves. Privileged filesystem/schema interference is outside application-write guarantees and must be reported as source integrity loss, not concealed by database metadata.

| Request/event | Identity effect |
| --- | --- |
| Same evaluation/profile/available proof content, repeated or concurrent request | Existing package, original issuance envelope; no duplicate finding/audit creation |
| Same UUID key with different actor, target or command body | Idempotency conflict; no side effect |
| Same package, different layout/locale/generation date | New or reused rendering artifact, same core fingerprint |
| New annotation/evidence-request note | Separate annotation identity/audit; no core change |
| Newly restored original with identical hash removes a previously issued proof gap | Explicit new proof content revision if needed, same evaluation; reason/predecessor retained |
| Later loss of a source after a COMPLETE package exists | Availability overlay; ordinary regenerate returns the original package plus warning, not unlimited incomplete copies |
| Approved material financial input changes | New Phase 4 evaluation/fingerprint; separate proof family, optional explicit replacement link |

Conceptual error vocabulary distinguishes financial reason codes from proof failures:

| Code | Meaning / user-facing behavior |
| --- | --- |
| PROOF_NOT_FOUND | Missing/inaccessible tenant-scoped object; generic not found, no enumeration details |
| PROOF_FORBIDDEN | Current role cannot perform this action; no mutation/download |
| PROOF_STALE_INPUT | Current-mode financial/context token changed; reload or explicitly request historical evidence |
| PROOF_BINDING_MISSING | Required historical operand/revision/evidence mapping unavailable; INCOMPLETE with exact gap |
| PROOF_SOURCE_UNAVAILABLE | Original unavailable; retain expected hash and source identity; INCOMPLETE/availability warning |
| PROOF_SOURCE_INTEGRITY | Observed bytes/hash/identity conflict; trusted generation fails and changed bytes are quarantined |
| PROOF_RECORD_INTEGRITY | Contradictory frozen result/revision/provenance/manifest; no automatic repair or financial recomputation |
| PROOF_VERSION_UNSUPPORTED | Schema/assembly/snapshot cannot be safely mapped; no “closest” version fallback |
| PROOF_LIMIT_EXCEEDED | Bound reached; no silent truncation, zero amount or misleading COMPLETE label |
| PROOF_IDEMPOTENCY_CONFLICT | Reused request key with another meaning; reject |
| PROOF_DISCLOSURE_INCOMPLETE | Redaction removes independent-reconstruction content; disclosed view is explicitly limited |

Failure messages omit stack traces, filesystem/storage keys, other-tenant IDs and source text. A failed generation is not a finding dismissal or a changed financial amount. A proof gap requests evidence/review; any corrected financial meaning remains a Phase 4 action.

## 12. Roles, human review and annotations

Permissions below are approved under PD5-03/04/09. Current membership, server-side tenant scope and role checks apply to every action, including retrieving previously generated artifacts.

| Action | Owner/Admin | Analyst | Viewer |
| --- | --- | --- | --- |
| View existing authorized package/core/annotations/history/source | Yes | Yes | Yes; no mutation |
| Request deterministic proof generation from an existing evaluation | Yes | Yes; grants no financial authority | No; show package absent/request-review message |
| Add source-bound nonfinancial annotation or evidence-request note | Yes | Yes | No |
| Record final proof review / acknowledge explicit replacement | Yes | Prepare proposal only | No |
| Correct financial fact / approve packet or association / evaluate | Existing Phase 4 authority only | Existing preparation only | No |
| Confirm/dismiss monetary finding | Existing Phase 4 decision operation, current evaluation only | No | No |
| Download canonical manifest / approve disclosed JSON view | Yes, with current disclosure authorization | No in approved V1 | No |
| Produce/approve redaction | Yes; analyst may prepare proposal | Prepare only | No |
| Public sharing / vendor communication / source deletion / money edit | Not a Phase 5 V1 capability | Not a Phase 5 V1 capability | Not a Phase 5 V1 capability |

Unauthenticated access is denied. Other-tenant users get no resource existence, source references, amounts, filters, previews, export jobs or audit details. Owner/admin status is tenant-specific, not global. Existing source authorization remains required; proof access cannot bypass stricter source restrictions added later. Current roles never substitute for historical approval-role evidence.

Annotations may identify business context, relevance questions, missing evidence, explanatory notes or a correction request. Required identity: tenant, package/evidence target, author/time, kind, bounded text, reason and request identity. Revisions/retractions are appended with predecessor, not silent edits/deletion. A claim “price should be 19.10” is a proposed financial correction, clearly non-authoritative; it cannot change core or completeness to assert that price. Owner/admin REVIEWED means the proof was reviewed, not financial confirmation, legal validation or recovery. Financial confirmation/dismissal stays in `FinancialFindingDecision`; proof UI must not create a competing status or permit bypassing Phase 4 stale checks.

Proof annotations can never modify financial amount, financial evaluation, approved facts, source evidence, financial decision or rule behavior. All authorized internal readers may inspect accepted nonfinancial annotations, labeled author assertion rather than source fact. Internal annotations are excluded from default canonical core and exports. Analyst evidence requests are notes for internal review, not automated requests to vendors or Phase 6 workflow. Annotation content is inert escaped text; source/annotation instructions cannot execute tools, URLs, markup or alter authorization.

## 13. Redaction and internal disclosure

Approved V1 separates immutable internal canonical proof from owner/admin-approved disclosure views. No raw canonical manifest is overwritten/redacted in place. Current view/export authorization is checked independently of who approved the source originally.

A redaction proposal identifies the package revision/fingerprint, exact evidence/text/field paths, withheld category, reason, creator, policy version and expected previous proposal. Owner/admin approval pins that proposal and its disclosed fields. Text-span offsets refer only to frozen quoted text, not nonexistent PDF coordinates. Bank details, unrelated clauses/pricing, personal information and internal annotations can be withheld. Hidden content is represented as `REDACTED` with its class and verification limitation, not numeric zero, empty text, null unknown or a changed quotation pretending to be whole.

Do not redact/change an asserted monetary number, currency, unit, scope or essential qualification while retaining a claim of independently reproducible financial proof. If identity/applicability/approved basis/source excerpt needed for reproduction is hidden, the view must say “Redacted evidence view — independent verification limited”; it cannot inherit the internal COMPLETE badge as its own proof quality. The internal original may still be complete. Do not splice text to imply a prohibition or omit an exception that changes the reader's understanding.

The view records: parent core fingerprint, package/schema/revision, disclosure policy/version, redaction IDs/approver/time/reasons, disclosed payload, hidden-field descriptors, exact financial conclusion if disclosed, verification limitation and view fingerprint. `view_fingerprint` is SHA-256 of UTF-8 `FLA-PROOF-DISCLOSURE/1` followed by one LF and the section 9 canonical JSON of the disclosure payload, including parent fingerprint, approved redaction identity and visible content, excluding its own fingerprint and export envelope. Export byte checksum covers the complete view/envelope. A recipient can verify the disclosed view against its trusted view fingerprint; a partial view cannot recompute/verify the undisclosed full core or original source bytes. State that limitation explicitly. No hidden original content, storage keys, names/emails or accidental metadata may survive in the redacted artifact.

V1 must not pretend to redact or modify original PDF/XLSX/CSV binaries. Raw originals remain private authorized source downloads; disclosed proof views include selected cited content only. Automated PDF-binary redaction, vendor-safe original bundles and public sharing are deferred. Redaction generation/approval/download are audited. A manual download does not constitute a supported external-dispute/sharing workflow or legal certification.

## 14. Export scope and deferred PDF contract

Approved V1 formats: authenticated in-app view and owner/admin JSON manifest download, optionally an approved redacted JSON view. CSV alone loses the evidence/relationship/trace structure and is not a canonical proof export. Browser printing is not a controlled proof artifact or certified PDF export. PD5-06 approves these V1 formats; PDF generation and dependencies are deferred.

Each registered export identifies artifact/package/content revision, evaluation/finding, financial and proof versions, generated-at/actor, exact original currency/outputs, source hashes/references, core/view fingerprint, artifact checksum, confidentiality marker, issued completeness, context-as-of finding/currentness/availability and limitations. No raw original document or unrelated full frozen context is embedded by default. Byte-integrity data may be supplied as separately registered metadata/checksum rather than a self-referential hash inside the same bytes.

Export authorization is owner/admin plus current membership/source access, server-side allowlisted format/profile, expected package/view fingerprint and current-context token when a current-context export is requested. Generation and registration pin one package and one observed disclosure context. Recheck membership and permitted context immediately before serving bytes; do not expose public/signed source URLs or trust bearer/tenant/role supplied in a manifest. Download audit distinguishes artifact generated from actual download authorized/started; neither proves the person read it or sent it. Revocation prevents subsequent access but cannot recall bytes already downloaded.

Register only completed artifacts whose bytes match their checksum and pinned parent fingerprint; never serve a staged/partial file as complete. Failed/abandoned output is private and cleaned up; no broken registry entry becomes a trusted export. A saved artifact freezes its context-as-of. Later download of an old artifact must identify that historical context rather than claim its “current” label is current today; an updated context requires a new artifact, not a changed core.

If separately approved later, PDF must include executive summary, exact currency/amount, scope, historic/current/context-as-of labels, contractual/actual/match sections, full exact calculation, cited evidence with honest location precision, approvals/versions, limitations, confidentiality marker, page numbering and manifest/core or view fingerprint. Long excerpts/tables cannot silently truncate; any bounded appendix/disclosed material must be explicit. A PDF must retain exact detail behind any abbreviated headline. Parent manifest plus renderer/profile and exact byte checksum bind the artifact. No active JavaScript, remote resources, hidden original attachments/PII or “audit-certified/court-proof” language is permitted. Digital signing is a separate unapproved capability. No PDF implementation or dependency is introduced here.

## 15. Executive and reviewer experience

For F02 the specified executive layer is:

| Question | Display |
| --- | --- |
| How much? | Potential leakage **74,199.90 USD** |
| Why? | Billed unit price exceeds the approved applicable contract rate |
| Compared to what? | Contracted 18.40 USD/unit; billed 20.10 USD/unit; billed quantity 43,647 units |
| Complete? | Evidence complete at issue, with current source availability/currentness separately visible |
| Review/action? | Detected / confirmed / dismissed / needs review from Phase 4; separate proof-review state; “View proof” action |

Blocked headline: “Unable to calculate — allocation needed”; amount “Unknown”, never `$0`. Undercharge headline: “Billed below contracted amount — informational”; no netting button. No-overcharge headline explicitly names the assessed scope and leaves other categories unassessed. Stale or dismissed context remains visible next to the amount; it is not buried only under audit.

Reviewer drill-down order: Overview; Contractual basis; Actual billing; Match & applicability; Calculation; Source evidence; Approval history; Audit/history; Limitations; Historical versions. Executive view opens only summary. Detail exposes each operand's binding and original/approved distinction, date selection, term replacement, source hash/verification and retained uncertainty. Exact rule/compiler/core fingerprints are audit detail, not compulsory product jargon.

The reviewer experience uses side-by-side cited content for supported evidence: left contracted/master/amendment meaning and dates, right invoice/billed scope and dates, below the recorded comparison. Clicking an operand opens its own revision/evidence; it does not jump to the latest extraction. PDF page text and spreadsheet cells may be shown only where known; no fabricated visual box. Manual/document-level citations say so. Source content renders as escaped text and original download is a protected verified action. Historical selector displays evaluation/package revision and relationship reason, never overwrites current values with a historical amount without a label.

## 16. Audit, security, bounds and retention

Required durable events: `proof.generated`, `proof.generation_failed` (safe tenant-scoped diagnostic), `proof.reviewed`, `proof.annotation_added`, `proof.annotation_retracted`, `proof.content_revised`, `proof.replacement_recorded`, `proof.integrity_observed`, `proof.redaction_proposed`, `proof.redaction_approved`, `proof.export_generated`, `proof.export_failed`, `proof.download_authorized`. Use existing financial journal conventions for actor/time/role/tenant/target/reason/request, package/evaluation/fingerprints/profile and predecessor. No event may claim a finding was confirmed unless the existing Phase 4 decision was recorded. No `share.created/revoked` feature is introduced; any later external-sharing extension must audit it separately within this architecture.

Issued completeness changes only via a new package/content record. Current integrity/currentness observations can be derived reads or append-only observations; ordinary views need not create excessive write audit noise. Meaningful manual review/replacement/export/redaction and observed integrity failure must be retained. Successful immutable creation and its trusted audit origin commit together; rollback cannot leave a trusted orphan or missing journal event. Application logging keeps IDs, versions, safe codes and duration, not clauses, bank details, tokens, manifest bodies or raw source content. Privileged DDL/trigger disabling remains outside application integrity guarantees; production roles must lack those privileges.

Security requirements: authorization before loading values/references; composite tenant-safe bindings in later storage; current membership rechecked at write/download; allowlisted server rendering and private storage keys; no remote URL fetching; escaped inert citations/annotations; server-only tokens; no-store responses; safe attachment filename/content type/nosniff/disposition; bounded inputs, output and work; no cross-tenant detail through errors, pagination, cached artifacts, audit or summaries. A download name is generated from server IDs/profile, not a client path. Proof view access never grants original-source access beyond current policy.

Approved PD5-14 adopts initial versioned operational safety defaults (`proof-operations/1`): request JSON at most 1 MiB; annotation text at most 4,000 characters; at most 500 calculation-driving revisions (including guards named in Phase 4's `calculation_driving_revision_ids`), 100 original source documents and 5,000 proof bindings; canonical JSON at most 10 MiB; at most 100 MiB cumulative source-byte reads per operation; a 25-second synchronous work budget; at most 100 history records per page; at most two concurrent proof operations per tenant; and at most ten new generation/export operations per actor per rolling minute, with explicit Retry-After. These limits apply to the tenant/actor operation totals, not a quota multiplied by worker count. Existing configurable original upload limits remain unchanged (baseline 20 MiB/document). Idempotent reads may reuse existing output but still require authorization and bounded access; no distributed queue/Kafka/cluster is required.

These defaults are **not financial-policy invariants**. They may be tuned later using measured performance, production load testing, enterprise usage and infrastructure capacity; record the effective operational profile version and bounds for diagnostics/audit without rewriting historical proof content. Tuning must never silently truncate proof, suppress valid financial amounts, weaken authorization, tenant isolation or integrity, alter financial calculations, or convert incomplete proof to complete proof. If a valid proof exceeds a limit, return an explicit bounded-resource result/error such as `PROOF_LIMIT_EXCEEDED`, identify the safe bound/retry behavior, and preserve the underlying evaluation/finding. Never emit a partially truncated COMPLETE package or delete small findings to satisfy a resource limit. Operational-profile tuning alone does not change C01–C10, monetary authority or the canonical financial/evidence fingerprint.

Retention is a policy boundary, not a guessed law or retention period. Existing referenced-source deletion is blocked by Phase 4 and must remain so in ordinary V1 use. No automatic tenant/source/proof/audit purge is permitted in Phase 5 V1; a later capability requires an explicit approved retention/deletion policy that addresses originals, copied excerpts/values, manifests, artifacts, annotations, actor identifiers, backups and audit together. UUIDs/hashes may still be sensitive/linkable; do not declare them exempt personal data.

For a legally authorized deletion/retention expiry, compliance must determine permissible destruction and any minimal tombstone; Phase 5 cannot invent “retain forever”, seven-year retention, legal hold priority or an override of deletion rights. A future approved purge must preserve truthful availability/deletion state where legally permitted and must never display Evidence Complete/current-original-available after material evidence was removed. Existing issued completeness is historical; live availability becomes unavailable, independent reconstruction may no longer be possible, and access to erased data is denied. No hidden shadow copy may bypass the deletion policy. Approved PD5-08 defers retention duration, legal holds, jurisdictional deletion, tenant offboarding and backup erasure to a later explicit compliance/legal policy before any such capability is implemented. No permanent-retention or regulatory-compliance claim is authorized.

## 17. Currency, aggregation and future boundaries

Each proof preserves the original currency and assessed comparison basis. USD and EUR packages are not summed or converted. An undercharge is not subtracted from unrelated positive findings. Source diagnostics in a blocked currency mismatch remain separated by currency; no difference of raw numbers is rendered as money.

Individual package scope mirrors its evaluation. A combined price/discount proof is one package family, not price proof + discount proof + combined proof to sum. F32's disjoint segment evaluations have two packages; a dashboard may display their existing supported 380 USD view, but Phase 5 must not issue a third monetary finding/proof claiming the same money. V1 aggregate proof/report persistence is out of scope under approved PD5-13. A future report would reference underlying package IDs/fingerprints, retain currency/coverage/non-overlap and avoid becoming new monetary authority.

Phase 6 interface boundary only: stable tenant/evaluation/finding/proof identifiers, core fingerprint, original currency/result and explicit lifecycle context could be referenced later. No claim sent, vendor response, credit note received, recovered money, gain-share billing or status is specified as a Phase 5 workflow. Payment timing is not inferred: a proof of a billing assessment need not assume payment occurred. Future pre-payment usage can reference the same evidence concepts, but no payment blocking or Firewall decision is built or approved.

Extensibility is limited to versioned typed rule/bundle identifiers, operand roles, evidence graph, trace shape, package kind, limitations and schema registry. A future rule must supply its Phase 4-approved semantics/evaluation before Phase 5 can present its evidence. No generic plug-in activates tiers, prohibited fees, surcharge, rebate, indexation, SLA, minimum, duplicate-payment or SaaS rules through proof generation.

## 18. Approved terminology and non-goals

Use: Potential Leakage; Contracted Amount/Rate; Billed Amount/Rate; Expected Financial Reality; Actual Financial Reality; Evidence Complete at Issue; Needs Review; Unable to Calculate; Source Evidence; Calculation Trace; Approved Financial Facts; Historical Assessment; Informational Undercharge; Redacted Evidence View. “Confirmed” refers only to the actual existing owner/admin financial decision; “Reviewed proof” is distinct.

Do not use: vendor stole, fraud, illegal charge, legally owed, confirmed debt, guaranteed recovery/savings, audit-certified, court-proof, legally proven, recovered cash or confirmed overpayment merely from a billing discrepancy. Cite a human annotation as its author's assertion, not a platform legal conclusion. Completeness, a hash or an export is not legal judgment.

Non-goals: legal determination/advice; autonomous dispute submission/vendor communication; recovery tracking/refund collection/gain-share; payment blocking/prevention; OCR or broad free-form legal interpretation; ERP/SaaS/payment connectors; tiers, surcharge/unauthorized-fee/rebate/FX/SLA/minimum or duplicate-payment implementation; SaaS-license optimization; Leakage DNA/Firewall; external/vendor accounts/public sharing; binary document redaction; V1 PDF/aggregate proof; production legal/compliance retention enforcement without approved policy. No Phase 1–4 redesign, new financial family, financial recalculation/edit endpoint, migration or application code is part of this specification task.

## 19. Worked proof packages and lifecycle examples

These are specification fixtures, not newly executed engine results. F-numbers reference unchanged Phase 4 vectors. Decimal strings below preserve source precision; monetary evaluation columns use six fractional digits, while an executive may display two where the recorded currency profile permits. Mathematical verification here never authorizes an evaluation. `E`, `A`, `Δ` and `P` denote stored expected, comparable actual, signed discrepancy and nullable potential respectively.

Unless a case explicitly says otherwise, its fixture includes tenant T1; an approved stable invoice and one master; exact bill, terms, packet, association and relevant reference/adjustment revisions; source hashes verified against captured bytes; approval actor UUID/time/cutoff/reason; historical evidence bindings; supported dates/currency/unit/tax basis; an established rounding profile; the unchanged calculation snapshot/fingerprint/versions; all C01–C10 results; and a trusted issuance audit. Symbols H-contract/H-invoice denote actual 64-character hashes in a real package, not literal hashes or fabricated proof IDs. Each case identifies the exceptional operands, decisions and lifecycle behavior; the common fixture supplies the remaining required content from sections 4 and 9. No COMPLETE assertion is justified by the few illustrative numbers alone.

### WP-01 — Fixed unit-price overcharge, F02

- Recorded R1 inputs: contracted unit price `"18.40"` USD/unit, billed unit price `"20.10"`, quantity `"43647"` in the same unit and scope. Price and quantity each have their own approved meaning/evidence binding; the packet/association explain why this price applies.
- `E = "803104.800000"`, `A = "877304.700000"`, `Δ = P = "74199.900000"`. An independent illustration is `(20.10 − 18.40) × 43647 = 74199.90`; it is labeled reconstructed arithmetic if that intermediate was not separately recorded in the trace.
- One MONETARY_FINDING_PROOF, finding ID equal to evaluation ID, COMPLETE at issue. Summary: “Potential leakage 74,199.90 USD; billed 20.10 versus contracted 18.40 per unit across 43,647 units.” No recovered/legally owed label.
- Canonical core binds the exact source-value scales, frozen E/A/Δ/P, unit, scope, trace, H-contract/H-invoice, review lineage and evaluation fingerprint. App and JSON reference the same core fingerprint; each JSON artifact has a separate byte checksum.

### WP-02 — No-overcharge unit price, F01

- Approved contracted and billed price `"10.00"`, quantity `"100"`, USD; the selected terms and billing evidence cover the same scope.
- `E = A = "1000.000000"`, `Δ = "0.000000"`, `P = null`; stored outcome NO_OVERCHARGE.
- COMPLETE ASSESSED_COMPARISON_EVIDENCE, finding ID null. Headline: “No overcharge in this assessed scope.” No monetary finding, recovery claim, or assertion that all invoice lines were assessed.
- Zero discrepancy is a known result; null potential means no positive finding, not missing evidence. Regeneration preserves both distinctions.

### WP-03 — Informational undercharge, F03

- Contracted price `"10.00"`, billed price `"9.00"`, quantity `"100"`, USD.
- `E = "1000.000000"`, `A = "900.000000"`, `Δ = "-100.000000"`, `P = null`; actual engine outcome UNDERCHARGE.
- COMPLETE ASSESSED_COMPARISON_EVIDENCE with no finding ID. Show signed −100.00 USD as informational undercharge; do not replace it with zero discrepancy or make it negative potential leakage.
- A separate +100 USD finding elsewhere remains +100; this package authorizes neither invoice-wide offsetting nor collection of an alleged underpayment.

### WP-04 — Complete fixed recurring fee, F06

- R2 approved fee `"5000.00"` USD for the identified complete July cycle; billed fee `"5400.00"`. Evidence binds fee/cadence, complete-cycle assertion, period and applicable packet.
- `E = "5000.000000"`, `A = "5400.000000"`, `Δ = P = "400.000000"`.
- COMPLETE MONETARY_FINDING_PROOF. Summary identifies the complete cycle rather than displaying a fabricated quantity of days or a unit-price formula.
- If a later source disputes cycle completeness, use Phase 4 correction/new evaluation. No proof annotation may introduce daily proration or adjust this historical 400 USD.

### WP-05 — Missing unconditional percentage discount, F04

- R3 evidence establishes an eligible base `"50000.00"` USD, explicit unconditional percentage `"8"`, and scope/base membership. The actual bridge has no applied discount, so A is `"50000.000000"`.
- Recorded expected calculation `50000 × (1 − 8/100)`: `E = "46000.000000"`, `Δ = P = "4000.000000"`.
- COMPLETE MONETARY_FINDING_PROOF binds the contractual percentage separately from money and quantity, and records why the base is eligible and complete.
- The summary says “Required unconditional 8% discount absent from this assessed base.” It does not reinterpret a conditional rebate or enable a fixed-money discount rule.

### WP-06 — Price plus missing discount, F27

- One scope: contracted price `"10.00"`, quantity `"100"`, unconditional discount `"10"` percent on the contracted-price base; billed price `"12.00"` with no actual discount, USD.
- `E = 10 × 100 × (1 − 10/100) = "900.000000"`; `A = "1200.000000"`; `Δ = P = "300.000000"`.
- One COMPLETE monetary package, one evaluation/finding, one combined `core-bundle/1` trace with both families. Components may explain price difference 200 and contracted-base discount difference 100; they are explanatory contributions to the same 300.
- No independent 200 + inflated-base 120 = 320 claim, and no additional 300 aggregate finding. View/export retains the shared base and operand bindings.

### WP-07 — Amendment selects applicable price, F12

- Master price `"10.00"`; approved amendment price `"12.00"` effective 1 July; service date 15 July; quantity `"100"`; billed price `"13.00"`, USD. The historical packet includes both sources and the applicable replacement edge.
- `E = "1200.000000"`, `A = "1300.000000"`, `Δ = P = "100.000000"`.
- COMPLETE monetary package shows the approved economic-date selector and selected amended term key. Master price remains visible as superseded context, not a second operand yielding 300.
- No assumption that the most recently uploaded/signed document governs: the recorded approval, effective scope and precedence establish the selection.

### WP-08 — Price-changing period without allocations, F14

- Service interval 15 June–15 July crosses a 1 July change from `"10.00"` to `"12.00"`; total quantity `"100"`; posted source amount `"1200.00"` USD; there is no approved quantity/amount allocation across periods.
- Stored NEEDS_REVIEW with the recorded period/allocation reason; E/A/Δ/P are all null. The invoice's 1,200 USD is source diagnostics, not a comparable evaluated A.
- COMPLETE BLOCKED_ASSESSMENT_EVIDENCE is possible: it explains the crossing, approved terms, missing allocation and prohibition on automatic proration. No monetary finding ID.
- No half-month split, quantity interpolation, assumed latest price or “zero leakage” result. Financial resolution requires approved allocations and a new Phase 4 evaluation.

### WP-09 — Currency mismatch, F15

- Contracted `"10.00"` USD/unit; billed `"12.00"` EUR/unit; quantity `"100"`. Source diagnostics may show 1,000 USD and 1,200 EUR independently.
- Stored NEEDS_REVIEW/currency mismatch: evaluation E/A/Δ/P and unresolved comparison currency remain null.
- COMPLETE blocked explanation shows both currencies, source hashes and mismatch. It must not display “200” with either currency or a mixed-currency total.
- JSON preserves null financial comparison fields and typed source currencies. No exchange-rate fetch or implicit conversion occurs.

### WP-10 — Known missing governing material

- An approved packet attestation identifies an incorporated price schedule as missing for the assessed line/period. A visible master price alone is insufficient; the engine records the governing-packet blocker.
- E/A/Δ/P remain null. Existing approved packet-gap assertions and available contract/invoice bytes are fully traceable; there is no fabricated Document/hash for the absent schedule.
- COMPLETE blocked explanation can show “Unable to calculate: governing material missing.” It cannot be a monetary proof, a claim that the schedule prohibits a fee, or a recommendation to use the visible price anyway.
- When the schedule arrives, create reviewed Phase 4 revisions/new evaluation, then a separately anchored package. Do not patch the old packet or blocker explanation.

### WP-11 — Material rounding ambiguity, F26

- Recorded raw expected `"10.005"`, actual `"10.01"` USD, quantum `"0.01"`, unresolved plausible half-up and half-even profiles.
- Trace alternatives: half-up E 10.01, A 10.01, Δ 0; half-even E 10.00, A 10.01, Δ 0.01. These are diagnostic alternatives, not two findings.
- Stored NEEDS_REVIEW; authoritative E/A/Δ/P null. COMPLETE blocked explanation includes both unchanged alternatives and the material rounding reason.
- No ambient Decimal mode, midpoint guess, epsilon, materiality threshold or selection of the alternative that produces leakage. An approved profile belongs to a new Phase 4 revision/evaluation.

### WP-12 — Correctly allocated credit, F21

- Contracted price `"10.00"`, quantity `"100"`, USD; gross posted amount `"1200.00"`; directly evidenced same-scope credit `"200.00"`, with its identity and allocation fixed in the billing bridge.
- `E = "1000.000000"`; `A = 1200 − 200 = "1000.000000"`; `Δ = "0.000000"`, `P = null`. Outcome NO_OVERCHARGE.
- COMPLETE comparison package shows gross, credit identity, signed application and residual actual exactly once. It does not report the gross 200 as potential leakage or describe the credit as recovery collected by this product.
- For PD-07's separate residual illustration, gross 1,500 less allocated credit 300 against E 1,000 yields A 1,200 and Δ 200; a proof must copy that evaluation's residual 200, never its gross 500.

### WP-13 — Finding subsequently dismissed

- Start from WP-01's complete 74,199.90 USD package. Owner/admin later appends a `false_positive` decision with actor/time/reason and expected last-decision ID.
- The frozen potential remains `"74199.900000"`, core fingerprint unchanged. Current view says “Evidence complete at issue; finding dismissed”, shows the actual decision history and separately observed currentness.
- Existing eligible-current summary semantics exclude the dismissed finding; a proof neither reinstates it nor zeros the historical amount. A historical export states the decision context as of export time.
- Analyst annotation “I disagree” cannot dismiss or reopen it. Authorized reopening is a distinct audited Phase 4 finding decision, plus a new evaluation if financial inputs changed.

### WP-14 — Later amendment and superseding evaluation

- Old bounded knowledge: approved master `"10.00"`, Q `"100"`, billed `"13.00"`, applicable July scope; old evaluation E 1,000, A 1,300, Δ/P 300 USD, with its original packet and cutoff.
- A later discovered amendment supports `"12.00"` for the same service scope. Owner/admin explicitly approves its governing-packet revision, precedence and retroactive applicability; a new Phase 4 evaluation records E 1,200, A 1,300, Δ/P 100 USD. The proof engine does not apply the amendment itself.
- New monetary package anchors to the new evaluation. Old issued package/300 USD stay immutable and reproducible, with currentness STALE. Owner/admin may record a same-scope explicit successor relation with reason; generation time alone cannot create that relation.
- Executive default uses supported current finding semantics; a historical reviewer can see both. No 400 USD combined total and no overwrite of old money or approved cutoff.

### WP-15 — Historical reproduction after extraction rerun

- WP-01's approved `"18.40"` derives from run 1/field 1. A later rerun of the same verified document produces a candidate `"22.00"`; a filename/display label changes too.
- Historical proof still binds run 1/field 1 and reviewed 18.40. Existing snapshot/trace and original bytes reproduce E 803,104.80, A 877,304.70 and Δ 74,199.90. The candidate grants no authority.
- Ordinary regeneration under the same schema/assembly finds the existing core fingerprint/package. A fresh current-context overlay or render artifact does not revise the financial result or core.
- If original bytes are no longer accessible, label current UNAVAILABLE; do not promise full source reproduction from a quotation alone or substitute the latest extraction.

### WP-16 — Evidence hash mismatch

- A referenced original has pinned hash H-contract, but a bounded consistent byte capture hashes to H-other. Document metadata still reports H-contract.
- New generation returns `PROOF_SOURCE_INTEGRITY` with a safe hash-mismatch diagnostic and issues no trusted complete package. It cannot stream those changed bytes under the original evidence identity or update the expected hash to make the check pass.
- An already issued package keeps its original core/output/completeness-at-issue record; current integrity becomes MISMATCH with an observed-at event and the offending source is quarantined. Historical financial amounts are not edited.
- Investigate/restore bytes or use reviewed new source/revision/evaluation as appropriate. Hash equality proves identity to pinned bytes, not correctness or legal authenticity of their content.

### WP-17 — Document-level/manual provenance without precise coordinates

- A manually reviewed `"10.00"` USD price has exact Document/hash, approved semantic support and reviewer citation/actor/time, but no ExtractionRun, page number or bounding box. Bill Q 100, A 1,200; existing E 1,000 and Δ/P 200.
- COMPLETE monetary package is allowed when the binding is unambiguous and C01–C10 pass. Location label: “Document-level, reviewer-supplied citation; exact page/coordinates unavailable.” Original bytes remain available.
- No invented page/cell, OCR coordinate, machine confidence or claim of machine-verified verbatim quotation. The reviewer can inspect the verified original document and the approved support assertion.
- If the manual binding cannot uniquely identify the asserted term, this becomes INCOMPLETE/PROOF_BINDING_MISSING rather than a silent precision downgrade.

### WP-18 — Cross-tenant access attempt

- Tenant T2's user submits a known T1 evaluation/package/document/artifact ID to view, generate or download. Neither global UUID knowledge nor an old signed-in session authorizes access.
- Return the existing indistinguishable not-found/unauthorized tenant behavior before exposing source bytes, amount, existence, filename, fingerprint or private object key. No T1 package, export or financial event is created by the request.
- Actor-appropriate denied-operation security logging may use a correlation ID and minimal metadata; it must not publish T1 financial/source content to T2 or forge a successful T1 audit event.
- Mixed-tenant evidence edges also fail server and database isolation. An artifact's stored creator role never overrides the requester's current membership.

### WP-19 — Duplicate simultaneous generation and retry

- Two authorized requests, including different request UUIDs, target the same WP-01 evaluation, kind, schema/assembly and unchanged canonical inputs. A third retries one request UUID after a response loss.
- Transactional uniqueness/fencing yields one canonical package UUID/revision/core fingerprint and one successful issuance audit. All successful responses reference it; there is still one Phase 4 finding.
- Reusing a request UUID for different evaluation/disclosure content fails as a conflict. Distinct render/export requests may create artifacts with distinct bytes/timestamps/checksums, all referencing the same core.
- A concurrent material approval change in CURRENT mode cannot issue a mixed package: return a stale-input outcome/retry. Explicit historical mode can explain the pinned old evaluation and mark currentness accurately.

### WP-20 — Owner-approved redacted JSON export

- WP-01 contains unrelated bank/PII fields in displayed evidence. Owner/admin approves a separate exact field-path redaction view and reason; essential price/quantity/currency/date/source and limitation facts remain disclosed.
- Original core, source bytes, potential and core fingerprint remain unchanged. Disclosed JSON references parent core fingerprint, redaction revision/profile and its separate disclosed-view fingerprint; the final artifact has its own byte checksum and creator/time.
- The download contains neither hidden original fields nor unredacted originals, filenames/annotations/snapshot content that reintroduce the removed PII. Internal recipients require existing tenant authorization; no external vendor link/send exists.
- Recipient can reproduce visible arithmetic and disclosed-view hash. A partial view cannot independently recompute the complete internal core hash. If critical identity/provenance is also hidden, mark the view limited for independent verification, not “fully verified complete proof”.

### WP-21 — Rounding uncertainty with invariant result

- Recorded exact aligned E `"1000.00"`, A `"1200.00"`, quantum `"0.01"`; all recorded plausible profiles produce E 1,000, A 1,200, Δ/P 200 USD.
- Existing permitted evaluation retains rounding uncertainty and its invariant alternatives. COMPLETE monetary package displays the invariance and uncertainty together, without pretending one rounding mode was approved.
- No blocker is invented merely because the mode is unresolved; no missing alternatives are fabricated. If the stored trace lacks a required alternative, proof completeness fails without changing financial output.

### WP-22 — Repairing proof availability without revising money

- Historical evaluation has fully approved operands/trace but original invoice bytes temporarily unavailable. An issued INCOMPLETE package records `PROOF_SOURCE_UNAVAILABLE`, expected hash and unchanged potential.
- Exact original bytes are restored and verified against the same historical hash. Authorized explicit evidence-repair generation creates a new immutable proof content revision, linking its incomplete predecessor and changed C07/gap result; evaluation/finding ID and monetary output remain identical.
- Old incomplete core is retained. New issuance actor/time/reason and content fingerprint are distinct; a routine repeat now returns the complete revision under its unique semantic key. Different bytes cannot use this repair path.

### WP-23 — Disjoint allocated periods, F32

- Approved split: Q `"400"` before 1 July at contracted `"18.40"`, billed `"19.20"`, gives E `"7360.000000"`, A `"7680.000000"`, Δ/P `"320.000000"` USD; Q `"600"` from 1 July at contracted `"19.10"`, billed `"19.20"`, gives E `"11460.000000"`, A `"11520.000000"`, Δ/P `"60.000000"` USD. The exact source quantity/amount allocations establish non-overlap.
- Two COMPLETE packages anchor to the two disjoint evaluations and preserve period/parent allocation bindings. Existing compatible view totals 380 USD; no third finding is created.
- This is explicit allocation, not automatic temporal interpolation. It does not enable a V1 aggregate proof, cross-currency sum, credit reuse or double counting.

## 20. Acceptance criteria and future implementation test strategy

Acceptance requires an executive to see exact potential/currency or explicitly unknown money, comparison/reason, evidence-completeness-at-issue and relevant current review/stale/source warnings in one summary. A reviewer must traverse every material operand/applicability/coverage assertion through its approval to unchanged source bytes and distinguish quotes, machine candidates and approved meaning. JSON must validate against the pinned schema and reproduce its core fingerprint with a conforming independent canonicalizer. Historical core/amounts remain immutable under all future events below. C01–C10 and limits are deterministic; no fuzzy “enough evidence” score is accepted.

The following tests are requirements for later authorized implementation, not tests implemented/run in this documentation task. Reuse Phase 4 golden vectors unchanged and isolated PostgreSQL 17 transactional/trigger tests. Pure schema/hash/format tests can use independent parsers/canonicalizers; they must not merely mirror implementation serialization. Existing backend/frontend/security/migration CI remains mandatory for eventual implementation.

| Future test group | Required cases and meaningful assertions |
| --- | --- |
| Financial compatibility | WP-01–12/21/23 and all supported Phase 4 vectors: exact copied outcome/currency/E/A/Δ/P; blocked null versus zero; undercharge null potential; one combined finding; no call to a fresh financial evaluator during proof generation. |
| Typed inputs | Decimal source scale, six-digit stored outputs, very large valid NUMERIC values, small one-cent finding, zero quantity/bases as actual approved semantics; reject float coercion/nonfinite values; quantities/percentages not Money. |
| Completeness | Each C01–C10 individually missing/failed; deterministic gap ordering; current source unavailable; mismatch fails issuance; manual document-level precision allowed; blocked package complete explanation with financial nulls. |
| Revision graph | Every selected/guard ID, packet, association, reference, bill, allocation/credit maps to exact tenant/snapshot/evidence; prepared/revoked guards never mislabeled approved; missing historical key cannot fall back to latest. |
| Source capture | Exact bytes verify; changed storage with unchanged metadata detected; change during read/capture returns safe failure; missing/truncated/oversized files bounded; no stream after mismatch; storage paths never returned. |
| Candidate reruns | Changed candidate/raw extraction version/filename leaves approved historical input/core untouched; original run/field remains traceable; explicitly manual evidence has no invented run. |
| Quotes/locations | PDF page/line/text offsets versus unsupported bounding boxes; CSV row/header; XLSX sheet/cell; reviewer citation versus extracted raw text; no false machine-verbatim claim; ambiguous support yields a gap. |
| Governing/time gates | Amendment/superseded master, selected date, approved retroactivity, known missing material, crossing blocked and allocated-disjoint scopes; no current packet substitution or date/proration guess. |
| Credits/discount | Gross-to-net bridge, allocated credit exactly once; unresolved allocation remains blocker; conditional/fixed-money discount stays unsupported; combined discount uses contracted base; unrelated undercharge never offsets positive. |
| Rounding | Material alternative delta changes versus invariant alternatives; original quantum/stage/aggregation/profile retained; no default ambient mode/epsilon/materiality deletion; raw values and alternative orders preserved. |
| Manifest canonicalization | Independent expected vectors: key order, Unicode without normalization, escaped strings/control characters, supplementary Unicode ordering, invalid surrogate/duplicate keys, financial numeric strings, null versus absent/zero, ordered arrays versus set sorting, UUID/hash/timestamp formats. |
| Hash boundaries | Same semantic core produces same hash under permitted input ordering; each money/source/binding/version/gap change changes it; current overlay/annotation/display filename does not; envelope/artifact checksum differs from core and cannot self-hash embedded final checksum. |
| Trust/reproducibility | Tampered field/trace/source/hash rejected against trusted stored manifest; attacker-rehashed export is not trusted issuer certification; whole-snapshot digest binds exact frozen context without leaking it; missing deployment digest never invented. |
| Idempotency | Same request retry, different keys with identical inputs, response loss and simultaneous identical generation yield one package and issuance event; same key/different scope conflicts; evidence repair creates one new content revision only. |
| PostgreSQL concurrency | Generation versus approval/revocation, packet revision, association revocation, membership removal; current-mode commit fences fail/retry safely; historical-mode reads exact old dependencies; two requests serialize under uniqueness without deadlock. |
| Export concurrency | Role/redaction changed before commit or stream prevents stale permissions/export; artifact references one consistent core/disclosure/current-context observation; no half-updated view; private failed/orphan artifacts cleaned without evidence deletion. |
| Financial immutability | No API/ordinary application-role SQL update/delete of historical evaluation/core/audit; annotations/rendering cannot edit E/A/Δ/P; new approved input creates a new Phase 4 evaluation, never patching old money. |
| Status/lifecycle | Complete-at-issue + stale + dismissed + current unavailable combinations; actual decision versus API needs_review overlay; currentness UNKNOWN on check failure; no invisible reopening or age-based replacement. |
| Supersession | Same-scope owner-approved relation with reason; different tenant/currency/period/scope denied as simple replacement; predecessor expectation/idempotency, cycles and conflicting successor branches guarded; newest timestamp alone does nothing. |
| Authorization | Full owner/admin/analyst/viewer matrix for view/generate/annotate/review/redact/export/replace; current membership on every request and final download; financial authority stays Phase 4 owner/admin; viewer mutation denied. |
| Tenant isolation | WP-18 for evaluation, family, revision, evidence, source, annotation, audit, artifact, request key and private cache; mixed-tenant FK rejection; denied responses/logs reveal no victim data. |
| Annotation safety | Separate actor/time/reason and revision history, length limit, plain inert text, escaped UI/JSON, correction references; no HTML/script injection, financial amount/evaluation, approved-fact, source-evidence, financial-decision or rule-behavior mutation, approval/decision impersonation or implicit legal conclusion. |
| Audit integrity | Trusted trigger origins, immutable history, denied direct forged insert, actor/reason/target and generated/exported/downloaded records; duplicate canonical issuance has one event; historical financial audit unchanged; no secrets/source bodies in logs. |
| Redaction | Original core/file unchanged; exact field paths/revision/owner approval; confidential data absent recursively from JSON, annotations, labels and filenames; material hidden fields carry limited-verification warning; parent hash cannot expose removed values. |
| Export | App and JSON same core; content-type/attachment escaping/current authorization, private staged bytes, exact artifact hash; versioned export-as-of context; no external link/email/vendor user; archived artifact treated as historical. |
| UI | Clear scoped zero/negative/blocked headline; separate completeness/review/currentness badges; accessible source link/manual location; honest quote and six-digit/raw detail; disjoint totals and currency separation; viewer read-only controls and server enforcement. |
| Limits/failures | Every approved count/byte/time/inflight/rate bound at boundary/boundary+1; controlled reason/retry-after; no partial COMPLETE export or silent truncation; original evaluation survives; queue/process loss does not duplicate issuance. |
| Operational tuning | Verify the effective versioned defaults and measured successor profile independently of financial policy; limits apply across tenant/actor requests; changing a bound cannot truncate content, suppress amounts, weaken authorization/isolation/integrity, change calculations or turn an incomplete proof complete. |
| Retention | Ordinary deletion of referenced originals/core/audit blocked; missing-source overlay correct; approved future erasure policy tested separately before activation, including exports/redactions/backups; no ad hoc purge or retention guarantee. |
| Migration/regression, later | Isolated PostgreSQL 17 upgrade/head/check, complete suite, safe populated downgrade refusal; all prior backend/frontend/golden/security suites; no legacy CaseStatus, Contract/Invoice or financial-version reinterpretation. |
| Deferred PDF, if later approved | Raw/currency formatting, page footers/hash/version/as-of/limitations, reproducible pinned renderer, no hidden PII/attachments, long quote/table wrapping and pagination, byte hash; rendered visual QA, no legal-certification claims. |

Implementation gate satisfied by the subsequent explicit user instruction: Phase 5 V1 is implemented on `phase5/leakage-proof-engine`; [implementation validation](phase5-validation.md) maps these requirements to actual tests and complete CI. Specification approval alone was not implementation authorization. Phase 6 and automatic merge remain unauthorized.

## 21. Policy compatibility, structured self-review and delivery checks

### 21.1 Inherited policy: no new approval required

| Approved Phase 4 decision | Inherited Phase 5 constraint |
| --- | --- |
| PD-01 | Every calculation-driving fact/mapping remains manually owner/admin-approved. Candidate confidence, proof completeness, proof review, annotation or export cannot confer financial authority. |
| PD-02 | Reuse the evaluated approved association/explicit reference/PO link; one master per invoice evaluation. No proof-time fuzzy matching, second master or guessed shared allocation. |
| PD-03 | Explain only fixed unit price, complete fixed fee/cycle, and explicit unconditional percentage discount, including one coherent combined bundle. No new financial family through proof metadata. |
| PD-04 | Preserve the scoped, versioned governing-packet attestation and known material gaps. Complete proof means complete evidence of the assessed result/blocker; it never certifies an exhaustive contract universe. |
| PD-05 | Preserve selected economic dates, amendments, explicitly approved retroactivity and allocations. No invoice-date substitution, daily proration or automatic interpretation. |
| PD-06 | Exact Decimal values/profile/alternatives, material unresolved rounding blocks, invariant results retain uncertainty. No epsilon/default rounding/materiality suppression. |
| PD-07 | Actual bridge applies directly allocated credits once; no cross-invoice/period netting or unrelated undercharge offset. Only existing compatible disjoint current findings can form a view; no duplicate aggregate finding. |

The Phase 4 specification's F03 historical status label says NO_OVERCHARGE while the merged engine distinguishes UNDERCHARGE. Both express no positive finding; this document preserves the actual stored outcome and negative discrepancy. Similarly, blocked vectors may describe known source amounts while the implemented evaluation's authoritative comparison outputs are null. Proof shows those source diagnostics separately; it does not change the policy vectors or manufacture settled monetary outputs. Legacy illustrative CaseStatus labels do not imply that Phase 4 creates a `LeakageCase` row. These are representation observations, not financial-policy amendments.

### 21.2 Structured self-review

This historical review checks the approved specification. “Addressed” below means requirements/examples existed at specification approval, not a claim about runtime enforcement at that time. The subsequent implementation's 26-point security review, financial-integrity review and test results are recorded separately in [implementation validation](phase5-validation.md).

| Risk checked | Review result and correction/guard |
| --- | --- |
| SR-01 Contradiction with Phase 4 approved policy | Addressed: policy unchanged; inherited PD-01–07 table above; three families and exact original vectors. WP-23 uses original F32 quantities/amounts, 320 + 60 = 380. Representation differences explicitly explained. |
| SR-02 Accidental recalculation of financial truth | Addressed: sections 1/8/10/11 copy immutable evaluations; reconstruction is verification only; no fresh evaluation or missing-input inference. |
| SR-03 Silent historical mutation | Addressed: sections 6/7/9; immutable core/envelope and financial snapshots, separate content/render/disclosure revisions and current overlays. WP-13–16/22 preserve old money. |
| SR-04 Ambiguous proof complete | Addressed: section 5 C01–C10, two issued completeness states, distinct blocked explanation and failure/absent states; mandatory current warnings. PD5-01/03 are approved; human proof review remains a separate optional audited state. |
| SR-05 Accidental legal claims | Addressed: sections 1/9/18; typed evidence/hash identity does not prove enforceability/authenticity; forbidden terminology and human assertions attributed. |
| SR-06 Recovery creeping into Phase 5 | Addressed: sections 17/18; only future stable-ID interface, no sending, recovery ledger/refunds/commission/payment blocking. Credits are actual billing evidence. |
| SR-07 Cross-tenant leakage | Addressed: sections 11–16; current membership, composite evidence isolation, tenant cache/storage/download scoping and denied-response confidentiality; WP-18. |
| SR-08 Insufficient evidence provenance | Addressed: sections 4/5/8/9; all driving/guard IDs and typed inputs bound to snapshot/review/support/original hash; contradictions fail instead of latest-source fallback. |
| SR-09 Unsupported Phase 3 locations | Addressed: sections 2/5/8; actual PDF/CSV/XLSX location capabilities, no fabricated bounding box/OCR; manual document-level binding permitted with limitation, WP-17. |
| SR-10 Decimal-to-float risk | Addressed: sections 8/9; finite exact typed strings, preserved source scales, recorded raw/settled values, explicit canonicalization; future independent tests. |
| SR-11 Stale/superseded ambiguity | Addressed: sections 5/6/11; currentness vs completeness vs explicit successor vs human decision; historical mode, no latest-timestamp replacement, WP-13–15. |
| SR-12 Double counting | Addressed: sections 10/17; one combined finding, credit once, no aggregate proof finding, no offset/FX; WP-06/12/23. |
| SR-13 Proof versus finding confusion | Addressed: section 3 positive evaluation is finding; one proof family per evaluation/kind; nonpositive/blocked finding_id null; generation creates no financial claim. |
| SR-14 Proof versus annotation confusion | Addressed: sections 6/12/13/16; separate inert nonfinancial annotations, author/time/reason/history and disclosure review; no source/amount/decision edits. |
| SR-15 Missing audit requirements | Addressed: section 16 event catalog and retained financial audit; trusted trigger-origin extension needed later, not arbitrary direct journal inserts. |
| SR-16 Export/redaction confidentiality | Addressed: sections 13/14; owner-approved separate view, final current authorization, recursive leakage checks, private artifacts, redacted-view limitations, no public/vendor sharing; WP-20. |
| SR-17 Concurrency inconsistencies | Addressed: section 11 pinned revision/role/source captures and commit fences; CURRENT versus HISTORICAL mode, atomic issuance, safe conflicts; section 20 future PostgreSQL race tests. |
| SR-18 Idempotency ambiguity | Addressed: sections 6/9/11; request-key conflict plus semantic uniqueness, one issuance event, separate artifact identities; WP-19/22. |
| SR-19 Extensibility/overengineering | Addressed: sections 7/17/18; typed/versioned trace interface and deferred rules only; no blockchain, generic legal interpreter, queue redesign, aggregate engine or PKI requirement. |
| SR-20 Product policy accidentally invented | Addressed: header and section 22 record explicit user approval of Option A for PD5-01–14 and the PD5-14 clarification; inherited financial constraints are separated. Product approval is not implementation or merge authorization; deferred compliance policy remains unresolved. |

The historical specification review found no material contradiction requiring a change to Phase 4 policy. Its identified implementation risks were actual-byte capture, historical bindings, version recognition, audit origins, authorization fencing, canonicalization and recursive redaction. Their implemented guards and verification are recorded in [implementation validation](phase5-validation.md). Product/legal retention policy remains intentionally unresolved; no compliance or legal-authenticity claim is introduced.

### 21.3 Specification delivery validation

The specification-only PR #6 was finalized against main `ecc0364cc7462d5257e210c26a97117d2d58eb5d` and is now merged. Its documentation checks were separate from implementation validation. The subsequent authorized Phase 5 branch starts at `f5e779b68cd8449ec94fabc50a34ca134c6a0f87` and requires complete final-head PostgreSQL 17/backend/frontend/migration/build/security CI. See [implementation validation](phase5-validation.md); historical green runs do not validate a newer head.

## 22. APPROVED PRODUCT POLICY — PD5-01 through PD5-14

**All PD5-01 through PD5-14 below are APPROVED PRODUCT POLICY**, explicitly approved by the user on 3 October 2026: Option A for each decision, with the PD5-14 clarification. Each approved-policy paragraph is authoritative for Phase 5 V1; alternatives are retained only as decision history and are unapproved. The inherited Phase 4 PD-01 through PD-07 constraints in section 21.1 remain mandatory and unchanged. Specification PR #6 is merged, and a subsequent explicit instruction authorized Phase 5 implementation on the dedicated review branch. Phase 6 remains NOT authorized. Later changes to product policy require explicit authorization; measured operational-default tuning is permitted only within the approved PD5-14 safeguards. Deferred retention/compliance policy is a separate future decision, not an unresolved PD5 approval.

### PD5-01 — APPROVED OPTION A: Completeness state model

- **Approved product policy:** Use deterministic COMPLETE / INCOMPLETE evidence completeness at issuance, with financial currentness, review, integrity and lifecycle represented as separate orthogonal states. Do not use a numerical confidence score.

- **Decision question:** How should issued evidence completeness be represented alongside financial/review/lifecycle states?
- **Reviewed options (A selected; B/C unapproved):** (A) COMPLETE/INCOMPLETE at issue, with ABSENT/failure outside issuance and separate currentness/review/integrity axes; (B) one combined complete/needs-review/stale/dismissed status; (C) a numerical confidence score.
- **Approved option/rationale:** A. Deterministic C01–C10 and orthogonal axes describe why complete historical evidence can be stale or dismissed without rewriting history. Scores cannot replace approvals.
- **Downside/tradeoff:** More domain fields and carefully composed executive labels than a single badge.
- **Implementation impact:** Immutable check/gap record; distinct dynamic overlays and tests for combinations rather than an overloaded enum.
- **Security/financial impact:** Prevents false financial/legal reassurance; no confidence-derived monetary authority or stale warning suppression.

### PD5-02 — APPROVED OPTION A: Blocked and nonpositive packages

- **Approved product policy:** V1 may issue distinct explanatory evidence packages for blocked, no-overcharge and undercharge assessments. These must not receive monetary finding identity or be represented as positive leakage proof. Unknown money remains null, never zero.

- **Decision question:** Should V1 issue evidence packages for blocked, zero and negative assessments?
- **Reviewed options (A selected; B/C unapproved):** (A) Yes, distinct explanatory kinds without finding IDs; (B) positive findings only; (C) generate blocked packages but classify them as monetary proofs.
- **Approved option/rationale:** A. Users can inspect why money is unknown or no positive finding exists; a blocked explanation can itself be complete. C is incompatible with financial semantics.
- **Downside/tradeoff:** More outcome-specific presentation and completeness fixtures; packages must not inflate finding counts.
- **Implementation impact:** Kind/outcome mapping and different C03–C08 expectations for blocked explanation; null comparison preservation.
- **Security/financial impact:** No missing-evidence-as-zero inference, fabricated monetary claim or uncertain claim exported as settled.

### PD5-03 — APPROVED OPTION A: Human approval of proof completeness

- **Approved product policy:** Technical proof completeness is determined automatically by deterministic C01–C10 requirements. Owner/admin human proof review is a separate optional/audited state. Technical completeness must never imply legal certification, financial confirmation or recovery.

- **Decision question:** Must an owner/admin approve a package before its technical evidence completeness can say COMPLETE?
- **Reviewed options (A selected; B/C unapproved):** (A) System C01–C10 decides completeness; owner/admin review is a separate optional state; (B) owner/admin signature also required for COMPLETE; (C) analyst decides completeness from a subjective checklist.
- **Approved option/rationale:** A. Financial inputs already require PD-01 approval, while reproducible technical completeness must not depend on another subjective approval. Final monetary confirmation remains Phase 4.
- **Downside/tradeoff:** Users need clear “complete evidence” versus “reviewed/confirmed” labels; a complete package may not have human proof review.
- **Implementation impact:** Automated deterministic checks plus separately audited owner review; no amount/approval mutation.
- **Security/financial impact:** Completeness never conveys legal certification, finding confirmation or authority to analysts; inherit owner/admin financial approval unchanged.

### PD5-04 — APPROVED OPTION A: Generation timing and request roles

- **Approved product policy:** Proof assembly is on demand for owner/admin/analyst. Viewers may read already issued authorized proofs but cannot trigger proof generation. Generation must be bounded, idempotent and must not create or recalculate financial truth.

- **Decision question:** When should packages be generated and who may initiate deterministic assembly?
- **Reviewed options (A selected; B/C unapproved):** (A) On demand by owner/admin/analyst; viewer reads already issued packages; (B) automatically after every evaluation plus on-demand retry; (C) owner/admin on demand only.
- **Approved option/rationale:** A. Avoid hidden storage/work and preserve existing synchronous architecture; an analyst request copies already authorized truth and grants no financial approval.
- **Downside/tradeoff:** First authorized view may need explicit generation/wait; viewers cannot cause missing-package generation themselves.
- **Implementation impact:** Bounded synchronous assembly, request UUID and semantic deduplication; no background queue requirement. Financial CURRENT versus explicit HISTORICAL mode remains visible.
- **Security/financial impact:** Current membership checks, bounds and audit; no viewer mutation or silent evaluation generation.

### PD5-05 — APPROVED OPTION A: External sharing

- **Approved product policy:** External/vendor/public sharing is OUT OF SCOPE for Phase 5 V1. No public share tokens, vendor accounts, supplier dispute communications or external delivery workflows.

- **Decision question:** Is vendor/external/public sharing part of V1?
- **Reviewed options (A selected; B/C unapproved):** (A) No; tenant app and current-authorized internal downloads only; (B) expiring public links; (C) vendor accounts plus communication workflow.
- **Approved option/rationale:** A. Identity, disclosure authority, recipient handling and dispute communications require separate policy; existing tenant boundary is reusable.
- **Downside/tradeoff:** No integrated vendor delivery; an authorized downloaded file can leave the platform outside its access controls.
- **Implementation impact:** No share tokens, public endpoints, recipient/account/communication entities or sends.
- **Security/financial impact:** Clear download confidentiality notice; redaction still needed, downloaded bytes cannot be revoked remotely. No vendor claim is automatically asserted.

### PD5-06 — APPROVED OPTION A: App, JSON and PDF scope

- **Approved product policy:** Phase 5 V1 supports the internal in-app proof experience and canonical machine-readable JSON proof manifest/export. PDF generation is deferred. Do not introduce a PDF dependency in V1.

- **Decision question:** Which viewing/export formats should V1 provide?
- **Reviewed options (A selected; B/C unapproved):** (A) Internal app plus canonical JSON download; defer PDF; (B) app only; (C) app, JSON and PDF now.
- **Approved option/rationale:** A. Machine-verifiable manifest and internal drill-down are the minimum rigorous deliverable; section 14 defines later PDF expectations without adding a renderer now.
- **Downside/tradeoff:** JSON is less convenient for nontechnical sharing; C requires render/version/pagination/confidentiality work and visual QA.
- **Implementation impact:** Versioned JSON artifacts with exact byte hashes; no PDF library/rendering dependency in the approved V1.
- **Security/financial impact:** Final-stream authorization/private staging and current export context; all formats preserve money/nulls and limitations, no format implies legal certification.

### PD5-07 — APPROVED OPTION A: Redaction

- **Approved product policy:** Redaction uses separately versioned disclosure/presentation views. Never edit or mutate the canonical internal proof or underlying evidence. Analyst may prepare redaction proposals where allowed; owner/admin approves disclosure. Redaction must not produce misleading evidence.

- **Decision question:** How should sensitive content be withheld without falsifying internal evidence?
- **Reviewed options (A selected; B/C unapproved):** (A) Separately versioned owner/admin-approved field-path disclosure views for app/JSON; (B) forbid redacted exports; (C) edit the canonical proof/source in place.
- **Approved option/rationale:** A. Preserve complete internal truth and disclose the exact limitation of a partial view. C violates immutability and is unavailable.
- **Downside/tradeoff:** Partial recipients may not verify the complete root/provenance; exact recursive leakage controls and owner review increase effort.
- **Implementation impact:** Inert analyst proposals, exact approval/predecessor/reason, view fingerprint/profile and artifact identity; no binary original/PDF redaction in V1.
- **Security/financial impact:** No hidden original content in attachments/metadata/annotations; critical hidden evidence means limited independent verification, never misleading completeness or monetary edits.

### PD5-08 — APPROVED OPTION A: Retention, deletion and legal erasure

- **Approved product policy:** Preserve evidence referenced by authoritative historical proof under existing integrity/delete safeguards. Do not invent a universal retention period or implement automatic legal erasure in Phase 5 V1. Retention duration, legal holds, jurisdictional deletion, tenant offboarding and backup erasure require a later explicit compliance/legal policy. Do not claim permanent retention or regulatory compliance.

- **Decision question:** What approved policy governs proof/source/artifact retention and exceptional deletion?
- **Reviewed options (A selected; B/C unapproved):** (A) V1 preserves referenced evidence under existing delete guards; no ad hoc purge or invented duration; approve a jurisdiction/contract/tenant legal-retention profile before implementing expiry/erasure; (B) fixed guessed duration for all tenants; (C) unrestricted user deletion of historical evidence.
- **Approved option/rationale:** A. Ordinary historical immutability is inherited. Actual legal retention duration, erasure obligations, holds, backup lifecycle and authorized tenant-offboarding rules are new and need product/legal approval; this spec does not infer them.
- **Downside/tradeoff:** Stored evidence grows; production retention compliance is unresolved until an approved profile exists. Do not advertise permanent reproduction or guaranteed regulatory compliance.
- **Implementation impact:** Preserve guards and availability observations; no automatic deletion job now. A later approved erasure design must enumerate originals, excerpts, manifests, redactions, exports, logs and backups plus residual lawful audit.
- **Security/financial impact:** Financial records cannot be quietly rewritten/deleted; mandated destruction may remove reproduction capability and personal data inside hashes/actor identifiers/excerpts must be assessed. No unapproved hidden retained copy.

### PD5-09 — APPROVED OPTION A: Annotation/review authority

- **Approved product policy:** Owner/admin/analyst may append attributed nonfinancial annotations under role controls. Analysts may prepare review/redaction proposals. Owner/admin retain final authority for proof review, disclosure/export and explicit successor relationships. Proof annotations can never modify financial amount, financial evaluation, approved facts, source evidence, financial decision or rule behavior.

- **Decision question:** Which roles may add nonfinancial annotations and change proof review/disclosure?
- **Reviewed options (A selected; B/C unapproved):** (A) Owner/admin/analyst append attributed annotations; analysts propose redaction/review; owner/admin finalizes proof review, disclosure, exports and successor relations; viewers read; (B) owner/admin only for all commentary; (C) analysts finalize financial decisions through proof actions.
- **Approved option/rationale:** A. Support existing analyst review duties while keeping distinct final authority; C conflicts with PD-01.
- **Downside/tradeoff:** Moderation/history/disclosure review needed; comments may contain sensitive assertions and cannot silently become canonical evidence.
- **Implementation impact:** Separate revisioned annotations with actor/time/reason, inert text and length bounds; current permission matrix and trusted audit events.
- **Security/financial impact:** No HTML/log injection, amount/source/approval/decision edit, impersonation or unapproved exported sensitive annotation.

### PD5-10 — APPROVED OPTION A: Historical/current and supersession semantics

- **Approved product policy:** Historical proof remains immutable and visible. Currentness, finding decision and evidence availability are separate overlays. Do not infer supersession solely from timestamps. Use explicit, authorized same-scope successor relationships when needed. New evidence never silently changes an old proof.

- **Decision question:** How should stale evaluations and successor packages appear?
- **Reviewed options (A selected; B/C unapproved):** (A) Preserve complete-at-issue; show currentness/decision/availability separately; explicit authorized same-scope successor relations; (B) newest timestamp automatically supersedes old packages; (C) hide/delete stale packages.
- **Approved option/rationale:** A. Existing scoped financial currentness is inherited; new explicit relationship/review presentation must not invent financial succession. B/C lose audit meaning.
- **Downside/tradeoff:** Several badges/history relations and explicit owner work; a new evaluation can exist before a successor relation is approved.
- **Implementation impact:** Read Phase 4 currentness, actual decision history, observed-at overlays; same-scope/currency identity, cycle/conflict/predecessor guards for explicit relations.
- **Security/financial impact:** No unnoticed reopening, double counting, old amount replacement, age-based obsolescence or cross-scope/tenant successor leakage.

### PD5-11 — APPROVED OPTION A: Manifest fingerprint and trust

- **Approved product policy:** Use a versioned deterministic canonical Proof Manifest core with SHA-256 fingerprinting and a domain-separated canonicalization profile. Keep the canonical financial/evidence fingerprint, issuance metadata, artifact hashes and redacted disclosure hashes logically separate. Do not introduce blockchain, PKI notarization or claims of legal authenticity.

- **Decision question:** Which reproducibility and integrity profile should V1 use?
- **Reviewed options (A selected; B/C unapproved):** (A) Section 9's versioned canonical core SHA-256/domain prefix, trusted stored issuance record, separate artifact/disclosure hashes; (B) hash arbitrary rendered JSON including timestamps; (C) mandate external PKI/blockchain/legal notarization now.
- **Approved option/rationale:** A. Deterministic semantic content and explicit trust boundaries are sufficient; this new canonical profile is approved; the existing financial fingerprint remains unchanged.
- **Downside/tradeoff:** Independent Unicode/string/order/typed-value conformance tests required; unsigned exports alone do not prove who issued them.
- **Implementation impact:** Versioned schema/assembly registry, core/envelope boundary, canonicalizer and source-byte verification; no invented evaluation-time deployment digest.
- **Security/financial impact:** Tampering detected against trusted records, no hash-as-authenticity/legal certification promise; restricted original core remains private when a view is redacted.

### PD5-12 — APPROVED OPTION A: Regeneration and versioning

- **Approved product policy:** Repeated generation of the same semantic proof must resolve to the same proof content identity where appropriate. A new rendering/export artifact does not create a new financial proof. A new immutable proof content revision is allowed only for an explicitly defined proof-layer reason such as repaired evidence availability, proof schema evolution or proof assembly evolution, without changing the underlying financial evaluation. Material financial input changes require a new Phase 4 evaluation. Never overwrite historical proof.

- **Decision question:** What should repeat generation or evidence availability repair create?
- **Reviewed options (A selected; B/C unapproved):** (A) Return same semantic package; new artifact for format/context changes; new immutable content revision only for explicit repaired gaps/schema/assembly changes; (B) new package/core for every request timestamp; (C) overwrite existing package.
- **Approved option/rationale:** A. Financial inputs/evaluations remain immutable and request + semantic idempotency avoid duplicates. C is forbidden by history requirements.
- **Downside/tradeoff:** Exact version/identity rules and old-renderer availability need maintenance; restoration repair is an explicit operation rather than a button silently rewriting history.
- **Implementation impact:** Unique family/schema/assembly/core hash, request conflicts, predecessor expectations; separate financial, proof, render and disclosure versions. Distinct financial inputs require new Phase 4 evaluation.
- **Security/financial impact:** Concurrent duplicate issuance has one event; no mixed snapshots/hidden mutation; lost or mismatched source cannot become an unverified replacement.

### PD5-13 — APPROVED OPTION A: Aggregate proof/report

- **Approved product policy:** Phase 5 V1 supports individual assessment/finding proof packages only. Do not implement aggregate proof/report persistence or a new aggregate monetary finding. Existing dashboard aggregates remain presentation views subject to Phase 4 non-overlap and currency rules.

- **Decision question:** Does V1 issue combined cross-evaluation proof reports?
- **Reviewed options (A selected; B/C unapproved):** (A) Individual packages only; existing compatible totals remain views; (B) aggregate manifest referencing disjoint package IDs; (C) standalone new monetary aggregate finding.
- **Approved option/rationale:** A. Phase 4 scope/non-overlap/currency rules are inherited, while new aggregate disclosure/deduplication is additional product scope. C is incompatible with duplicate-finding prevention.
- **Downside/tradeoff:** Reviewer opens multiple packages for allocated periods; no single portfolio export.
- **Implementation impact:** Preserve scope/currency/parent allocation bindings for later extension, without aggregate persistence/export/engine now.
- **Security/financial impact:** No double counted combined rules, mixed-currency sum, unrelated undercharge netting or totals mistaken for new findings/recovery.

### PD5-14 — APPROVED OPTION A WITH CLARIFICATION: Operational size and work limits

- **Approved product policy:** Adopt the section 16 profile as initial safe engineering defaults: request JSON 1 MiB; annotation text 4,000 characters; maximum 500 calculation-driving revisions; maximum 100 original source documents; maximum 5,000 proof bindings; canonical JSON 10 MiB; maximum 100 MiB cumulative source-byte reads per operation; 25-second synchronous work budget; 100 history records per page; maximum two concurrent proof operations per tenant; maximum ten new generation/export operations per actor per rolling minute. These are NOT financial-policy invariants. They are versioned operational safety defaults and may be tuned later based on measured performance, production load testing, enterprise usage and infrastructure capacity, provided tuning does not silently truncate proof, suppress valid financial amounts, weaken authorization, weaken tenant isolation, weaken integrity, alter financial calculations or convert incomplete proof to complete proof. When a valid proof exceeds a limit, return an explicit bounded-resource result/error rather than truncating financial/evidence content.

- **Decision question:** Which finite V1 resource profile should apply before performance evidence is available?
- **Reviewed options (A selected; B/C unapproved):** (A) Section 16's approved bounded profile with versioned engineering-default clarification, explicit errors and existing upload limits; (B) unbounded generation/export; (C) silently truncate large valid scopes.
- **Approved option/rationale:** A with the approved clarification. Finite defaults bound synchronous work and storage while explicit errors preserve valid financial results. Defaults are versioned engineering safety settings that may be tuned using measurements and capacity evidence only within the approved safeguards. Original upload configuration remains unchanged.
- **Downside/tradeoff:** Some financially valid large evaluations cannot produce a V1 complete package under this profile; show the exact bound/reason rather than truncate or invalidate their finding.
- **Implementation impact:** Admission/work/byte/count limits, cancellation/private cleanup and Retry-After, idempotent retries; use existing execution architecture rather than invent a distributed queue. Measured future tuning is a versioned operational change, not a financial policy revision; the effective profile must remain diagnosable/auditable and cannot weaken the approved safeguards.
- **Security/financial impact:** Prevent resource exhaustion and partial-complete output; no upload limit widening, hidden financial data loss, unauthorized expensive viewer operations or arbitrary amount suppression.

**Stop condition:** PD5-01 through PD5-14 remain approved product policy. Specification PR #6 is merged; Phase 5 V1 was subsequently explicitly authorized and implemented on `phase5/leakage-proof-engine`. Stop after complete final-head validation and the unmerged implementation PR/report. Do not merge automatically. Phase 6 has not started and remains unauthorized.
