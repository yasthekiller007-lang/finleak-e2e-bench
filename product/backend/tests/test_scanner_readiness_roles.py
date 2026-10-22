"""Real restricted logins and owner-run migrations on a disposable PostgreSQL database."""

import os
import subprocess
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from app.core.config import REPOSITORY_ROOT, Settings
from app.core.preflight import (
    PRIVILEGE_QUERY,
    SCANNER_PRIVILEGE_QUERY,
    ReadinessFailure,
    database_readiness,
    scanner_database_readiness,
)
from app.operations.roles import Roles, bootstrap, grant_runtime

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def scanner_database():
    original = os.environ.get("TEST_DATABASE_URL")
    if not original:
        pytest.skip("Set TEST_DATABASE_URL to an isolated PostgreSQL test administrator")
    original = make_url(original)
    suffix = uuid4().hex[:12]
    name = "phase7_scanner_" + suffix
    roles = Roles(*(kind + "_" + suffix for kind in ("app", "migration", "operator", "scanner")))
    # These are disposable test credentials, never production/Azure principals.
    logins = {
        kind: getattr(roles, kind) + "_login" for kind in ("migration", "application", "scanner")
    }
    secrets = {kind: uuid4().hex for kind in logins}
    administrator = create_engine(original, isolation_level="AUTOCOMMIT", hide_parameters=True)
    engines = {}
    created_roles = []
    with administrator.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{name}"')
    try:
        engines["owner"] = create_engine(original.set(database=name), hide_parameters=True)
        with engines["owner"].begin() as connection:
            bootstrap(connection, roles)
            created_roles.extend(
                (roles.application, roles.migration, roles.operator, roles.scanner)
            )
            connection.exec_driver_sql(f'REVOKE CONNECT ON DATABASE "{name}" FROM PUBLIC')
            for kind, login in logins.items():
                inherit = "NOINHERIT" if kind == "migration" else "INHERIT"
                with connection.connection.driver_connection.cursor() as cursor:
                    cursor.execute(
                        sql.SQL(
                            "CREATE ROLE {} LOGIN " + inherit + " NOSUPERUSER NOCREATEDB "
                            "NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}"
                        ).format(sql.Identifier(login), sql.Literal(secrets[kind]))
                    )
                created_roles.append(login)
                group = getattr(roles, kind)
                for option, value in (
                    ("INHERIT", "FALSE" if kind == "migration" else "TRUE"),
                    ("SET", "TRUE" if kind == "migration" else "FALSE"),
                    ("ADMIN", "FALSE"),
                ):
                    connection.exec_driver_sql(
                        f'GRANT "{group}" TO "{login}" WITH {option} {value}'
                    )
                if kind == "migration":
                    connection.exec_driver_sql(f'GRANT CONNECT ON DATABASE "{name}" TO "{login}"')
                engines[kind] = create_engine(
                    original.set(database=name, username=login, password=secrets[kind]),
                    hide_parameters=True,
                )
        environment = dict(os.environ)
        environment.update(
            FLA_ENVIRONMENT="test",
            FLA_DATABASE_URL=engines["migration"].url.render_as_string(hide_password=False),
            FLA_MIGRATION_ROLE=roles.migration,
        )
        migrated = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=REPOSITORY_ROOT / "backend",
            env=environment,
            capture_output=True,
            timeout=90,
        )
        assert migrated.returncode == 0, "Fresh restricted-owner migration failed"
        with engines["migration"].begin() as connection:
            connection.exec_driver_sql(f'SET LOCAL ROLE "{roles.migration}"')
            grant_runtime(connection, roles)
        yield SimpleNamespace(engines=engines, roles=roles, logins=logins)
    finally:
        for engine in engines.values():
            engine.dispose()
        with administrator.connect() as connection:
            connection.exec_driver_sql(f'DROP DATABASE "{name}" WITH (FORCE)')
            for role in reversed(created_roles):
                connection.exec_driver_sql(f'DROP ROLE IF EXISTS "{role}"')
        administrator.dispose()


