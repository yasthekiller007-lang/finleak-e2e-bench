"""Bounded operational readiness. It never grants financial authority."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings

EXPECTED_SCHEMA_REVISION = "0009"


@dataclass
class ReadinessFailure(Exception):
    code: str

    def __str__(self) -> str:
        # Never include a URL, database exception, credential or source contents.
        return self.code


def https_origin(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlsplit(value)
    return bool(
        parsed.scheme == "https"
        and parsed.hostname
        and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        and not parsed.username
        and not parsed.password
        and parsed.path in {"", "/"}
        and not parsed.query
        and not parsed.fragment
    )


def production_configuration(settings: Settings) -> None:
    """Called at production startup, rather than constructing testable settings."""
    if settings.environment != "production":
        return
    if settings.database_url is None:
        raise ReadinessFailure("database_not_configured")
    query = parse_qs(urlsplit(settings.database_url.unicode_string()).query)
    if query.get("sslmode") != ["verify-full"]:
        raise ReadinessFailure("database_tls_required")
    if not settings.oidc_issuer or not settings.oidc_audience:
        raise ReadinessFailure("identity_not_configured")
    if not https_origin(settings.public_app_url):
        raise ReadinessFailure("public_https_origin_required")
    if not settings.cors_origins or any(not https_origin(v) for v in settings.cors_origins):
        raise ReadinessFailure("explicit_https_origins_required")
    if settings.public_app_url.rstrip("/") not in settings.cors_origins:
        raise ReadinessFailure("public_origin_not_allowed")
    if not settings.allowed_hosts or any(
        not re.fullmatch(r"[a-zA-Z0-9.-]{1,253}", host)
        or host in {"localhost", "127.0.0.1", "testserver"}
        for host in settings.allowed_hosts
    ):
        raise ReadinessFailure("explicit_private_hosts_required")
    if not settings.release_sha:
        raise ReadinessFailure("release_identity_required")
    if settings.storage_backend != "s3" or not (
        settings.s3_bucket and settings.s3_region and https_origin(settings.s3_endpoint_url)
    ):
        raise ReadinessFailure("private_storage_configuration_required")
    if bool(settings.s3_access_key_id) != bool(settings.s3_secret_access_key):
        raise ReadinessFailure("storage_credentials_incomplete")
    if settings.scanner_backend != "clamav" or not settings.scanner_socket_path:
        raise ReadinessFailure("private_scanner_configuration_required")
    if settings.scanner_database_url is None:
        raise ReadinessFailure("scanner_database_not_configured")
    if parse_qs(urlsplit(settings.scanner_database_url.unicode_string()).query).get("sslmode") != [
        "verify-full"
    ]:
        raise ReadinessFailure("scanner_database_tls_required")
    if settings.log_level == "DEBUG":
        raise ReadinessFailure("production_debug_logging_forbidden")


PRIVILEGE_QUERY = """
SELECT EXISTS (
 SELECT 1 FROM pg_roles r WHERE pg_has_role(current_user, r.oid, 'MEMBER') AND
 (r.rolsuper OR r.rolcreaterole OR r.rolcreatedb OR r.rolreplication OR r.rolbypassrls)
) OR EXISTS (
 SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND pg_has_role(current_user,c.relowner,'MEMBER')
) OR EXISTS (
 SELECT 1 FROM pg_namespace n WHERE n.nspname='public'
 AND pg_has_role(current_user,n.nspowner,'MEMBER')
) OR has_schema_privilege(current_user,'public','CREATE')
 OR has_database_privilege(current_user,current_database(),'CREATE')
 OR has_database_privilege(current_user,current_database(),'TEMPORARY')
 OR has_table_privilege(current_user,'organization_memberships','INSERT,DELETE')
 OR has_column_privilege(current_user,'organization_memberships','role','UPDATE')
 OR has_table_privilege(current_user,'organizations','INSERT')
 OR has_table_privilege(current_user,'pilot_user_access','INSERT,UPDATE,DELETE')
 OR has_table_privilege(current_user,'pilot_tenant_access','INSERT,UPDATE,DELETE')
 OR has_table_privilege(current_user,'pilot_access_journal','INSERT,UPDATE,DELETE,TRUNCATE')
 OR has_table_privilege(current_user,'pilot_source_scans','INSERT,UPDATE,DELETE,TRUNCATE')
 OR has_table_privilege(current_user,'pilot_source_releases','UPDATE,DELETE,TRUNCATE')
 OR has_table_privilege(current_user,'pilot_source_requests','UPDATE,DELETE,TRUNCATE')
 OR has_parameter_privilege(current_user,'session_replication_role','SET')
