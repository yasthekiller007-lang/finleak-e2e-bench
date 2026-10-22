# FINLEAK P0 — executable development acceptance candidate

Status: preparation delivered; **first GitHub Actions execution BLOCKED**.
The user reports 1,000 remaining minutes but an Actions $0 budget with `Usage blocked`.
The scope of that UI label (paid overages versus the proposed included job) is
not established. `usage_blocked` in the guard document denotes an effective job
block; it is not a badge parser. A protective paid-usage block is never removed
to make a run possible. No authenticated account/billing/permission evidence was
obtained in this mission.
No repository, branch, budget or workflow was created or modified on GitHub.
No job, PostgreSQL process/container, product E2E or migration was executed here.

## Source and executable files

Original V2.3 ZIP SHA-256:
`bf7f05fe0720dcce9dd3d3d553a95a5ec9f56ee3d93b4861f2e03bd4c29aebc8`.
Original commit: `951c4a13d5f4bef37ae694e44e680a4bdf816d19`.
All 479 archive manifest entries and all 425 original source files were verified.
The original Git objects were recovered only after reproducing their exact hashes
from original archives/patches. Main and all prior refs remain unchanged.

- `finleak-p0.yml`: candidate outside the active workflow directory; manual only,
  one standard `ubuntu-24.04` job, hard timeout 10 minutes, zero retries/matrix.
- `prepare_repository.py`: creates a local reviewable bench projection, never pushes.
- `gate.py`: actor, manual event, first attempt, approved exact commit, fresh scoped
  billing review and original-source checks. These validate a reviewed document;
  they do **not** query or guarantee GitHub billing or grant execution permission.
- `runtime.py`: bounded PostgreSQL/OIDC/backend/frontend orchestration and cleanup.
- `runtime-grants.sql`: dedicated ephemeral runtime grants; no production role change.
- `oidc_provider.py`: disposable loopback authorization-code provider, RS256 JWKS,
  S256 PKCE, exact redirect, state transport, nonce-bound ID tokens, confidential
  client authentication, one-use expiring codes and bounded authorization sessions.
- `witness.py`: independent READ ONLY native PostgreSQL session and audit checks.
- `frontend/p0-acceptance/financial.spec.ts`: actual browser-session scenario.
- `frontend/playwright.p0.config.ts`: one Chromium worker, no retries, no service
  startup during discovery, no traces/video/screenshots containing credentials.
- `pins.json`, `provenance/`, `v23-source.sha256`: immutable descriptors and source locks.

The existing `acceptance.product_v11` source-only fixture and business helpers are
reused unchanged. They create only synthetic identities, memberships and documents.
All preparation, approval, association, evaluation and decisions use existing APIs.
No decision, financial revision, evaluation or proof package is seeded directly.

The complete offline SQL export stops at historical migration 0002, which reads
existing rows via a real connection. That is preserved and documented; no migration
was altered. Revision graph discovery and the isolated 0009:0010 offline SQL export
succeed. None of these static checks proves that the full chain runs natively.

## Exact future scenario and scope

1. Create PostgreSQL 17.11 on tmpfs using the official immutable linux/amd64 manifest.
   No image build, host volume, registry push, privileged container or sudo.
2. Create a non-superuser migration/fixture role and a separate application role.
   Apply the existing migrations through `0010` to **finleak_product_v11_test only**.
   Seed through the existing fixture, then restrict the application role: no database
   or table ownership, no role-management privileges, no DDL or membership-role update.
   Column `UPDATE(id)` permits PostgreSQL row locks; immutable triggers remain active.
3. Start the synthetic issuer, unmodified FastAPI factory and unmodified Next.js
   development server on loopback. HTTP is already allowed by development contracts;
   production HTTPS/authentication checks are not changed or disabled.
4. Login two synthetic accounts through the real NextAuth authorization-code flow.
   NextAuth validates ID-token signatures/issuer/audience/nonce/state/PKCE; the normal
   backend discovers JWKS and verifies its separate access-token signature/claims.
5. Review/approve the existing explicit unit-price fixture through the APIs:
   100 units × USD 50 = 5,000; actual USD 6,000; potential USD 1,000, exact Decimal.
6. Inspect invoice, anomaly, citations, source hashes and an issued proof package.
   **Sources remain UNSCANNED; source gate stays closed and proof is INCOMPLETE C07.**
   This validates preserved citations/provenance and the honest availability overlay,
   not machine extraction, real upload, scanned bytes or complete documentary proof.