def test_fresh_scanner_can_read_schema_and_all_readiness_metadata(scanner_database):
    scanner = scanner_database.engines["scanner"]
    settings = Settings(_env_file=None, environment="test")
    scanner_database_readiness(scanner, settings)
    database_readiness(scanner_database.engines["application"], settings)
    with scanner.connect() as connection:
        assert connection.scalar(text("SELECT current_user")) == scanner_database.logins["scanner"]
        assert connection.scalar(text("SELECT version_num FROM public.alembic_version")) == "0009"
        assert connection.scalar(text(SCANNER_PRIVILEGE_QUERY)) is False
        tls = connection.scalar(text("SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()"))
    # Exercise production checks too. Plain CI PostgreSQL must fail specifically at TLS,
    # not at an earlier hidden permission/schema/role query. No TLS result is fabricated.
    settings = settings.model_copy(update={"environment": "production"})
    if tls is True:
        scanner_database_readiness(scanner, settings)
    else:
        with pytest.raises(ReadinessFailure, match="^scanner_database_tls_required$"):
            scanner_database_readiness(scanner, settings)


def test_scanner_metadata_grant_is_read_only_and_financial_tables_remain_unreadable(
    scanner_database,
):
    with scanner_database.engines["scanner"].connect() as connection:
        for table in (
            "financial_revisions",
            "financial_evaluations",
            "financial_audit",
            "financial_finding_decisions",
            "proof_packages",
            "proof_events",
            "recovery_cases",
            "recovery_records",
            "recovery_publications",
        ):
            assert not connection.scalar(
                text(
                    "SELECT has_table_privilege(current_user,:table,"
                    "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE')"
                ),
                {"table": table},
            )
            with pytest.raises(DBAPIError) as error:
                with connection.begin_nested():
                    connection.exec_driver_sql(f'SELECT * FROM "{table}" LIMIT 1')
            assert error.value.orig.sqlstate == "42501"
        for command in (
            "UPDATE alembic_version SET version_num='0008'",
            "TRUNCATE alembic_version",
            "INSERT INTO financial_evaluations DEFAULT VALUES",
            "INSERT INTO recovery_publications DEFAULT VALUES",
            "INSERT INTO pilot_source_releases DEFAULT VALUES",
            "CREATE TABLE public.scanner_unauthorized(id int)",
            "CREATE TEMP TABLE scanner_unauthorized(id int)",
            "CREATE SCHEMA scanner_unauthorized",
            "ALTER TABLE documents DISABLE TRIGGER recovery_source_guard",
            "SET session_replication_role=replica",
            f'SET ROLE "{scanner_database.roles.migration}"',
            f'SET ROLE "{scanner_database.roles.application}"',
            f'SET ROLE "{scanner_database.roles.operator}"',
            "SET ROLE "
            + scanner_database.engines["owner"].dialect.identifier_preparer.quote_identifier(
                scanner_database.engines["owner"].url.username
            ),
            f'ALTER ROLE "{scanner_database.logins["scanner"]}" BYPASSRLS',
        ):
            with pytest.raises(DBAPIError) as error:
                with connection.begin_nested():
                    connection.exec_driver_sql(command)
            assert error.value.orig.sqlstate == "42501"
        attributes = connection.execute(
            text(
                "SELECT rolsuper,rolcreaterole,rolcreatedb,rolreplication,rolbypassrls "
                "FROM pg_roles WHERE rolname=current_user"
            )
        ).one()
        assert not any(attributes)
    with scanner_database.engines["application"].connect() as connection:
        assert connection.scalar(text(PRIVILEGE_QUERY)) is False
        for command in (
            "INSERT INTO pilot_source_scans DEFAULT VALUES",
            f'SET ROLE "{scanner_database.roles.scanner}"',
        ):
            with pytest.raises(DBAPIError) as error:
                with connection.begin_nested():
                    connection.exec_driver_sql(command)
            assert error.value.orig.sqlstate == "42501"


