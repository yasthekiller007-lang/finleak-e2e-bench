# Phase 5 V1 — implementation and validation

Updated 3 October 2026. Historical implementation starting main: `f5e779b68cd8449ec94fabc50a34ca134c6a0f87`, including merged specification PR #6. Historical implementation branch: `phase5/leakage-proof-engine`. Phase 5 was explicitly authorized after specification approval. Current merged status: [PR #7](https://github.com/yasthekiller007-lang/financial-leakage-ai/pull/7) is merged into main at `a881e2248419dfc98cf68239485edde327240431`, including the validated final implementation `3cac668cde6d2368210de5662c84f66048487920`. Phase 6 is unauthorized and has not started.

The complete code checkpoint `b9fd325782a8c341f312a5b38675acd0858ad9c5` passed [PostgreSQL 17.11 and frontend CI run 37105946049](https://github.com/yasthekiller007-lang/financial-leakage-ai/actions/runs/37105946049): **516 backend tests, 86 frontend tests, no backend skips**, and all configured checks. Documentation was finalized afterward. The final delivery and implementation PR record the exact final branch head and its own complete green CI; the code checkpoint alone does not validate a later head. [Branch CI history](https://github.com/yasthekiller007-lang/financial-leakage-ai/actions?query=branch%3Aphase5%2Fleakage-proof-engine) provides the corresponding run records.

## Policy and scope preservation

[Phase 4 business policy](phase4-business-spec.md) is byte-identical to starting main, SHA-256 `1ee9eebf9ca81496f616c8bf55e64389341141762a501c3ec91fa654bb99fe09`. Phase 4 engine, service, typed financial schema, rules and the original 35-vector tests are unchanged. The only Phase 4 model addition is a composite uniqueness constraint on normalized evidence identity for proof foreign keys; migration 0005 applies it. Historical migration tests compare their own phase's exact metadata rather than including later proof tables.

PD5-01 through PD5-14 remain approved Option A, including the PD5-14 clarification. Their approved-policy paragraphs and the inherited PD-01–07 policy table are unchanged. Specification edits only update execution/handoff metadata and label preimplementation observations as historical. No financial amount, rule, family, interpretation, recovery process or legal/compliance policy was added.

## Architecture and persisted identities

The proof collector consumes one immutable `FinancialEvaluation`, its exact frozen snapshot and the pinned calculation-driving/guard revisions. It never calls match, compile, `run_engine` or financial evaluation to rebuild historical money. The existing financial fingerprint helper is used only to check the frozen semantic input digest. Existing scoped `is_stale` supplies a separate currentness overlay; it does not recalculate an amount.

| Record | Identity and responsibility |
| --- | --- |
| `proof_families` | Unique tenant/evaluation/kind anchor. Positive findings use the existing evaluation UUID; informational/blocked evidence has no monetary finding UUID. |
| `proof_packages` | Immutable core/envelope, content fingerprint, issued completeness, numbered predecessor/reason. Semantic uniqueness returns the first issued content/envelope on retry. |
| `proof_bindings` | Tenant-safe links to historical normalized revision evidence, document/run/field and exact input pointer. Existing evidence IDs are reused; missing normalized evidence uses the specified deterministic binding digest and yields an explicit gap. |
| `proof_events` | Append-only attributed annotation, proposal/final review, disclosure, download and source-integrity observations. Revisions/retractions use explicit predecessors and sequence numbers. |
| `proof_artifacts` | Completed private canonical JSON bytes, exact SHA-256, parent package and optional approved disclosure. A rendering is not another financial proof. |
| `proof_requests` | UUID request key, semantic request digest, original result, quota participation and trusted operation audit. Changed meaning conflicts without overwriting the original. |
| `proof_successors` | Owner/admin explicit relationship between distinct evaluations of the same known invoice scope, members, currency, unit and period. No cycle, fork, timestamp supersession or monetary edit. |

Migration 0005 adds these seven tables, composite tenant/evidence/audit foreign keys, immutable/authorization/integrity triggers and proof-referenced source deletion/identity guards. Financial audit is reused through trusted nested trigger origins; direct journal insertion remains forbidden. Downgrade refuses any persisted proof or proof audit, including failed operations. Empty disposable upgrade/downgrade/re-upgrade and schema comparisons pass. Legacy users/documents are preserved.

## Canonical content and exact evidence

Versions are `proof-manifest/1`, `proof-assembly/1`, `proof-canonical/1`, `proof-completeness/1`, `proof-disclosure/1`, `proof-json/1` and `proof-operations/1`. Historical `financial-snapshot/1`, `reviewed-compiler/1` and `core-bundle/1` are recognized exactly; unknown versions are explicit completeness gaps or safe failures, never nearest-version financial recomputation.

Canonical UTF-8 has no BOM/trailing LF/whitespace, scalar-ordered keys, preserved Unicode and decimal-string scale, lowercase `\u00xx` control escapes and literal U+2028/U+2029. Duplicate keys, floats, numeric exponents, nonfinite numbers, surrogate code points and unsupported types fail safely. Source decimal strings and database six-place amounts remain exact.

| Digest | Exact input |
| --- | --- |
| Manifest | SHA-256 of `FLA-PROOF-MANIFEST/1` + LF + canonical core. Issuance envelope and live overlays are excluded. |
| Frozen snapshot | SHA-256 of `FLA-EVALUATION-SNAPSHOT/1` + LF + canonical entire stored snapshot, including original contextual entries and array order. |
| Fallback binding | SHA-256 of `FLA-PROOF-BINDING/1` + LF + the specified revision/pointer/document/hash/run/field/support/location tuple. |
| Disclosure | SHA-256 of `FLA-PROOF-DISCLOSURE/1` + LF + canonical disclosed view, including parent fingerprint and approved disclosure identity, excluding its own hash/export context. |
| Artifact/source | SHA-256 of exact exported/original bytes; neither is financial confirmation or issuer/legal authentication. |

Independent byte vectors, PostgreSQL/Python canonical agreement and fixed F02 manifest/snapshot golden digests are tested. Set-like proof collections have deterministic ordering; the complete frozen snapshot preserves historical array order. Random issuance IDs/times, filenames, annotations and current overlays cannot alter semantic content identity.

| Requirement | Implemented enforcement |
| --- | --- |
| C01 | Exact tenant, invoice source, evaluation and scope identity; scoped queries and composite FKs. |
| C02 | Exact stored outcome/reason/currency/E/A/Δ/P, financial semantic fingerprint and recorded trace consistency. Unknown remains null; no fabricated intermediate or arithmetic conclusion. |
| C03 | Every driving/guard revision and scalar leaf is mapped to its historical reviewed value, support pointer and citation. Missing bindings produce named gaps. |
| C04 | Historical actor/time/state/cutoff/reason and trusted review audit; approval role at action time is distinct from today's membership. |
| C05 | Frozen governing packet, document hashes, association, selected terms/dates/scope and applicability. A known absent schedule has no fabricated document. |
| C06 | Copied recorded expression/trace/precision/rounding alternatives/actual bridge/credits and typed operands. No current financial evaluator call. |
| C07 | Bounded reads of every available original against pinned SHA-256 and size. Missing bytes yield INCOMPLETE; mismatched bytes fail generation and are quarantined on presentation. |
| C08 | Financial blockers, uncertainties, invariance and scope/location limitations remain visible. A complete blocked explanation has no monetary claim. |
| C09 | Frozen provenance agrees with normalized evidence, document, run/field/path/raw/normalized lineage and support. Contradictions fail safely. |
| C10 | Pinned profiles, deterministic manifest digest, immutable envelope and atomic trusted issuance audit. Database also checks financial/core/envelope identities. |

Issued COMPLETE/INCOMPLETE is immutable. Currentness CURRENT/STALE/UNKNOWN, finding decision, human review, source availability and explicit successor are separate overlays with observation times. Missing source, dismissal, rerun or later approval never rewrites old proof. Ordinary regeneration returns existing content; identical-byte availability repair requires explicit predecessor/reason and resolves only C07 gaps. Schema/assembly evolution requires a newly released version, not a client-selected override.

## Source bytes, operations and concurrency

Storage opens regular files without following symlinks/FIFOs. Verification hashes bounded chunks and checks actual length and SHA-256. Original and artifact downloads verify and capture the bytes they serve before response; source absence/mismatch never serves replacement or partial verified bytes. Generic document downloads enforce the same source-integrity boundary. No storage path/key or signed/public source URL enters the manifest.

PostgreSQL organization locking reuses Phase 4 lock order. Current membership is re-read under share lock and held through capture/commit; historical revisions/documents are locked consistently. All proof endpoints, including paged histories, use shared admission; each summary refreshes the remaining database/work budget. Operation admission uses transaction-scoped advisory slots across workers; actor quota uses an actor-wide advisory lock across tenants. Statement/lock timeouts, elapsed-work checks, savepoint rollback and safe transaction-retry responses prevent partial issuance. Commit fences preserve the exact evaluated immutable revisions and current-mode context. Filesystem writers cannot participate in PostgreSQL transactions: an actual hash-bound capture proves the bytes observed, and later downloads reverify them.

Independent PostgreSQL transactions test same/different simultaneous request keys, one semantic proof/issuance audit, approval correction/revocation, governing packet revision/revocation, association revocation, membership changes before/during generation, two shared slots and final-review/disclosure CAS races. Existing Phase 4 simultaneous evaluation/stale-revision tests remain intact. A source changed during capture produces MISMATCH and no captured download bytes. Failure after assembly rolls back package/artifact/audit before recording the failed operation through a trusted origin.

## Roles, disclosure and internal product experience

Owner/admin/analyst can explicitly generate and append nonfinancial annotations. Analysts may prepare review/disclosure proposals. Viewers read issued authorized packages/source evidence and cannot generate. Owner/admin alone finalize human proof review, approve disclosure, export/download private JSON artifacts or create explicit successors. Current tenant membership is always required; authorization never comes from request-body actor/role claims. Financial confirmation/dismissal remains the existing Phase 4 action.

Annotations are inert escaped text with attributed append/revision/retraction history; they cannot change financial inputs/results, source evidence, completeness or rules. A human review is a separate audited opinion, never legal certification or financial approval.

Disclosure proposals pin exact scalar paths and prior proposal identity. Approval pins an attributed proposal. A separately versioned view conservatively masks full/partial/case-varied duplicate values, dynamic keys, sibling fields and export-context metadata. Original evidence/binding/evaluation digests are withheld to avoid disclosing hidden evidence through hash oracles; simple derived-value hashes are masked too. The required parent manifest reference remains a linkage to the private trusted original, not a claim that the redacted view can reconstruct the full core.

Canonical core/envelope, original source binaries, annotations, free-text review/disclosure reasons, filenames and unrelated frozen context are not included as unredacted companions to the view. Attributed approval identity/time is masked when necessary; its free-text reason remains in private history. Recursive validation covers the **entire final view/export**, not just selected core fields. A disclosure that cannot preserve required metadata without exposing a hidden value fails with a generic controlled error. The disclosed completeness section explicitly says LIMITED_VERIFICATION and identifies the internal issued state separately. Disclosure/view hash and final byte checksum are separate. Artifact metadata/download headers use generated UUID filenames and contain no original source filename.

Private JSON artifacts freeze context-as-of, actor, profile and confidentiality notice; later download does not claim the saved context is current today. Database guards reject changed canonical core/envelope even if an attacker recomputes an artifact checksum. Source/artifact download authorization and integrity observations are audited. No PDF dependency, public token, external delivery or vendor dispute flow exists.

The UI provides an executive exact-money/reason summary, current/stale/dismissed/review/source warnings, contractual versus billed basis, complete recorded calculation, typed reviewed inputs, machine raw/normalized lineage, honest manual citations, verified originals, C01–C10 gaps/limitations, versions/fingerprints, content revisions and paged history. Generation is explicit and lazy, with CURRENT/HISTORICAL choice; role controls and errors preserve visible historical amounts. Annotation, proposal/final review, exact-path disclosure approval, JSON export/history and successor controls use the authenticated server proxy. Lists/bindings are paginated with bounds rather than truncating the canonical proof.

## Versioned operational defaults

| Bound | Initial `proof-operations/1` default |
| --- | --- |
| Actual request JSON | 1 MiB |
| Annotation | 4,000 characters |
| Driving/guard revisions | 500 |
| Original source documents | 100 |
| Proof bindings | 5,000 |
| Canonical JSON/export | 10 MiB |
| Cumulative source reads | 100 MiB per operation |
| Synchronous work | 25 seconds |
| History page | 100 records |
| Tenant concurrent operations | 2 across workers |
| New generation/export requests | 10 per actor per rolling minute across tenants |

Optional `FLA_PROOF_LIMITS` JSON records profile version and actual values with issuance. These are engineering defaults, not financial invariants. Safe tuning requires measurement and versioned configuration; it cannot truncate content, suppress money, weaken authorization/isolation/integrity, change calculations or promote incomplete proof. Limits return explicit 413/429/503 resource/retry results and preserve financial truth. Idempotent existing-content/request retries do not count as new generation.

## Worked-example and regression mapping

The original 35 Phase 4 vectors remain unchanged. The new pure collector suite explains each vector from a fixed captured historical fixture and checks exact copied output/null/finding semantics and immutable snapshot. It constructs historical fixture truth before collection; production proof assembly never evaluates it.

| Example | Implemented test coverage |
| --- | --- |
| WP-01, F02 | Exact 18.40/20.10/43,647; E 803104.800000, A 877304.700000, P 74199.900000; fixed manifest/snapshot goldens. |
| WP-02, F01 | Exact zero comparison, null potential/finding identity; informational API/UI package. |
| WP-03, F03 | Exact negative discrepancy, no finding/potential; no netting. |
| WP-04, F06 | Complete fixed-cycle fee 400 copied; full cycle/date/trace in bindings. |
| WP-05, F04 | Missing unconditional discount 4,000; contractual eligible base has contract-source evidence. |
| WP-06, F27 | One combined 300 finding/evaluation anchor; no duplicate financial result. |
| WP-07, F12 | Amendment-selected applicable price and effective-date evidence copied. |
| WP-08, F14 | Crossing period without allocations remains blocked/null. |
| WP-09, F15 | Currency mismatch remains a blocked explanation; typed source currencies retained. |
| WP-10 | Known missing governing schedule yields COMPLETE explanation, unknown money, no invented document. |
| WP-11, F26 | Material rounding alternatives retained; comparison outputs remain null. |
| WP-12, F21 | Allocated credit affects the copied actual bridge once; no inferred recovery. |
| WP-13 | Subsequent dismissal retained as overlay; historical core/output unchanged. |
| WP-14 | New approved input/new evaluation/new proof; same-scope explicit successor, cycles/conflicts rejected. |
| WP-15 | New extraction run and filename change do not replace pinned historical lineage or identity. |
| WP-16 | Actual-byte mismatch prevents trusted issuance/download; old completeness survives with audited mismatch overlay. |
| WP-17 | Reviewed manual/document-level citation can be complete, labeled honestly without invented coordinates. |
| WP-18 | Cross-tenant package/evaluation/history/source/artifact queries return no victim content; composite tenant constraints. |
| WP-19 | Same/different simultaneous keys produce one package/content/issuance audit; retries reproduce first result. |
| WP-20 | Analyst proposal, owner approval, duplicate/partial/metadata/hash masking, private export checksum and current-role download. |
| WP-21 | Invariant rounding alternatives retained separately; one-cent positive result remains 0.010000. |
| WP-22 | Missing identical original restored through explicit new content revision; old incomplete proof/evaluation unchanged; stale CAS fails. |
| WP-23, F32 | Real reviewed parent/segments create two COMPLETE packages, 320.000000 and 60.000000; two evaluations, no persisted aggregate proof/finding; cross-period successor fails. |

Tests: [collector/goldens](../backend/tests/test_proof_assembly.py), [canonical/source/redaction](../backend/tests/test_proof_canonical.py), [proof API/security/lifecycle](../backend/tests/test_proof_api.py), [independent PostgreSQL races](../backend/tests/test_proof_concurrency.py), [migration](../backend/tests/test_phase5_migration.py), [UI](../frontend/tests/proof-workspace.test.tsx), [proxy](../frontend/tests/proof-proxy.test.ts). Existing financial, document intelligence, auth, storage, migration and frontend suites remain present.

## Structured security review

Reviewed the actual backend/SQL/proxy/UI paths and regression evidence, fixed discovered migration naming/CASE and redaction metadata/hash issues, then reran complete CI. The review is scoped engineering verification, not a penetration-test, legal or regulatory certification.

| Check | Result and guard |
| --- | --- |
| 01 Cross-tenant proof | Scoped evaluation/family/package queries and composite FKs; generic inaccessible 404. |
| 02 Cross-tenant evidence | Historical normalized evidence/document/run/field agreement; no latest foreign-tenant fallback. |
| 03 Cross-tenant artifact | Package/disclosure/organization FKs, owner/admin download and tenant-scoped lookup. |
| 04 Viewer mutation | Backend current-role gates and database insert guards; UI/proxy never grant authority. |
| 05 Analyst escalation | Final review/disclosure/export/successor owner/admin-only; proposal/annotation rights separate. |
| 06 Export authorization | Fresh locked membership at generation/download; source capture/audit committed before response. |
| 07 Disclosure leakage | Entire export recursively validated; duplicate/partial strings, metadata, keys and original/derived digests masked; generic failure if unsafe. |
| 08 Source paths/keys | Internal storage abstraction; no path/key/credential in manifest, response or operation log. |
| 09 Manifest secrets | Minimal scoped cited evidence; no session/token/email/default bank fields/full unrelated documents. Sensitive citations remain private and disclosure-controlled. |
| 10 Audit forgery | Trusted trigger-origin extension reuses immutable financial journal; direct forged INSERT rejected. |
| 11 ID enumeration | Inaccessible/missing IDs indistinguishable; denied output contains no victim amount/hash/source. |
| 12 Filenames/disposition | Generated UUID export filenames, quoted original download disposition, nosniff/sandbox/no-store; proxy discards unsafe backend disposition. |
| 13 Source reads | Cumulative chunk-read bound, actual SHA/length, regular files, work deadline; no unverified streaming. |
| 14 JSON work | Actual body-byte guard before parse, strict JSON, canonical limit, bounded lists/bindings/revisions. |
| 15 Stale membership | Backend re-read with populate-existing and share lock, not cached role or proof actor. |
| 16 Mid-operation role change | Independent connection race proves revocation waits through authoritative commit/capture. |
| 17 Source mismatch | Initial mismatch rejected; historical mismatch overlay/audit/quarantine; original/artifact bytes rehashed on download. |
| 18 Mixed state | Common organization lock order, pinned immutable rows, final currentness fence, safe transaction rollback/retry. |
| 19 Idempotency race | Unique family/fingerprint/request constraints and concurrent same/different UUID tests; one issuance audit. |
| 20 Successor abuse | Exact known same scope/currency/period, distinct evaluations, unique edges, cycle rejection; F32 cross-period link rejected. |
| 21 Annotation authority | Extra financial fields forbidden, inert text, append-only revisions/retractions; canonical core/output unchanged. |
| 22 Completeness/legal | Automatic technical requirements; separate optional human review; limitations disclaim certification/confirmation/recovery. |
| 23 Historical mutation | Database UPDATE/DELETE refusal, immutable envelope/core/evaluation, forged financial artifact rejection and explicit revision/repair rules. |
| 24 Floats | Strict canonical/JSON rejection and typed exact decimal strings; unchanged Phase 4 Decimal arithmetic. |
| 25 PDF provenance | Recorded page/line/cell or manual citation only; no fabricated box/OCR/byte-offset/verbatim verification. |
| 26 Phase 6 | No recovery ledger, communications, public delivery, firewall/payment control or new financial family. |

## Financial-integrity review

| Invariant | Verified result |
| --- | --- |
| No Phase 4 amount/rule change | Engine/service/schema/policy/original financial vectors byte-identical; all previous financial tests pass. |
| No recalculation | API test forbids engine evaluation/run_engine during collection; assembler only copies, validates and hashes frozen records. |
| Deferred rules stay blocked | All 35 original vectors retain exact outcomes; no new family or legal interpretation. |
| Unknown versus zero | Blocked comparison E/A/Δ/P null; true zero discrepancy preserved as 0.000000. |
| Undercharge not netted | Negative discrepancy copied; potential/finding identity null; no aggregate monetary proof. |
| Combined/non-overlap | One coherent evaluation/finding anchor; F32 two disjoint packages and no third claim. |
| Confidence not authority | Reviewed revision/audit/support required; raw/normalized candidate and reviewer meaning separate. |
| COMPLETE not approval | Technical completeness fixed at issue; current finding decision and human review separate. |
| Human proof review not approval | Final proof event never writes financial revision, evaluation or decision. |
| Stale stays historical | Explicit HISTORICAL generation; original money/fingerprint retained; currentness overlay only. |
| Dismissed stays historical | False-positive decision remains visible; no regeneration/reactivation or core edit. |
| New evidence cannot mutate proof | Rerun/renaming leaves old content; financial change requires Phase 4 revision/evaluation; identical-byte repair is a separate explicit content revision. |

## Actual validation and remaining boundary

| Validation | Actual result |
| --- | --- |
| Local backend | Ruff lint/format; pytest 297 passed / 219 PostgreSQL skips; no local database workaround. |
| PostgreSQL code CI | PostgreSQL 17.11; 516 tests passed without skips on `b9fd325`; complete job successful. |
| Frontend | 86 tests in 10 files; npm ci/lint/format/TypeScript/production build passed in CI; local checks also passed. |
| Migration | Upgrade/head, no schema drift, disposable downgrade/base, re-upgrade/head and second no-drift check; legacy preservation and populated-history refusal tests passed. |
| Benchmark | 16 synthetic documents, 73/73 required fields, 128/128 evidence checks, zero fabricated missing fields/failures; no unseen-document accuracy claim. |
| Secret scan | 183 source files, zero findings; bounded pattern coverage. |
| Documentation | Relative links, 23 examples/14 decisions/20 historical risks, unchanged approved policy/inherited financial table, whitespace and byte-identical Phase 4 checks. |
| Final implementation head | `3cac668cde6d2368210de5662c84f66048487920` passed complete [CI run 37106226636](https://github.com/yasthekiller007-lang/financial-leakage-ai/actions/runs/37106226636) and [PR CI run 37106454115](https://github.com/yasthekiller007-lang/financial-leakage-ai/actions/runs/37106454115). Historical checkpoint evidence above remains unchanged; no earlier green head is substituted. |

No production deployment, real OIDC-provider browser acceptance, production load test, legal retention policy or compliance certification is claimed. Synchronous limits and tenant serialization constrain throughput; stronger operational storage/monitoring and larger enterprise workloads require measured follow-up. Manual citations require human interpretation and do not certify legal authenticity. Conservative redaction may refuse unsafe/ambiguous disclosures. Future proof schema/assembly evolution must be explicitly versioned; no evaluation-time deployment digest is fabricated.

PDF generation, external/vendor/public sharing, supplier communications, aggregate proof persistence, new financial families, universal retention/legal erasure, Recovery Ledger, Firewall and Leakage DNA remain deferred. Phase 6 has not started. PR #7 is merged; this report records the validated implementation and does not authorize production deployment or later phases.

## Changed implementation areas

- Backend proof domain: `app/proof/{canonical,budget,schema,models,assemble,service}.py`, package initialization, proof API and main/config/model registration.
- Integrity/audit integration: document byte downloads, storage regular-file capture, structured proof logs, normalized financial evidence composite uniqueness.
- Database: migration `0005_leakage_proof_engine.py`; exact historical Phase 3/4 migration metadata tests.
- Tests: proof collector/canonical/API/concurrency/migration suites and frontend proof workspace/proxy suites.
- Frontend: proof types/server proxy/route/workspace; explicit entry from existing financial detail/cards.
- CI: dedicated Phase 5 branch runs the existing complete application matrix.
- Documentation: this validation report, HANDOFF and specification execution metadata. Approved policy, dependency lockfiles and financial calculations are unchanged.
