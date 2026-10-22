# Financial Leakage AI

Evidence-led contract-to-invoice review with approved financial facts, deterministic leakage evaluation, immutable proofs and the Phase 6 V1 Recovery Ledger. Phases 1–6 are merged through PR #11 at main `4a0d2520d4713355cec8b143f233aa61e5e655cc`. Phase 7 pilot-readiness hardening is separately authorized and in progress on `phase7/pilot-readiness-hardening`; no production deployment or real customer pilot is claimed. See [current handoff](HANDOFF.md) and [Phase 7 execution decisions](docs/phase7-implementation-decisions.md).

## Repository

```text
frontend/                 Next.js App Router, TypeScript, shared UI, Vitest tests
backend/
  app/api/                Versioned health, identity, and protected document APIs
  app/core/               Environment configuration, JSON logging, error envelopes
  app/db/                 SQLAlchemy models, exact numeric types, sessions
  app/domain/             Money, tenant context, status enums
  app/modules/            Ingestion, extraction, matching, rules, calculations,
                          confidence, evidence, and object storage interfaces
  migrations/             Alembic migrations
  tests/                  Unit and PostgreSQL integration tests
docs/                     Architecture decisions and validation report
.github/workflows/ci.yml   Backend and frontend checks
compose.yaml              PostgreSQL only
.env.example              Configuration template; contains no real credentials
```

## Local development

Prerequisites: Python 3.12, uv 0.12.19, Node.js 24, npm, and Docker Compose v2 (or an existing PostgreSQL 17 instance). Exact dependency versions are retained in `backend/uv.lock` and `frontend/package-lock.json`.

From the repository root:

```sh
cp .env.example .env
```

Edit `.env`: choose a local development PostgreSQL password, and set `FLA_DATABASE_URL` with the matching username, password, database, and `postgresql+psycopg://` driver. URL-encode special characters. The template's `USER:PASSWORD` is a placeholder. Do not commit `.env`. Docker Compose requires a nonempty password.

```sh
docker compose up -d --wait postgres
cd backend
uv sync --locked
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log
```

In a second terminal, from the repository root:

```sh
cd frontend
npm ci
cp .env.example .env.local
# Configure the identity provider in .env.local before sign-in.
npm run dev
```

Backend settings and Compose read the root `.env`. Next.js reads its own directory's environment files or process variables. Copy `frontend/.env.example` into `frontend/.env.local` and configure it locally. `BACKEND_URL` is server-only and is never sent to the browser. No public frontend variable contains a credential.

Frontend routes: `/login`, `/dashboard`, `/documents`, `/leakage-cases`, `/settings`. `/` redirects to `/dashboard`. The workspace routes require a verified session and backend identity lookup. `/login` uses the external identity provider; it collects no passwords. Missing provider configuration fails closed and displays an administrator configuration message. Metrics show an unavailable marker rather than invented financial amounts.

Backend endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/health` | Application liveness, version |
| `GET /api/v1/health/ready` | Database connectivity and presence of the migrated organization table; 503 otherwise |
| `/docs`, `/openapi.json` | FastAPI-generated API documentation |

Health requests return `X-Request-ID`; API errors use an `error` envelope with code, message, and request ID. Readiness is a development startup check, not an exhaustive schema auditor. Use `alembic check` to detect model/schema drift.

Configuration uses the `FLA_` prefix: `DATABASE_URL`, `ENVIRONMENT`, `CORS_ORIGINS` (JSON list), `STORAGE_ROOT`, `LOG_LEVEL`, and `DATABASE_TIMEOUT_SECONDS`. Relative storage paths resolve against the repository root. CORS permits only configured origins, GET/POST with Authorization and no credentialed cross-origin browser requests. Omitting the database URL allows liveness, but readiness returns 503.

## Checks

Backend, from `backend/`:

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run alembic check
```

For PostgreSQL integration tests, use a separate disposable database:

```sh
# Run from the repository root once to create the test database.
docker compose exec postgres createdb -U financial_leakage financial_leakage_test
cd backend
# Substitute your local credentials; never use a production database.
export TEST_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/financial_leakage_test'
FLA_DATABASE_URL="$TEST_DATABASE_URL" uv run alembic upgrade head
uv run pytest -q
```

