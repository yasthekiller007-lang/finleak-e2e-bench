# Azure scanner database readiness correction

## Confirmed cause and scope

On main `47a077025d6bf2bf608be09384e916a202fae3ee`, the official runtime grant
helper gives `fla_app` SELECT on `alembic_version` but omits that table from
the scanner's SELECT allowlist. The unchanged scanner readiness path calls
the common database readiness checks, starting with the exact Alembic head.
The real Azure scanner login therefore receives permission denied and a
controlled `database_or_schema_unavailable` result.

The fix adds **SELECT on `public.alembic_version` to `fla_scanner` only**.
No migration or readiness implementation changes. The schema remains `0009`.
The table contains migration revision metadata, not financial facts or K.
Both fresh installations and existing installations using the old grant
helper are affected. The remaining queries inspect PostgreSQL settings,
catalogs, effective privileges and the connecting session's TLS state; they
require no financial-table reads. Real restricted-login tests exercise those
queries rather than assuming the first grant resolves every check.

The application still cannot append scan verdicts. Scanner money/history
reads and writes, migration/admin membership, ownership, DDL, temporary-table,
replication and BYPASSRLS authority remain absent. Phase 4–6 policy, approvals,
immutable audit/history, authentic commit capture, publication equality guards
and as-known reporting are unchanged. No SECURITY DEFINER shortcut is added.

## Authorization and execution boundary

These instructions are for user execution **after reviewing and authorizing
the fix and Azure remediation**. Work does not mutate Azure. Do not rerun
bootstrap, migrations, seeds or restore creation. The existing database is
`finleak_phase7_drill` on `finleak-pg17-staging-01`; the first-probe restore
server remains untouched. This correction is not Azure provider-fit PASS,
Phase 7 completion or customer-intake authorization.

No Azure Contributor permission is required. Use the existing migration
login, which must CONNECT to this database and be able to SET ROLE to the
object owner `fla_migration`. Do not grant it new administrator capabilities.
Reapplying grants is transactional; an error rolls back the whole operation.

## Obtain the reviewed code on Ubuntu / WSL2

Preserve the existing checkout. Set `FIX_SHA` to the final SHA shown in the
reviewed PR and its successful CI receipts; this document intentionally does
not embed its own commit SHA. Use an unused worktree path.

```bash
cd "$HOME/finleak-phase7-runner"
git fetch origin hotfix/phase7-scanner-readiness-metadata
FIX_SHA='<final-reviewed-40-character-SHA>'
test "$(git rev-parse FETCH_HEAD)" = "$FIX_SHA" || exit 1
git worktree add --detach "$HOME/finleak-phase7-scanner-fix" "$FIX_SHA"
cd "$HOME/finleak-phase7-scanner-fix/backend"
uv sync --locked --python 3.12
```

Verify the actual runner artifact and dependencies before using its results
as qualification evidence. The scoped npm development finding and patched
zlib reviews expire **2026-10-09 00:00 UTC**. They cover only the reviewed
scope/actual artifacts; Ubuntu's Python/zlib does not inherit an Alpine-image
review. After expiry, fresh scans and substantive reachability/runtime review
are required; do not extend dates. No frontend build is required here.

## Apply the existing helper under the migration object owner

Run interactively so `getpass` can read the terminal. Passwords stay in process
memory, not shell history, command arguments, environment variables or files.
The CA bundle must be trusted and readable. Do not enable SQL echo/debug logs.

```bash
.venv/bin/python - <<'PY'
from getpass import getpass

from sqlalchemy import text
from sqlalchemy.engine import URL

from app.core.config import Settings
from app.db.session import create_database_engine
from app.operations.roles import Roles, grant_runtime

url = URL.create(
    "postgresql+psycopg",
    username="finleak_p7_migration",
    password=getpass("Migration credential (hidden): "),
    host="finleak-pg17-staging-01.postgres.database.azure.com",
    port=5432,
    database="finleak_phase7_drill",
    query={"sslmode": "verify-full", "sslrootcert": "/etc/ssl/certs/ca-certificates.crt"},
)
settings = Settings(_env_file=None, environment="test",
                    database_url=url.render_as_string(hide_password=False))
engine = create_database_engine(settings)
try:
    with engine.begin() as connection:
        connection.exec_driver_sql("SET LOCAL ROLE fla_migration")
        if connection.scalar(text("SELECT current_database()")) != "finleak_phase7_drill":
            raise ValueError("wrong_target")
        if connection.scalars(text("SELECT version_num FROM public.alembic_version")).all() != ["0009"]:
            raise ValueError("unexpected_schema")
        grant_runtime(connection, Roles())
    print("PASS: owner-scoped runtime allowlist applied; schema remains 0009")
except Exception:
    raise SystemExit("STOP: runtime grant remediation failed; use protected diagnostics") from None
finally:
    engine.dispose()
PY
```

