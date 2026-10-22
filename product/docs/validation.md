# Foundation delivery and validation

Validated on 2026-10-02 in the provided Codex cloud environment. All results below refer to the current instance; no GitHub push, commit, deployment, or environment publication was performed.

## Delivered scope

The monorepo has `frontend/`, `backend/`, and `docs/`, plus root configuration, a PostgreSQL-only Compose file, and GitHub Actions. The frontend has Login, Dashboard, Documents, Leakage Cases, and Settings foundations. The backend has environment configuration, SQLAlchemy lifecycle, structured logs, sanitized API errors, typed domain/extraction/evidence schemas, object storage, domain interfaces, and tests.

The ten requested entities are User, Organization, OrganizationMembership, Document, Contract, ContractVersion (original/amendment), Invoice, InvoiceLineItem, LeakageCase, and LeakageEvidence. A tenant-scoped document/case association table supports related documents. All business data is organization-scoped; composite foreign keys enforce tenant-consistent links. See [architecture](architecture.md) for fields, guarantees, and deferred authorization.

Custom API endpoints created: `GET /api/v1/health` and `GET /api/v1/health/ready`. FastAPI also supplies `/docs`, `/redoc`, and `/openapi.json`. No business-data APIs, fake authentication, integrations, OCR engine, AI provider, detection algorithm, workflow automation, or additional product module was added.

## Installed versions

| Component | Version |
| --- | --- |
| Python | 3.12.14 |
| uv | 0.12.19 |
| FastAPI | 0.142.2 |
| Pydantic / pydantic-settings | 2.13.5 / 2.15.0 |
| SQLAlchemy / Alembic | 2.0.54 / 1.20.0 |
| Psycopg / Uvicorn | 3.3.6 / 0.54.0 |
| PostgreSQL | 17.11, Debian package 17.11-0+deb13u1 |
| pytest / Ruff / httpx2 | 9.1.1 / 0.16.10 / 2.13.1 |
| Node.js / npm | 24.19.0 / 11.9.0 |
| Next.js / React / React DOM | 16.3.8 / 19.3.0 / 19.3.0 |
| TypeScript | 5.9.3 |
| ESLint / eslint-config-next | 9.39.5 / 16.3.8 |
| Prettier / Vitest | 3.9.9 / 5.0.3 |
| Testing Library React / jest-dom / jsdom | 16.3.3 / 7.0.1 / 30.1.1 |
| Docker / Docker Compose | 28.4.0 / 2.40.3 |

Backend and frontend dependency graphs are locked, including artifact hashes. Runtime majors are specified in `.python-version`, `.node-version`, and package manifests. TypeScript 7 and ESLint 10 initially conflicted with the current Next.js lint plugins, so compatible versions were pinned. TestClient now uses the supported httpx2 adapter rather than its deprecated httpx adapter.

## Executed checks and exact outcomes

