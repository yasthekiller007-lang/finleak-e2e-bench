# Phase 2 implementation and validation

Validated on 2026-10-02 in the published Financial Leakage AI cloud workspace. The starting checkout was clean, synchronized with `origin/main` at `c85c7ee6f30f09e65dfb6772cd130095b3391849`, with foundation commit `7282776e6de588c6cb0419114a1a18ff7a785dd1` present through merged PR #1. The existing Next.js/FastAPI/PostgreSQL/storage architecture was preserved. All 63 backend foundation tests remain present and pass; existing health, financial precision, tenant foreign-key, and storage assertions were preserved. Frontend assertions for the old login/documents placeholders were replaced with stronger tests for the authorized workflows they now implement. Phase 2 changes are local and uncommitted; this task did not request publishing them.

## Authentication architecture and configuration

Stable NextAuth/Auth.js 4.24.15 supplies the standard OIDC authorization-code flow with PKCE, state, nonce, ID-token verification, encrypted HttpOnly session cookies, and CSRF-protected login/logout. It was selected to avoid implementing credentials or OAuth protocols ourselves and to use a stable release compatible with the existing Next.js 16 application. The Next.js server forwards the API access token from the encrypted session; public session JSON excludes API tokens, and browser Authorization headers cannot substitute for the session cookie.

The reusable FastAPI authenticated-user dependency independently verifies JWT signatures using PyJWT/JWKS, an explicit asymmetric algorithm allowlist, issuer, API audience, expiry, issued-at, subject, and optional not-before. The default is RS256; ES256 and other supported asymmetric algorithms are configurable. HMAC and unsigned tokens are rejected. Discovery checks the exact issuer and secure JWKS URL, refuses redirects, and uses PyJWT's key cache/controlled rotation refresh. Optional explicit JWKS configuration is supported. Token-provided key URLs are ignored. Invalid tokens return safe 401 responses; missing/unavailable configuration returns 503.

Auth0 is the intended first production provider, with no SDK or provider endpoint assumptions in the implementation. Backend variables are `OIDC_ISSUER_URL`, `OIDC_AUDIENCE`, optional `OIDC_JWKS_URL`, and optional `OIDC_SIGNING_ALGORITHMS`. Frontend variables are `OIDC_ISSUER_URL`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `NEXTAUTH_URL`, `NEXTAUTH_SECRET`, optional `OIDC_AUDIENCE` authorization parameter, and optional `OIDC_SCOPES`. API selection through scopes is supported without an audience request parameter. Register `/api/auth/callback/oidc` with the provider. Use a distinct API audience and frontend client ID. Production requires HTTPS. Credentials are empty in the environment templates and belong only in secure runtime configuration or ignored local environment files.

No real production provider exists, as confirmed by the user. Automated tests generate temporary keys in memory. Factory-injected test verifiers require the explicit `test` environment; the ordinary deployed application has no test-user header, fake login route, token-minting endpoint, or environment switch that installs test auth. A temporary external OIDC fixture was used only by an out-of-repository live-validation script and was stopped afterward. This exercises the real protocol and cryptographic checks; it does not bypass the application verifier.

## Database and authorization

Migration `0002_identity_membership_uploads.py` follows the unchanged initial migration:

- Adds `user_identities` with unique `(issuer, subject)` and a user foreign key/index. Repeated/concurrent login maps to one internal user; email never links accounts.
- Makes user email nullable/nonunique profile data. Existing email-only users are preserved and require explicit reconciliation to identities.
- Preserves organization/user membership uniqueness; adds owner/admin/analyst/viewer roles and maps legacy member to analyst.
- Adds nullable `documents.uploaded_by` referencing users. Null preserves historical records; new API uploads always record the verified user.
- Replaces the checksum index with unique `(organization_id, sha256)`.
- Adds purchase_order/credit_note document types and queued processing status; new uploads remain pending.
- Keeps UUIDs, timezone-aware timestamps, tenant composite foreign keys, Decimal/NUMERIC financial conventions, and all unrelated financial entities unchanged.

Upgrade refuses existing same-organization duplicate documents instead of discarding them. Downgrade refuses identity, uploader, role, classification, status, or email data it would lose. Empty disposable databases can downgrade/upgrade normally. Legacy populated data that is compatible with the foundation is tested through upgrade, downgrade, and upgrade again.

Every document request resolves membership from the verified internal user and the database. Organization IDs select a membership lookup; frontend organization/role claims grant no authority. Owner/admin/analyst may upload; viewer may list/read/download. Missing/invalid identity is 401, viewer mutation is 403, and inaccessible/unknown organizations or documents are 404 with safe errors. Membership revocation takes effect on the next request with the same token. Database-operator CLI commands create organizations and grant/update memberships for an already verified identity. No public grant API or self-enrollment exists.

