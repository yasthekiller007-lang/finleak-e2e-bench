# Phase 7 H–I validation and evidence report

**Pilot: NO-GO.** H–I adds browser/fault/capacity engineering evidence and final traceability. The selected staging/provider/cloud/managed-restore/customer environment has not been qualified. Every P0-01–35 and AC7-01–35 remains **IMPLEMENTED / EXTERNAL EVIDENCE PENDING**; no gate is waived by CI. [Complete traceability](phase7-traceability.md) records each obligation.

Work resumed from GitHub checkpoint `14f175e9e5c62a252268fd773f807bd6eb293c2d` on `phase7/pilot-readiness-hardening` after verifying identical remote HEAD, no newer commits, successful [push CI 37216404898](https://github.com/yasthekiller007-lang/financial-leakage-ai/actions/runs/37216404898), and approved Phase 4–6 policy unchanged against merged main `4a0d2520d4713355cec8b143f233aa61e5e655cc`. A fresh checkout was reconstructed and verified against the complete GitHub tree. The previous local environment was not edited; B–G were retained.

## Exact-head evidence

The implementation PR delivery record records the final SHA and both complete successful push/PR run URLs. CI generates `phase7-qualification-{event}-{SHA}/qualification.json` only after every required job succeeds on an explicit checkout of that SHA. PR checks deliberately use the PR head, rather than an unreported synthetic merge tree. Both event receipts must agree for AC7-38 to resolve to PASS; a newer branch commit invalidates the receipt. Earlier checkpoints and local checks cannot establish final-head acceptance.

The receipt embeds test counts, browser versions/results, measured operation latency and sampled resources, plus date/tester/runtime/schema/profiles and limitations. Measurements vary by runner: use the receipt for the reviewed SHA, not values copied from another release. CI artifacts last 14 days; the PR retains durable identifiers and measured summary. Operators must preserve required external evidence under approved retention/access rules.

## Browser acceptance implementation

Playwright uses one sequential Chromium journey, four role checks, one no-membership/keyboard/forged-bearer check, one recovery-history fault check and Firefox login/logout smoke. Retries are disabled. Tests exercise the real UI, cookie-authenticated proxy, API, PostgreSQL 17 commit tracking and two API workers. Actual discovery/JWKS, code/PKCE/state/nonce and signed access/ID tokens use ephemeral fixture keys. This is a **synthetic provider**, not real OIDC-01–10 acceptance. HTTP loopback does not qualify production HTTPS/Secure cookies.

Only synthetic organizations/verified identities/memberships are seeded. Financial and recovery authority uses normal protected commands and database guards. Rich structured source/recovery proposal preparation uses the typed API; visible UI controls perform source approval, finding confirmation, proof generation and economic approval. No claim that every preparation field was manually entered in the browser is made.

The scanner fixture returns a synthetic clean response with the existing guard's accepted wire format. Its version is fixture data, not evidence that ClamAV ran in this journey. The fixture is excluded from production images and cannot be selected by runtime configuration. The separate scanner-conformance job executes the real private engine; deployed scanner/signature/containment qualification remains pending.

| Journey | Actual assertions and remaining scope |
| --- | --- |
| E2E-01/06/10 | Normal synthetic sign-in, no membership, four-role UI/server denials, cross-tenant denial, logout/cookie invalidation and keyboard activation. Actual roster/tenant switch, manual tab/error-focus/accessibility and provider SSO remain pending. |
| E2E-02/03 | Three exact CSV uploads; quarantine blocks processing/download; scan and separate owner release; identical original bytes; explicit extraction; reviewed term/packet/billing/association approval. Customer source meaning, duplicate/unsupported/old-run UI acceptance remains pending. |
| E2E-04/05 | Explicit evaluation: USD expected 1,000 / billed 1,200 / potential 200; confirmation preserves money; explicit COMPLETE C01–C10 proof and stable fingerprint. Broader null/currency/blocked/disclosure usability remains component/domain and external scope. |
| E2E-07/08 | Case starts R=0, C/S unknown; partial cash 60; issued credit 90 adds no R; applied credit 40 gives R=100/N=60/pending=50; economic cash return 20 gives R=80/N=40. Prior as-known report digest and proof fingerprint stay unchanged. Other profiles/costs remain domain-test scope. |
| E2E-09 | Lost scan response after commit retries with the same key/scan ID. Economic/proof/evaluation post-commit retry assertions are PostgreSQL tests, not browser response-loss claims. |
| FAIL-04 / AC7-35 | Synthetic history 503 after explicit inspection removes stale financial detail, approval controls and notice; backend R/N stays unchanged. Actual dependency outages and delivered alerts remain pending. |

Browser work exposed stale recovery detail after failed reloads. The workspace now clears detail/controls/notice on failure; component regressions and a browser fault test cover it. List and detail read failures have independent error state, so a successful companion refresh cannot erase an outage or restore monetary controls. Auth controls remain disabled until hydration attaches handlers so premature keyboard activation cannot silently do nothing. Budgeted Recovery reads run sequentially, and proof generation waits for initial history readiness, preserving the default tenant admission bounds. No financial authority changed.

## Fault and restore evidence

`phase7_fault_gate.py` rejects skipped/failed/error backend tests and requires the named passing PostgreSQL/component assertions mapped to FAIL-01–07 and FAIL-09–12. The receipt names exactly those assertions. This is **partial engineering coverage** of the staging fault plan; it does not claim every subscenario, before/after audit inspection or alert delivery was exercised through the chosen deployed runtime.

FAIL-08 requires the inherited separate restore-conformance job: genuine post-commit publication interruption, restart and actual isolated synthetic native backup restore, with original bytes, historical digests, roles/guards and logical-copy provenance rejection. It is not managed cloud restore. Actual managed backup/PITR/object reconciliation, loss window/recovery time and operator/deputy sign-off remain **EXTERNAL EVIDENCE PENDING**.

## Measured capacity qualification

Successful `capacity.json` and `resources.json` record actual observations, attributed to the tested SHA. The envelope is one synthetic company plus a negative tenant, three small CSV originals, one evaluation/proof/recovery case, six identities, two API workers and four simultaneous summary reads. HTTP p50/p95/max samples cover UI-triggered operations and protected API preparation/read/report requests; they exclude human review time.

Resource sampling observes the API process tree/parser descendants at 0.5-second intervals: resident memory, cumulative process CPU, dedicated PostgreSQL connections/lock waiters and local original bytes and parser temporary files, counted separately. The observer contributes a DB connection and brief peaks may be missed. Frontend/OS/SDK memory, cloud IO/WAL, sustained pressure and full disk capacity are unqualified. Exact-head qualification receipts contain sample count/duration/maxima and operation distributions.

**OBSERVED_SYNTHETIC_ENVELOPE_ONLY** is the result classification. No customer latency target, maximum dataset, throughput or SLA is invented. Shared admission/quota/timeouts are tested across independent PostgreSQL pools without increasing defaults to pass the browser journey. The fast browser flow deliberately reaches the unchanged ten-attempt intake limit: attempt eleven returns 429/Retry-After 60, leaves the clean original quarantined, keeps authentication/health usable, and succeeds only on explicit release retry after the real window expires. This is an observed boundary, not a throughput promise. The evidence does not justify Redis/Celery/Kafka or architecture expansion. Agreed customer extrema/thresholds, production-like sustained same/cross-tenant writes, bounded overload behavior and resource budgets remain required for P0-34.

## Final validation and preservation

CI retains B–G backend full PostgreSQL tests/lint/format/benchmark/secret scan/reversible disposable migrations; frontend lint/format/typecheck/tests/production build; both non-root runtime images; isolated real S3/private scanner/native restore conformance; pinned advisory/locked dependency/runtime inventory checks. Browser acceptance and exact-head receipt aggregation are additional required jobs. Aggregation rejects mismatched SHA, incomplete jobs/receipts, frontend/backend skips or missing measurements.

Preparatory local backend validation: 521 passed / 427 PostgreSQL skips. Local frontend: 120 passed plus lint/format/typecheck/build. These do not substitute for complete final-head CI. The new stale-history regression covers the UX fix. No financial/security guard was relaxed.

The preservation gate pins 28 approved specification/domain/migration files to the verified checkpoint. Approved Phase 4/5/6 specification SHA-256 values remain `1ee9eebf9ca81496f616c8bf55e64389341141762a501c3ec91fa654bb99fe09`, `1dac7eb8377322552e12cc0c87b49baaa60123e53938209bb7e98699415c6e2a`, and `02ca1dfc256ef08f5fd8bf921b2f9a65ac185ae3df40e765439a40063d2c60c0`. The original Phase 7 audit is also unchanged.

Only safe summaries are uploaded: originals, roster, PID, credentials, raw auth traces, screenshots/video and raw frontend/JUnit debug output are excluded. The fixed frontend receipt exports counts, not raw test bodies.

## External obligations and stop

The [35-row traceability table](phase7-traceability.md) is authoritative. Outstanding obligations include isolated deployed environments; managed PostgreSQL TLS/privileges/failover; real cloud originals IAM/version/encryption/durability; actual issuer/session/key/outage/revoke behavior and roster/offboarding; customer packets and domain approval; secrets/HTTPS/ingress/log controls; named staffed operators and delivered/acknowledged alerts; managed backups/restore/reconciliation/RPO/RTO; release/incident/deputy drills; deployed-image/advisory refresh; customer limits/data-handling/commercial acknowledgment; real browser/manual accessibility; full staged happy/fault paths and representative capacity thresholds.

AC7-36/37/39 engineering preservation/scope/safe evidence pass with final checks; AC7-38 needs matching successful push and PR receipts. AC7-40 remains BLOCKED. **No merge, production deployment, customer intake, Phase 8 or major architecture expansion is performed or authorized. Stop at the PR and evidence report.**