7. Submit the first authorized financial decision through the UI. Playwright lets
   the real backend commit, then drops that HTTP response. Re-read explicitly; count
   exactly one POST and one persisted decision. No automatic write retry.
8. Verify native SQL decision and trigger-origin audit from a fresh read-only session.
   Reload the browser; restart FastAPI; use a **new OIDC browser session** and SQL
   session to retrieve the same decision. PostgreSQL itself is not restarted.
9. Submit two concurrent HTTP intents with the same predecessor: require 201/409
   and exactly two total append-only decisions, not three. Reject stale input after
   a source revocation. Keep proof review distinct from finding confirmation.

Negatives: anonymous/invalid token 401; another organization 404; analyst approval
and decision 403; missing reason 422; duplicate, concurrent and stale decision 409.
Expired signatures/audience/PKCE/replay are also tested at the provider/backend
HTTP protocol level during preparation. Those tests are not browser E2E evidence.

PASS requires the actual browser test, SQL witness, restart reread, audit and issuer
receipts to agree. FAIL records an applicable assertion/stage failure. BLOCKED records
missing permissions, resources, services or deadlines. A skipped/not collected/test
discovery result cannot become PASS. The original full frontend diagnostic remains
611 PASS / 1 historical FAIL; its proposed test migration remains NOT APPLIED.

## Resources, immutable inputs and limits

Official GitHub documentation currently lists private standard Ubuntu x64 runners
as 2 CPUs, 8 GB RAM, 14 GB SSD. This is a documentary sizing basis, not a measurement
of the future allocated runner. No larger-runner fallback exists.

| Component | Prepared bound or estimate |
| --- | --- |
| PostgreSQL | 768 MiB memory, 1 CPU, 128 PIDs, 128 MiB shm, tmpfs database |
| Next.js development | V8 old-space maximum 1,536 MiB; one server |
| OIDC + FastAPI | One process each; estimated combined <512 MiB, not qualified |
| Chromium | One headless worker; expected <1 GiB, not measured here |
| Admission | x64, ≥2 CPUs, ≥5 GiB available RAM, ≥7 GiB free disk |
| Stage reserve | Check ≥512 MiB available RAM and ≥2 GiB free disk before stages |
| Time | Hard job 10 minutes; executor stops at job start +510 seconds; no retry |

Cold dependency/browser/image downloads and dev compilation may exhaust the budget.
The executor refuses to start the scenario with <150 seconds left. A timeout or
resource failure stops this candidate; it never enlarges the machine or enables
privileges. Runtime peak memory and total duration remain NOT VERIFIED. VM teardown
is the final boundary if cancellation prevents hooks. Normal and rescue cleanup
target only process groups and the container carrying this run's private instance
label; no host files, arbitrary Docker resources or checkpoints are removed.

Python 3.12.15, Node 24.21.0, uv 0.12.19 and Playwright 1.63.0 are exact candidate
versions. Python/npm dependencies reuse the unmodified hash-bearing V2.3 lockfiles.
Actions are full-SHA-pinned. Registry index, amd64 manifest and config bytes were
independently hashed and PG_VERSION 17.11 checked. Image layers/runtime and the future
browser binary are not verified here. The GitHub runner image behind ubuntu-24.04
remains provider-managed and mutable; record its job metadata for reproduction.

Services bind loopback; browser routes reject external hosts; children receive an
environment allow-list without GitHub/cloud/production credentials. Dependency
installation and image/browser pulls require outbound public registry/vendor access.
There is no privileged firewall or assertion of complete network-egress isolation.
This is a development bench, not production least-privilege or Phase 7 qualification.

## Evidence and safe collection

No `upload-artifact`, cache or cloud-storage resource is used. Only bounded sanitized
JSON receipts are printed in Actions logs as base64 plus SHA-256. Download the run
logs later through the authenticated GitHub interface; decode/verify the receipts.
`result.json`, `browser.json`, `witness.json`, `checks.json` distinguish actual checks
and missing evidence. Passwords, signing keys, tokens, cookies, codes and nonce/state
values never enter these receipts. Raw process output is captured privately and
not exported. Initial/final preparation diagnostics are retained in this checkpoint.

First-run instructions and the separate approval boundary are in `FIRST-RUN.md`.

Maintained: E2E OIDC/PostgreSQL BLOCKED; migration 0010 NOT APPLIED here; native
PostgreSQL NOT VERIFIED; Phase 7/PITR/ClamAV NOT QUALIFIED; scanner BLOCKED; pilot
NO-GO; PC/production NOT AUTHORIZED. An eventual development PASS lifts none of them.