| Check | Result |
| --- | --- |
| `uv sync --locked` | Passed; repeat installation succeeded without lockfile changes |
| `npm ci --no-audit --no-fund` | Passed; repeat frozen installation succeeded |
| `alembic upgrade head` on empty PostgreSQL databases | Passed; initial revision `0001` installed |
| `alembic downgrade base`, then `upgrade head` on the disposable validation database | Passed |
| Repeated `alembic upgrade head` | Passed; no-op at head |
| `alembic check` | Passed; “No new upgrade operations detected” |
| `alembic current` | `0001 (head)` |
| Backend `pytest -q` with migrated PostgreSQL | **63 passed**, 0 failed, 0 skipped, no warnings in the final run |
| Backend test composition | 35 unit tests; 28 real PostgreSQL integration tests |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed; 35 Python files formatted |
| Frontend `npm test` | **8 passed**, 2 test files, 0 failed or skipped |
| `npm run lint` | Passed, maximum warnings 0 |
| `npm run format:check` | Passed |
| `npm run typecheck` (`next typegen && tsc --noEmit`) | Passed, including regeneration from a missing ignored `next-env.d.ts` |
| `npm run build` | Passed; production App Router routes generated |
| Backend Uvicorn startup | Passed; application startup completed |
| Production `npm start` | Passed; real HTTP requests checked all five requested routes |
| Development `npm run dev` | Passed; real HTTP requests checked all five requested routes |
| Backend health responses | Liveness 200 `ok`, readiness 200 `ready`, request ID present |
| Backend OpenAPI | Only the two public custom health paths exposed |
| Frontend HTTP behavior | All five foundation routes 200 with expected content; `/` redirects to overview; unknown route 404 |
| Frontend/backend/database link | Dashboard showed `Connected` after an actual readiness request |
| Database outage and recovery | Stopping PostgreSQL produced readiness 503 and dashboard `Unavailable`; restarting restored 200 and `Connected` |
| `docker compose config --quiet` | Passed with a temporary placeholder password for configuration validation only |
| Repository hygiene | `git diff --check` passed; source/lockfiles and generated-output exclusions reviewed |
| Secret checks | No private-key, AWS-key, GitHub-token, or OpenAI-key signatures in included repository files; `.env`, nested env files, key files, credential files, and generated outputs are excluded; `.env.example` remains included |
| Process cleanup | Backend, frontend development/production servers, and PostgreSQL validation instance stopped; application ports closed |

Backend tests exercise exact Decimal arithmetic and string serialization, monetary limits and float rejection, mixed-currency rejection, storage integrity/size/traversal/overwrite handling, error sanitization, CORS, logging, settings, all tenant-owned cross-record boundaries, currency consistency, membership uniqueness, version dates, database bounds, UTC timestamps, and migrated database readiness. Frontend tests check route navigation, active state, honest empty states, no fake login controls, and actual readiness response handling.

Initial migration testing found duplicate names for composite unique constraints; the naming convention now includes all participating columns. Monetary boundary tests found that Pydantic digit counting alone was insufficient for the PostgreSQL integer range; explicit Decimal bounds and the ORM numeric guard now enforce it. These failures were fixed before the final passing runs.

## Cloud setup and limitations

Docker Hub refused the anonymous PostgreSQL image pull because its rate limit was exceeded. The image mirrors checked were denied by the cloud egress proxy. Therefore the Compose container launch was not verified here. This did not block real PostgreSQL validation: PostgreSQL 17 was downloaded through Debian's signed package index, verified by apt, extracted under `/workspace/.onboarding-postgres`, and run as the unprivileged cloud user. TLS, signatures, and checksums were preserved.

The prepared PostgreSQL cluster has TCP disabled and host authentication rejected. Local trust is limited by the private Unix socket directory; this is an isolated development facility, not a production authentication design. Development and test databases are separate (`financial_leakage`, `financial_leakage_test`), and tests roll back their fixture data. No real secret, API key, or local database password was added to the repository or saved instructions.

Reusable `install_script` and `start_skill` fields were saved successfully in the cloud configuration draft. The complete installation script was executed successfully against the prepared instance and left no newly started processes running. It refreshes locked dependencies, prepares the local PostgreSQL fallback when needed, creates missing development/test databases without dropping existing ones, and applies/checks migrations. Startup instructions identify the existing checkout, tool versions, database/service startup, readiness requests, test database, and cleanup. They explicitly avoid unnecessary worktrees. Saving does not publish a snapshot; publication and restoration into a new task have not been verified.

ESLint 9 remains pinned because the current Next.js plugins do not declare ESLint 10 compatibility. npm reports ESLint 9 as deprecated/unsupported during installation; the lint command itself passes without warnings. Revisit this development-tool pin when those plugins support ESLint 10. GitHub Actions is configured and its constituent commands were run locally; the hosted workflow has not run because nothing was pushed.

The UI is intentionally unfinished and has no private financial data or working authentication. Authorization, extraction implementations, matching algorithms, detection rules, confidence calibration, S3 storage, case transitions, audit/retention policy, and production operations remain future work. These are scope boundaries, not failed setup checks.