def test_existing_install_missing_metadata_access_fails_closed_and_owner_reapply_repairs_it(
    scanner_database,
):
    engines, roles = scanner_database.engines, scanner_database.roles
    with engines["migration"].begin() as connection:
        connection.exec_driver_sql(f'SET LOCAL ROLE "{roles.migration}"')
        connection.exec_driver_sql(
            f'REVOKE SELECT ON public.alembic_version FROM "{roles.scanner}"'
        )
    try:
        with pytest.raises(ReadinessFailure, match="^database_or_schema_unavailable$"):
            scanner_database_readiness(
                engines["scanner"], Settings(_env_file=None, environment="test")
            )
    finally:
        with engines["migration"].begin() as connection:
            connection.exec_driver_sql(f'SET LOCAL ROLE "{roles.migration}"')
            grant_runtime(connection, roles)
            grant_runtime(connection, roles)  # Same owner-scoped remediation is safely repeatable.
    scanner_database_readiness(engines["scanner"], Settings(_env_file=None, environment="test"))


@pytest.mark.parametrize("revision", [None, "0008"])
def test_real_scanner_rejects_missing_or_old_schema_revision(scanner_database, revision):
    owner = scanner_database.engines["owner"]
    with owner.begin() as connection:
        if revision is None:
            connection.exec_driver_sql("DELETE FROM alembic_version")
        else:
            connection.execute(
                text("UPDATE alembic_version SET version_num=:revision"), {"revision": revision}
            )
    try:
        with pytest.raises(ReadinessFailure, match="^schema_revision_mismatch$"):
            scanner_database_readiness(
                scanner_database.engines["scanner"], Settings(_env_file=None, environment="test")
            )
    finally:
        with owner.begin() as connection:
            connection.exec_driver_sql("DELETE FROM alembic_version")
            connection.exec_driver_sql("INSERT INTO alembic_version(version_num) VALUES('0009')")


@pytest.mark.parametrize(
    "table,trigger,code",
    [
        ("documents", "recovery_source_guard", "source_guards_unavailable"),
        ("users", "pilot_identity", "access_guards_unavailable"),
        ("pilot_intake_profiles", "pilot_intake_immutable", "intake_guards_unavailable"),
        ("pilot_source_scans", "pilot_source_authority", "source_gate_guards_unavailable"),
    ],
)
def test_real_scanner_rejects_disabled_guard(scanner_database, table, trigger, code):
    owner = scanner_database.engines["owner"]
    with owner.begin() as connection:
        connection.exec_driver_sql(f'ALTER TABLE "{table}" DISABLE TRIGGER "{trigger}"')
    try:
        with pytest.raises(ReadinessFailure, match="^" + code + "$"):
            scanner_database_readiness(
                scanner_database.engines["scanner"], Settings(_env_file=None, environment="test")
            )
    finally:
        with owner.begin() as connection:
            connection.exec_driver_sql(f'ALTER TABLE "{table}" ENABLE TRIGGER "{trigger}"')


def test_real_production_scanner_rejects_unsafe_financial_write_grant(scanner_database):
    engines, roles = scanner_database.engines, scanner_database.roles
    with engines["migration"].begin() as connection:
        connection.exec_driver_sql(f'SET LOCAL ROLE "{roles.migration}"')
        connection.exec_driver_sql(f'GRANT INSERT ON financial_evaluations TO "{roles.scanner}"')
    try:
        with pytest.raises(ReadinessFailure, match="^unsafe_scanner_database_role$"):
            scanner_database_readiness(
                engines["scanner"], Settings(_env_file=None, environment="production")
            )
    finally:
        with engines["migration"].begin() as connection:
            connection.exec_driver_sql(f'SET LOCAL ROLE "{roles.migration}"')
            grant_runtime(connection, roles)