Without `TEST_DATABASE_URL`, PostgreSQL tests are explicitly skipped; unit tests alone do not validate migrations or database tenant constraints. Tests roll back fixture data and require an already migrated database. CI runs all tests against its disposable PostgreSQL service and verifies downgrade/upgrade of the migration chain there. Migration tests also verify legacy data preservation and refusal of destructive downgrades.

Frontend, from `frontend/`:

```sh
npm run lint
npm run format:check
npm run typecheck
npm test
npm run build
BACKEND_URL=http://127.0.0.1:8000 npm start
```

Format with `uv run ruff format .` in `backend/` or `npm run format` in `frontend/`. Stop application servers with Ctrl+C and stop local PostgreSQL with `docker compose stop postgres`; the development volume is retained.

## Phase 2 authentication and documents

See [architecture](docs/architecture.md) for tenant isolation, money, versioning, provenance, and extension points. [Validation](docs/validation.md) records exact versions, results, cloud startup details, limitations, and the file inventory for this milestone.

The frontend uses stable NextAuth/Auth.js 4 with generic OIDC discovery and authorization code, PKCE, state, and nonce. Backend tokens are independently verified against the configured issuer, API audience, expiry, and discovered JWKS. Auth0 is the intended first provider; no Auth0 SDK, tenant name, endpoint path, or organization claim is hard-coded. Configure an OIDC confidential web client with callback `/api/auth/callback/oidc` and logout destination `/login`. The API audience must be separate from the frontend client ID. RS256 is the default signing algorithm; `OIDC_SIGNING_ALGORITHMS` accepts a JSON allowlist of supported asymmetric algorithms only.

Set `OIDC_ISSUER_URL` identically for backend and frontend and configure backend `OIDC_AUDIENCE`. Frontend `OIDC_AUDIENCE` adds an audience authorization parameter when set (required for the intended Auth0 API); omit it for providers that select API tokens through scopes. Backend `OIDC_JWKS_URL` is optional: keys are discovered from the issuer when omitted. Frontend also needs `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, `NEXTAUTH_URL`, and a strong random `NEXTAUTH_SECRET` (at least 32 characters). Store real credentials in runtime settings or ignored local environment files, never the repository or browser variables. Production requires HTTPS identity and application URLs. The selected provider must issue JWT API access tokens. Requesting an API audience is configurable; providers using API scopes can configure `OIDC_SCOPES` instead. Tokens remain in encrypted HttpOnly session cookies and are forwarded to the API only by the Next.js server. Access-token expiry requires fresh sign-in; refresh tokens are deliberately not retained.

First verified sign-in creates an internal user keyed by issuer/subject and no memberships. Email is optional profile data and never links accounts. A trusted database operator provisions membership after sign-in, from `backend/`:

```sh
uv run python -m app.admin --actor-id VERIFIED_OPERATOR_USER_UUID --reason 'Approved enrollment' --apply create-organization --name 'Your organization'
uv run python -m app.admin --actor-id VERIFIED_OPERATOR_USER_UUID --reason 'Approved owner enrollment' --apply grant-membership --organization-id UUID --issuer ISSUER_URL --subject VERIFIED_SUBJECT --role owner
```

Use the same command to assign `admin`, `analyst`, or `viewer`; the grant updates an existing organization/user pair. This command requires privileged database access. No public membership-grant API exists. Existing email-only foundation users are not automatically attached to an OIDC identity; reconcile them explicitly rather than linking by email.

| API | Behavior |
| --- | --- |
| `GET /api/v1/me` | Verified user, authorized organizations/roles, upload limit |
| `POST /api/v1/organizations/{id}/documents` | Member with owner/admin/analyst role; multipart `file` and `document_type`; 201 or duplicate 409 |
| `GET /api/v1/organizations/{id}/documents` | All member roles; `limit` 1–100 and nonnegative `offset` |
| `GET /api/v1/organizations/{id}/documents/{document_id}` | Authorized metadata only |
| `GET /api/v1/organizations/{id}/documents/{document_id}/content` | Authorized private attachment stream |

Browser requests go through matching `/api/organizations/...` routes on Next.js using the session cookie; users never supply backend tokens in client code. Membership is checked in PostgreSQL on every backend request. Inaccessible and unknown tenants/documents return 404. Viewers can read/download but cannot upload (403). Unauthenticated/invalid tokens return 401. Missing or unavailable provider/database configuration returns 503.

Uploads accept PDF (`application/pdf`), UTF-8 CSV (`text/csv`), and XLSX (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`) with matching extensions and validated containers. The default limit is 20 MiB, configured with `FLA_MAX_UPLOAD_BYTES` on both processes. All uploads start `pending`; Phase 3 adds explicit, authorized processing and review states (see Document Intelligence below). Type is a user selection: contract, invoice, purchase order, credit note, or other. SHA-256 uniqueness is enforced per organization. Private storage keys are generated from organization/document UUIDs and never exposed in responses. Downloads require membership and use attachment, nosniff, no-store, and sandbox headers.