## APIs and frontend

| Backend endpoint | Result |
| --- | --- |
| `GET /api/v1/me` | Verified profile, authorized organizations/roles, upload limit |
| `POST /api/v1/organizations/{organization_id}/documents` | Authorized multipart upload; 201 or same-tenant duplicate 409 |
| `GET /api/v1/organizations/{organization_id}/documents` | Authorized list; limit 1–100, offset at least 0 |
| `GET /api/v1/organizations/{organization_id}/documents/{document_id}` | Authorized metadata |
| `GET /api/v1/organizations/{organization_id}/documents/{document_id}/content` | Authorized private attachment |

Next.js provides `/api/auth/[...nextauth]` and matching `/api/organizations/.../documents` proxy routes. Proxy paths are restricted to UUIDs, browser credentials are not forwarded, upload Origin must match the configured app origin, and response headers are restricted. Workspace routes are explicitly dynamic so runtime auth configuration cannot be replaced by a build-time placeholder. Login handles configured/unconfigured providers and safe failure messages. Documents supplies verified organization context, role-aware controls, classification, client validation, actual upload progress, backend errors, paginated filename/type/status/date metadata, and authorized downloads. A new user without membership sees a clear administrator-access state. No customer financial examples or AI analysis UI were added.

## Upload and storage controls

Authorization precedes multipart parsing. Uploads accept one file and one classification. The default file limit is 20 MiB; configure `FLA_MAX_UPLOAD_BYTES` consistently on both processes. Server and proxy count received body bytes independently of Content-Length, with 1 MiB bounded multipart overhead. Empty/oversized/unsupported files are rejected before object publication.

Extensions and exact MIME types must match PDF, UTF-8 CSV, or XLSX. PDF header/EOF and CSV encoding/syntax are checked. XLSX validation bounds entries and total uncompressed size, rejects traversal, encrypted members, macros, and unsupported compression, checks required workbook parts, and uses defused XML. These checks validate containers without extracting financial data; they do not establish malware safety.

Filenames are normalized and restricted to safe basenames without paths/control characters, including encoded traversal/control characters. Multipart normalization of Windows browser paths is tested. Storage keys are generated from organization/document UUIDs, never filenames. The existing private `ObjectStorage` interface calculates SHA-256 while streaming and enforces the size cap again. Metadata returns audit/checksum/size/type/status/date, with no storage key or public object URL. A failed transaction/duplicate compensates the object write; another tenant may upload identical bytes independently. Content requires membership and uses attachment, nosniff, no-store, and sandbox headers. Logs retain safe request metadata rather than tokens, secrets, or document bodies.

## Exact validation results

| Check | Result |
| --- | --- |
| Complete saved cloud install script (`uv sync --locked`, `npm ci`, both DB upgrades/checks) | Exit 0; reproduced dependencies and schemas |
| Backend `ruff check .` and `ruff format --check .` | Passed; 51 Python files formatted |
| Backend `pytest -q` with real isolated PostgreSQL | **153 passed, 0 failed, 0 skipped** |
| Frontend `npm run lint` and `npm run format:check` | Passed |
| Frontend `npm run typecheck` | Passed |
| Frontend `npm test` | **27 passed across 4 files, 0 failed, 0 skipped** |
| Frontend `npm run build` | Passed; all workspace routes dynamic |
| PostgreSQL test DB downgrade base → upgrade head → Alembic check | Passed, no schema drift |
| PostgreSQL application DB upgrade head → Alembic check | Passed, no schema drift |
| Isolated legacy-schema migration tests | 3 passed; preserve records, refuse duplicate upgrade and destructive identity downgrade |
| Concurrent first-login race against PostgreSQL | Passed; one user/identity, no orphan |
| Live OIDC + development backend/frontend requests | **17 checks passed** |
| Live production backend + `npm start` | **10 checks passed** |
| `git diff --check` and generated-file review | Passed; generated dependencies/builds/local configuration excluded |
| Versionable-file secret pattern scan and environment template review | No findings or populated secret placeholders |

The live OIDC checks covered real discovery, authorization-code exchange, PKCE/state/nonce, HttpOnly encrypted session creation, token-free public session JSON, verified identity mapping, authorized workspace rendering, CSV upload through the browser proxy, correct checksum/status/uploader, metadata listing, attachment content, duplicate 409, tenant-ID substitution 404, cross-origin upload 403, wrong-audience/expired token 401, and signout clearing API access. PDF/CSV/XLSX positive cases, all classifications, malicious filenames, malformed files, actual streamed limits, viewer denial, tenant-isolated detail/content, pagination, database failure compensation, and JWT claim/signature failures execute in the automated suites.

