# Product V1.1 — isolated development acceptance

This is product development acceptance, not Phase 7 qualification. The prepared suite has not been run against OIDC/PostgreSQL in the current Work Cloud: those services are absent. Browser screenshots from `/demo` are synthetic exercises, never authentication or persistence evidence.

## Existing services required, with no provisioning

Use an already-authorized, disposable Cloud development environment only. No PC, CI/GitHub Actions, paid resources, production, privileged role, scanner, importer or PITR. The harness starts no service and creates no database, issuer, cloud resource or workflow. It does not change migrations, permissions, financial rules or auth guards.

1. CPython 3.12 and the existing `backend/uv.lock` environment; Node 24 and existing `frontend/package-lock.json`.
2. A dedicated, empty, already-created PostgreSQL **17** database named `finleak_product_v11_test`, reachable on loopback from the Cloud test processes, with the existing Alembic migrations at head. Use the existing migration procedure under a separately authorized migration role; the harness never runs it. Application/fixture credentials must not have SUPERUSER, CREATEROLE or CREATEDB. No role/permission changes are performed by the harness.
3. An already-running OIDC **test realm** on loopback, supporting discovery, authorization code + S256 PKCE, state, nonce, RS256, proper API audience and JWKS. It must contain two exclusively synthetic accounts. Do not reuse the user's identity. No fake token verifier, cookie injection, password grant, header impersonation or mocked JWKS is used by this suite.
4. The existing backend configured in `FLA_ENVIRONMENT=test`, the dedicated `FLA_DATABASE_URL`, `OIDC_ISSUER_URL` and `OIDC_AUDIENCE`; scanner remains unconfigured. Point `FLA_STORAGE_ROOT` to `.local/product-v11/originals` (absolute path) for the manual fixture documents.
5. An already-running existing frontend with its normal NextAuth settings and `BACKEND_URL`. Loopback HTTP OIDC is accepted only by the existing development-mode configuration; do not weaken production HTTPS rules. The test configuration has **no `webServer` or service-launch hook**.

## Private runtime configuration

Set these through the authorized Cloud process environment, never in a tracked file or chat:

- `PRODUCT_V11_ACCEPTANCE=1`, `PRODUCT_SYNTHETIC_ACCOUNTS_ONLY=1`, `FLA_ENVIRONMENT=test`.
- Existing `FLA_DATABASE_URL`, `OIDC_ISSUER_URL`, `OIDC_AUDIENCE` and standard frontend NextAuth/OIDC settings.
- `PRODUCT_OWNER_SUBJECT`, `PRODUCT_ANALYST_SUBJECT`: the two synthetic subjects in the test realm.
- `PRODUCT_OWNER_USERNAME`, `PRODUCT_OWNER_PASSWORD`, `PRODUCT_ANALYST_USERNAME`, `PRODUCT_ANALYST_PASSWORD`: test accounts only.
- `PRODUCT_FRONTEND_URL`: loopback frontend origin, normally `http://127.0.0.1:3000`.
- `PRODUCT_PYTHON`: absolute path to the backend's Python 3.12 executable.
- Optional test-issuer form labels: `PRODUCT_OIDC_USERNAME_LABEL`, `PRODUCT_OIDC_PASSWORD_LABEL`, `PRODUCT_OIDC_SUBMIT_NAME` (defaults Username / Password / Sign In). The suite verifies the issuer origin before filling credentials.

No bearer token, cookie, authorization code, client secret or password belongs in evidence. Automatic network traces, video and auth screenshots are off. The reporter exports fixed test titles/statuses without raw error messages. The only screenshot explicitly taken is inside the synthetic application after authentication, never on the provider page.

## Execution, only when services are already authorized and available

From `backend`, run `.venv/bin/python -m acceptance.product_v11 preflight`. A BLOCKED result exits 2 before seeding; it never becomes E2E PASS. A `PREFLIGHT_ONLY` result demonstrates dependencies only, not authentication.

Run `.venv/bin/python -m acceptance.product_v11 seed` once. It refuses an existing roster or nonempty identity/organization database. It creates only synthetic organizations, two synthetic identities/memberships, and manual document fixtures in development storage. The documents remain `needs_review`; no scan result, release, extraction, financial source, review, evaluation or final decision is injected. This explicit test-only fixture is not an import validation or a source-availability qualification.

From `frontend`, run `npm run test:product-e2e`. The prepared Playwright suite uses the already-running frontend/backend/issuer and normal encrypted NextAuth cookies. It then:

- Logs in through the actual test issuer UI as owner and analyst; the backend validates access tokens with its normal issuer/audience/JWKS path.
- Rejects anonymous access and an inaccessible synthetic organization.
- Creates reviewed sources through the existing financial API.
- Uses the analyst to prepare each term/packet/billing/association record; rejects analyst approval, then approves through owner API calls with the actual predecessor.
- Evaluates **100 units × USD 50 = USD 5,000** against **100 × USD 60 = USD 6,000**, asserting exact strings and a USD 1,000 potential discrepancy under the existing unit-price/tax/date/rounding rules.
- Uses Invoices → recorded evidence → the real decision form; requires a reason and rejects an analyst's financial confirmation.
- Reads the committed decision and financial audit; reloads the browser and checks the reason/actor from the existing audit API.
- Rejects replay using the stale predecessor with HTTP 409.
- Calls a separate Python interpreter that opens a fresh PostgreSQL session, checks exactly one decision and its audit, and writes a synthetic-only witness.
- Revokes an approved term while retaining its recorded value through the authorized review endpoint, verifies that the original evaluation becomes stale and that another decision is rejected without changing the historical amount.

The roster and output live under ignored `.local/product-v11`. No fixture is auto-deleted, no immutable database record is rewritten and no migration downgrade/drop is attempted. Retain the synthetic evidence for review; discard the dedicated development environment only through its owner's authorized lifecycle.

## Additional evidence still required

The current delivery has no OIDC session, PostgreSQL witness or persisted decision log. Their evidence files explicitly say NOT EXECUTED. The suite is prepared and typechecked, not presented as executed.

After a successful run, verify `browser-results.json` and `persisted-decision.json` together; a preflight, fixture seed or SQL read alone is not E2E PASS. For a backend-process restart, restart only the dedicated authorized development process using its existing supervisor, then repeat the same read-only `witness --evaluation UUID --decision UUID` command and reread the UI. The harness never restarts unknown services and does not claim a restart happened automatically.

Expired/invalid real issuer tokens require the test provider's supported short-lived/invalid-audience test-token setup. A real PostgreSQL outage/rollback requires a separately controlled disposable service failure and restoration. These scenarios remain NOT VERIFIED here. Frontend transport-failure fixtures test conservative UI behavior; they are not evidence of an actual PostgreSQL outage. No production token or database is used to fill those gaps.

Phase 7 / PostgreSQL-PITR / ClamAV-WSL remain NOT QUALIFIED; scanner BLOCKED; pilot NO-GO; PC and production NOT AUTHORIZED.