Do not invoke `app.operations.roles grant-runtime --apply` merely with
`FLA_MIGRATION_ROLE` set: that CLI does not SET ROLE. The snippet explicitly
assumes the migration owner in the transaction and calls the official helper.
It reapplies the existing application/operator/scanner allowlists; relative
to the reported provisioning state the sole new permission is scanner SELECT
on `alembic_version`. It is safe to rerun. Do not use blanket/default grants.

No deployed application code changes or restart are needed for the unchanged
readiness query to benefit from the committed grant. Future provisioning must
use the corrected helper. This procedure does not deploy a scanner or service.

## Validate using the actual application and scanner principals

This makes only read-only database probes and transaction-local timeout
settings. It calls production-mode database checks directly, not production
application startup; it does not claim real OIDC, ClamAV or storage qualification.

```bash
.venv/bin/python - <<'PY'
from getpass import getpass

from sqlalchemy import text
from sqlalchemy.engine import URL

from app.core.config import Settings
from app.core.preflight import (PRIVILEGE_QUERY, SCANNER_PRIVILEGE_QUERY,
                                database_readiness, scanner_database_readiness)
from app.db.session import create_database_engine

for kind, login, check, privileges in (
    ("application", "finleak_p7_app", database_readiness, PRIVILEGE_QUERY),
    ("scanner", "finleak_p7_scanner", scanner_database_readiness, SCANNER_PRIVILEGE_QUERY),
):
    url = URL.create("postgresql+psycopg", username=login,
        password=getpass(f"Credential for {kind} (hidden): "),
        host="finleak-pg17-staging-01.postgres.database.azure.com", port=5432,
        database="finleak_phase7_drill",
        query={"sslmode": "verify-full", "sslrootcert": "/etc/ssl/certs/ca-certificates.crt"})
    settings = Settings(_env_file=None, environment="production",
                        database_url=url.render_as_string(hide_password=False))
    engine = create_database_engine(settings)
    try:
        check(engine, settings)
        with engine.connect() as connection:
            connection.exec_driver_sql("SET TRANSACTION READ ONLY")
            assert connection.scalar(text("SELECT current_user")) == login
            assert connection.scalar(text("SELECT current_database()")) == "finleak_phase7_drill"
            assert connection.scalar(text(privileges)) is False
            assert connection.scalar(text("SELECT version_num FROM public.alembic_version")) == "0009"
            assert connection.scalar(text("SHOW track_commit_timestamp")) == "on"
            assert connection.scalar(text("SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()")) is True
            if kind == "scanner":
                for table in ("financial_revisions", "financial_evaluations", "financial_audit",
                              "proof_packages", "proof_events", "recovery_cases",
                              "recovery_records", "recovery_publications"):
                    assert not connection.scalar(text(
                        "SELECT has_table_privilege(current_user,:table,"
                        "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE')"), {"table": table})
                assert not connection.scalar(text(
                    "SELECT has_table_privilege(current_user,'alembic_version',"
                    "'INSERT,UPDATE,DELETE,TRUNCATE')"))
            else:
                assert not connection.scalar(text(
                    "SELECT has_table_privilege(current_user,'pilot_source_scans','INSERT')"))
        print(f"PASS: {kind} production database readiness and privilege isolation")
    except Exception:
        raise SystemExit(f"STOP: {kind} validation failed; preserve protected diagnostics") from None
    finally:
        engine.dispose()
PY
```

Retain final SHA and CI links, UTC execution time, redacted command results,
the unchanged `0009` revision, connecting role, TLS facts and before/after ACL
receipts. Never retain passwords, credentialed URLs or financial row contents.
Any failure is STOP, not a reason to expand scanner grants or disable checks.
Actual Azure readiness remains unverified until this execution returns both
PASS lines. Do not seed Case A/B or create another restore as part of remediation.

## Rollback

Stop qualification/scanner admission. As the migration owner, in a transaction
on the dedicated database, execute only:

```sql
BEGIN;
SET LOCAL ROLE fla_migration;
REVOKE SELECT ON TABLE public.alembic_version FROM fla_scanner;
COMMIT;
```

Rollback deliberately restores the old scanner readiness failure; it is not
a safe operating workaround. Schema/head and financial history are untouched.
Prevent the corrected grant helper from being reapplied while investigating.
Do not downgrade migrations, delete data or substitute administrator credentials.

## Regression qualification

The existing pytest framework adds a fresh disposable PostgreSQL database,
restricted migration/app/scanner logins and the unchanged migration chain.
Tests cover exact schema/catalog reads, repeatable owner remediation, denied
financial reads/writes, SET ROLE to owner/admin/app/operator, DDL, temporary
tables, BYPASSRLS escalation, app scan-verdict denial, invalid/missing revision,
disabled source/access/intake/quarantine guards and unsafe scanner grants.

Unit tests retain PG17/commit-tracking/schema/guard/TLS fail-closed coverage.
The PostgreSQL test executes production scanner checks too: a genuine encrypted
connection must pass; a plain CI connection must reach and fail at the TLS check.
No fake TLS result is used. CI evidence is synthetic PostgreSQL qualification,
not proof that the real Azure runner/artifact/provider has passed.