The production smoke checks verified PostgreSQL readiness, login redirects for all four workspace routes, honest missing-provider UI, unavailable auth configuration 503, anonymous browser/backend API 401, and supplied-bearer rejection when provider configuration is absent. Development, production, and OIDC fixture servers were stopped after validation; the prepared PostgreSQL instance was also stopped. Live validation rows were removed from the disposable test database, without modifying application data.

New locked runtime dependencies include NextAuth/Auth.js 4.24.15, PyJWT 2.15.1, cryptography 50.0.2, python-multipart 0.0.32, defusedxml 0.7.1, and httpx2 2.13.1 moved from dev to runtime for discovery. Existing pinned Next.js/React/Node/Python/PostgreSQL versions remain as recorded in the foundation validation report. npm retains the existing ESLint 9 deprecation warning; lint itself passes.

## Files changed

Configuration and documentation:

- `.env.example`, `frontend/.env.example`, `.github/workflows/ci.yml`
- `README.md`, `docs/architecture.md`, this validation report
- `backend/pyproject.toml`, `backend/uv.lock`, `frontend/package.json`, `frontend/package-lock.json`

Backend:

- `app/core/config.py`, `app/db/models.py`, `app/domain/types.py`, `app/main.py`
- `app/auth/__init__.py`, `app/auth/oidc.py`, `app/auth/dependencies.py`
- `app/api/me.py`, `app/api/documents.py`, `app/modules/upload_validation.py`, `app/admin.py`
- `migrations/versions/0002_identity_membership_uploads.py`
- `tests/__init__.py`, `tests/identity_fixtures.py`, `tests/test_identity.py`, `tests/test_identity_concurrency.py`
- `tests/test_documents.py`, `tests/test_upload_validation.py`, `tests/test_admin.py`, `tests/test_phase2_migration.py`

Frontend:

- `src/app/login/page.tsx`, `src/app/(workspace)/layout.tsx`, `src/app/(workspace)/documents/page.tsx`
- `src/app/error.tsx`, `src/app/(workspace)/error.tsx`, `src/app/globals.css`
- `src/app/api/auth/[...nextauth]/route.ts`
- `src/app/api/organizations/[organizationId]/documents/route.ts`
- `src/app/api/organizations/[organizationId]/documents/[documentId]/route.ts`
- `src/app/api/organizations/[organizationId]/documents/[documentId]/content/route.ts`
- `src/components/auth-buttons.tsx`, `src/components/document-workspace.tsx`
- `src/lib/auth-config.ts`, `src/lib/auth-server.ts`, `src/lib/backend.ts`, `src/lib/backend-proxy.ts`, `src/lib/documents.ts`
- `tests/foundation.test.tsx`, `tests/auth-proxy.test.ts`, `tests/documents.test.tsx`

CI still runs frozen installs, checks, all tests, production build, schema drift, and disposable migration reversibility. New tests are discovered by the existing test runners; no tests are disabled.

## Limitations, technical debt, and next work

No real Auth0 tenant or production provider acceptance test exists. Configure the client/API, secure runtime credentials, allowed callback/logout URLs, and exact provider/discovery/JWKS network destinations when available. The saved cloud draft contains tested install/start instructions and runtime-variable requirements without values; saving did not publish a snapshot, restart the environment, or prove restoration in a new task. Current network rules were preserved, with no guessed provider domains. Application/session secrets need raw secure process values, not network-proxy secret placeholders.

Access-token refresh, immediate provider-token revocation/introspection, account-linking/migration administration, public invitations/membership management, broader RBAC, API/concurrency throttling, malware scanning, managed S3 storage, object encryption/retention/backup operations, and full audit/event history are deferred. Large uploads are bounded but multipart spooling still needs disk/quota monitoring. A process crash between object publication and metadata commit can leave an orphan; failed compensation deletion needs a reconciliation/retry lifecycle. SQL tenant filters and composite foreign keys provide the current isolation boundary; PostgreSQL row-level security is not installed. Health readiness checks the foundation table rather than every migration, so use Alembic drift checks. This is a validated development milestone, not a completed production rollout.

Before customer rollout, connect a real provider and complete those operational requirements. The next product phase should define versioned extraction candidates and provenance, add controlled queued processing and failure/retry behavior, and specify the first deterministic contract/invoice rule with exact Decimal calculations. Phase 3, OCR, extraction, LLM calls, leakage detection/compiler/proof/recovery systems, integrations, billing, and recovery automation were not started.