"""

GUARD_QUERY = """
SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
 JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND c.relname='documents'
 AND t.tgname IN ('financial_source_guard','proof_source_guard','recovery_source_guard')
 AND t.tgenabled IN ('O','A')
"""

ACCESS_GUARD_QUERY = """
SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
 JOIN pg_namespace n ON n.oid=c.relnamespace
 JOIN (VALUES
 ('users','pilot_identity'), ('organizations','pilot_identity'),
 ('organization_memberships','pilot_identity'), ('user_identities','pilot_identity'),
 ('documents','pilot_identity'), ('pilot_user_access','pilot_identity'),
 ('pilot_tenant_access','pilot_identity'), ('organizations','pilot_access'),
 ('organization_memberships','pilot_access'), ('pilot_user_access','pilot_access'),
 ('pilot_tenant_access','pilot_access'), ('organizations','pilot_access_audit'),
 ('organization_memberships','pilot_access_audit'), ('pilot_user_access','pilot_access_audit'),
 ('pilot_tenant_access','pilot_access_audit'), ('pilot_access_journal','pilot_journal_immutable'),
 ('documents','pilot_original_registration')
 ) required(table_name,trigger_name) ON c.relname=required.table_name
 AND t.tgname=required.trigger_name
 WHERE n.nspname='public' AND t.tgenabled IN ('O','A')
"""

INTAKE_GUARD_QUERY = """
SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
 JOIN pg_namespace n ON n.oid=c.relnamespace
 JOIN (VALUES
 ('pilot_intake_profiles','pilot_intake_immutable'),
 ('pilot_intake_attempts','pilot_intake_immutable'),
 ('pilot_intake_profiles','pilot_intake_profile'),
 ('pilot_intake_attempts','pilot_intake_attempt'),
 ('pilot_tenant_access','pilot_0_tenant_intake')
 ) required(table_name,trigger_name) ON c.relname=required.table_name
 AND t.tgname=required.trigger_name
 WHERE n.nspname='public' AND t.tgenabled IN ('O','A')
"""

SOURCE_GATE_GUARD_QUERY = """
SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
 JOIN pg_namespace n ON n.oid=c.relnamespace
 JOIN (VALUES
 ('pilot_source_scans','pilot_source_immutable'),
 ('pilot_source_releases','pilot_source_immutable'),
 ('pilot_source_requests','pilot_source_immutable'),
 ('pilot_source_scans','pilot_source_authority'),
 ('pilot_source_releases','pilot_source_authority'),
 ('pilot_source_requests','pilot_source_authority'),
 ('documents','pilot_scanned_original')
 ) required(table_name,trigger_name) ON c.relname=required.table_name
 AND t.tgname=required.trigger_name
 WHERE n.nspname='public' AND t.tgenabled IN ('O','A')
"""

SCANNER_PRIVILEGE_QUERY = """
SELECT EXISTS (
 SELECT 1 FROM pg_roles r WHERE pg_has_role(current_user,r.oid,'MEMBER') AND
 (r.rolsuper OR r.rolcreaterole OR r.rolcreatedb OR r.rolreplication OR r.rolbypassrls)
) OR EXISTS (
 SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND pg_has_role(current_user,c.relowner,'MEMBER')
) OR EXISTS (
 SELECT 1 FROM pg_namespace n WHERE n.nspname='public'
 AND pg_has_role(current_user,n.nspowner,'MEMBER')
) OR has_schema_privilege(current_user,'public','CREATE')
 OR has_database_privilege(current_user,current_database(),'CREATE,TEMPORARY')
 OR has_parameter_privilege(current_user,'session_replication_role','SET')
 OR has_table_privilege(current_user,'organization_memberships','INSERT,UPDATE,DELETE')
 OR has_table_privilege(current_user,'organizations','INSERT,DELETE')
 OR has_table_privilege(current_user,'pilot_user_access','INSERT,UPDATE,DELETE')
 OR has_table_privilege(current_user,'pilot_tenant_access','INSERT,UPDATE,DELETE')
 OR has_table_privilege(current_user,'pilot_access_journal','INSERT,UPDATE,DELETE,TRUNCATE')
 OR has_table_privilege(current_user,'pilot_source_releases','INSERT,UPDATE,DELETE,TRUNCATE')
 OR has_table_privilege(current_user,'pilot_source_scans','UPDATE,DELETE,TRUNCATE')
 OR has_table_privilege(current_user,'pilot_source_requests','UPDATE,DELETE,TRUNCATE')
 OR has_table_privilege(current_user,'financial_revisions','INSERT,UPDATE,DELETE')
 OR has_table_privilege(current_user,'financial_evaluations','INSERT,UPDATE,DELETE')
 OR has_table_privilege(current_user,'proof_packages','INSERT,UPDATE,DELETE')
 OR has_table_privilege(current_user,'recovery_records','INSERT,UPDATE,DELETE')
 OR NOT has_table_privilege(current_user,'pilot_source_scans','INSERT')
 OR NOT has_table_privilege(current_user,'pilot_source_scans','SELECT')
 OR NOT has_table_privilege(current_user,'pilot_source_requests','INSERT')
 OR NOT has_table_privilege(current_user,'pilot_source_requests','SELECT')