## Assumptions and next work

Money supports fourteen integer digits and six decimal places, with uppercase three-letter currency format checks and no conversion. Invoice values may be signed for future credit adjustments; leakage exposures are nonnegative. Contract effective intervals are half-open, and amendments may overlap pending a defined active-terms interpretation policy. `/leakage-cases` is the canonical route for the Cases/Anomalies foundation.

Next: implement a real identity adapter and verified organization membership boundary, then authorized document upload with metadata/object-store consistency. Specify extraction validation, contract version matching, and a single deterministic detection rule in later tasks. Work stops at this validated foundation.

## Files changed

The root README was replaced with setup, checks, route/API, and scope documentation. All other included repository files listed below are new. Generated virtual environments, caches, frontend type declarations/builds, and the local PostgreSQL installation/data are excluded from Git.

73 new files; 1 modified file (`README.md`).

- `.env.example`
- `.github/workflows/ci.yml`
- `.gitignore`
- `README.md`
- `backend/.python-version`
- `backend/alembic.ini`
- `backend/app/__init__.py`
- `backend/app/api/__init__.py`
- `backend/app/api/health.py`
- `backend/app/core/__init__.py`
- `backend/app/core/config.py`
- `backend/app/core/errors.py`
- `backend/app/core/logging.py`
- `backend/app/db/__init__.py`
- `backend/app/db/base.py`
- `backend/app/db/models.py`
- `backend/app/db/session.py`
- `backend/app/db/types.py`
- `backend/app/domain/__init__.py`
- `backend/app/domain/money.py`
- `backend/app/domain/tenancy.py`
- `backend/app/domain/types.py`
- `backend/app/main.py`
- `backend/app/modules/__init__.py`
- `backend/app/modules/confidence.py`
- `backend/app/modules/contract_extraction.py`
- `backend/app/modules/evidence.py`
- `backend/app/modules/financial_calculations.py`
- `backend/app/modules/ingestion.py`
- `backend/app/modules/invoice_extraction.py`
- `backend/app/modules/leakage_rules.py`
- `backend/app/modules/matching.py`
- `backend/app/modules/storage.py`
- `backend/migrations/env.py`
- `backend/migrations/script.py.mako`
- `backend/migrations/versions/0001_initial_tenant_scoped_financial_schema.py`
- `backend/pyproject.toml`
- `backend/tests/conftest.py`
- `backend/tests/test_api.py`
- `backend/tests/test_config.py`
- `backend/tests/test_database.py`
- `backend/tests/test_money.py`
- `backend/tests/test_storage.py`
- `backend/uv.lock`
- `compose.yaml`
- `docs/architecture.md`
- `docs/validation.md`
- `frontend/.node-version`
- `frontend/.prettierignore`
- `frontend/.prettierrc.json`
- `frontend/eslint.config.mjs`
- `frontend/next.config.ts`
- `frontend/package-lock.json`
- `frontend/package.json`
- `frontend/src/app/(workspace)/dashboard/page.tsx`
- `frontend/src/app/(workspace)/documents/page.tsx`
- `frontend/src/app/(workspace)/layout.tsx`
- `frontend/src/app/(workspace)/leakage-cases/page.tsx`
- `frontend/src/app/(workspace)/settings/page.tsx`
- `frontend/src/app/globals.css`
- `frontend/src/app/layout.tsx`
- `frontend/src/app/login/page.tsx`
- `frontend/src/app/not-found.tsx`
- `frontend/src/app/page.tsx`
- `frontend/src/components/empty-state.tsx`
- `frontend/src/components/page-heading.tsx`
- `frontend/src/components/sidebar.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src/lib/navigation.ts`
- `frontend/tests/api.test.ts`
- `frontend/tests/foundation.test.tsx`
- `frontend/tests/setup.ts`
- `frontend/tsconfig.json`
- `frontend/vitest.config.ts`