Migration `0002` preserves existing documents and money types, maps legacy `member` roles to `analyst`, makes email optional/nonunique, and adds unique external identities, uploader attribution, document types/status, and per-tenant checksum uniqueness. Upgrade refuses existing duplicate same-tenant documents. Downgrade refuses Phase 2 data it would discard; use a backup/reconciliation plan on populated databases. Test downgrade only on disposable databases.

See [Phase 2 validation](docs/phase2-validation.md) for exact results, file inventory, limitations, and next steps. No real provider tenant exists yet. Local/security fixtures use temporary signing keys; there is no application route, header, environment flag, or production shortcut that mints test tokens. A real provider rollout requires runtime configuration and provider-host network access, not a new authentication architecture. Phase 3 extraction is described below; matching and financial rules remain deferred.


## Phase 3 document intelligence

Contracts and invoices can be explicitly processed from Documents → Review. Inspect structured candidates, raw/normalized values, source evidence and immutable version history. Unknown or conflicting values remain unknown. Processing is synchronous and bounded; no OCR, live LLM calls, financial leakage detection, or authoritative entity creation occurs.

See [Document Intelligence](docs/document-intelligence.md), [Phase 3 validation](docs/phase3-validation.md), and the updated [handoff](HANDOFF.md). Run `uv run python -m app.intelligence.benchmark` in backend for the synthetic benchmark. Configure `FLA_PROCESSING_LIMITS` and `FLA_MAX_EXTRACTION_ATTEMPTS` only through environment settings. Database changes require complete PostgreSQL 17 CI.

## Phase 6 V1 Recovery Ledger (merged through PR #11)

The approved [Recovery Ledger policy](docs/phase6-recovery-ledger-spec.md) remains authoritative. See [architecture](docs/phase6-architecture.md), [validation](docs/phase6-validation.md) and [policy-to-code traceability](docs/phase6-traceability.md). One case anchors an immutable positive FinancialEvaluation. Manual protected evidence, reviewed proposals and owner/admin recognition preserve immutable economic allocations, credits, reversals, costs and historical cutoffs. The internal workspace is `/recovery-ledger`; APIs are under `/api/v1/organizations/{organization_id}/recovery`.

PostgreSQL 17 must start with `track_commit_timestamp=on`; the compose service and CI enable it. Actual commit provenance, not created_at, supplies known-at K. Unavailable provenance blocks historical authority rather than guessing it. Existing installations must enable the server setting before recovery operations. Apply migration `0006_recovery_ledger`; populated authoritative downgrade is refused. Optional `FLA_RECOVERY_LIMITS` JSON configures the versioned operational profile documented in the validation report.

Phase 4/5 financial/proof policy remains unchanged. No recovery export, bank/ERP integration, accounting posting, vendor communication, bundled allocation, FX, forecasting, gain-share, autonomous recognition or later phase is implemented. No production deployment or compliance claim is made. Phase 6 is merged; Phase 7 implementation is a separate review branch and must not merge automatically.