"""


def database_readiness(engine: Engine | None, settings: Settings) -> None:
    if engine is None:
        raise ReadinessFailure("database_not_configured")
    try:
        with engine.connect() as connection:
            # Explicit timeout bounds readiness even if runtime/session defaults drift.
            connection.execute(
                text("SELECT set_config('statement_timeout', :timeout, true)"),
                {"timeout": str(settings.database_timeout_seconds * 1000)},
            )
            revisions = connection.scalars(text("SELECT version_num FROM alembic_version")).all()
            if revisions != [EXPECTED_SCHEMA_REVISION]:
                raise ReadinessFailure("schema_revision_mismatch")
            version = int(connection.scalar(text("SHOW server_version_num")))
            if not 170000 <= version < 180000:
                raise ReadinessFailure("postgresql_17_required")
            if connection.scalar(text("SHOW track_commit_timestamp")) != "on":
                raise ReadinessFailure("commit_tracking_required")
            if connection.scalar(text(GUARD_QUERY)) != 3:
                raise ReadinessFailure("source_guards_unavailable")
            if connection.scalar(text(ACCESS_GUARD_QUERY)) != 17:
                raise ReadinessFailure("access_guards_unavailable")
            if connection.scalar(text(INTAKE_GUARD_QUERY)) != 5:
                raise ReadinessFailure("intake_guards_unavailable")
            if connection.scalar(text(SOURCE_GATE_GUARD_QUERY)) != 7:
                raise ReadinessFailure("source_gate_guards_unavailable")
            if settings.environment == "production":
                if connection.scalar(text(PRIVILEGE_QUERY)):
                    raise ReadinessFailure("unsafe_application_database_role")
                tls = connection.scalar(
                    text("SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()")
                )
                if tls is not True:
                    raise ReadinessFailure("database_tls_required")
    except SQLAlchemyError:
        raise ReadinessFailure("database_or_schema_unavailable") from None


def scanner_database_readiness(engine, settings):
    if engine is None:
        raise ReadinessFailure("scanner_database_not_configured")
    database_readiness(engine, settings.model_copy(update={"environment": "development"}))
    if settings.environment != "production":
        return
    try:
        with engine.connect() as connection:
            if connection.scalar(text(SCANNER_PRIVILEGE_QUERY)):
                raise ReadinessFailure("unsafe_scanner_database_role")
            if (
                connection.scalar(text("SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()"))
                is not True
            ):
                raise ReadinessFailure("scanner_database_tls_required")
    except SQLAlchemyError:
        raise ReadinessFailure("scanner_database_unavailable") from None


def readiness(
    engine: Engine | None,
    settings: Settings,
    *,
    storage_probe: Callable[[], None] | None = None,
    scanner_probe: Callable[[], None] | None = None,
) -> None:
    production_configuration(settings)
    database_readiness(engine, settings)
    if settings.environment == "production":
        from app.intelligence.confinement import healthcheck

        for probe, code in (
            (storage_probe, "storage_unavailable"),
            (scanner_probe, "scanner_unavailable"),
        ):
            if probe is None:
                raise ReadinessFailure(code)
            try:
                probe()
            except (OSError, ValueError, TimeoutError):
                raise ReadinessFailure(code) from None
        try:
            healthcheck()
        except OSError:
            raise ReadinessFailure("parser_confinement_unavailable") from None
