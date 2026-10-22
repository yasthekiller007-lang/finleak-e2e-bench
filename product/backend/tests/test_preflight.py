from contextlib import nullcontext
from types import SimpleNamespace

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import REPOSITORY_ROOT, Settings
from app.core.preflight import (
    EXPECTED_SCHEMA_REVISION,
    ReadinessFailure,
    database_readiness,
    production_configuration,
    readiness,
    scanner_database_readiness,
)


def production_settings(**changes):
    values = dict(
        _env_file=None,
        environment="production",
        database_url="postgresql+psycopg://app@db.example.test/pilot?sslmode=verify-full",
        oidc_issuer="https://identity.example.test",
        oidc_audience="pilot-api",
        public_app_url="https://pilot.example.test",
        cors_origins=["https://pilot.example.test"],
        allowed_hosts=["api.internal.example.test"],
        release_sha="a" * 40,
        storage_backend="s3",
        s3_endpoint_url="https://objects.example.test",
        s3_bucket="pilot-originals",
        s3_region="staging-region",
        scanner_backend="clamav",
        scanner_host="scanner.internal",
        scanner_socket_path="/run/clamav/clamd.sock",
        scanner_database_url="postgresql+psycopg://scanner@db.example.test/pilot?sslmode=verify-full",
    )
    values.update(changes)
    return Settings(**values)


@pytest.mark.parametrize(
    "change,code",
    [
        ({"database_url": None}, "database_not_configured"),
        ({"database_url": "postgresql+psycopg://app@db.example.test/pilot"}, "database_tls"),
        ({"oidc_audience": None}, "identity_not_configured"),
        ({"public_app_url": "http://pilot.example.test"}, "public_https"),
        ({"cors_origins": ["https://evil.example.test/path"]}, "explicit_https"),
        ({"cors_origins": ["https://different.example.test"]}, "public_origin"),
        ({"allowed_hosts": ["*"]}, "explicit_private_hosts"),
        ({"allowed_hosts": ["testserver"]}, "explicit_private_hosts"),
        ({"release_sha": None}, "release_identity"),
        ({"storage_backend": "local"}, "private_storage"),
        ({"s3_endpoint_url": "http://objects.example.test"}, "private_storage"),
        ({"s3_access_key_id": "sensitive-example"}, "storage_credentials_incomplete"),
        ({"scanner_backend": "unconfigured"}, "private_scanner"),
        ({"scanner_socket_path": None}, "private_scanner"),
        ({"scanner_database_url": None}, "scanner_database_not_configured"),
        ({"log_level": "DEBUG"}, "production_debug"),
    ],
)
def test_production_configuration_fails_closed_without_sensitive_values(change, code):
    with pytest.raises(ReadinessFailure, match=code) as error:
        production_configuration(production_settings(**change))
    assert "sensitive-example" not in str(error.value)
    assert "example.test" not in str(error.value)


def test_complete_production_configuration_and_bounded_connection_profile():
    settings = production_settings()
    production_configuration(settings)
    assert settings.database_pool_size == 5
    assert settings.database_max_overflow == 0
    assert settings.database_pool_timeout_seconds == 5
    assert settings.s3_timeout_seconds <= 10
    assert settings.scanner_timeout_seconds <= 10


def test_expected_schema_head_matches_the_actual_migration_chain():
    assert ScriptDirectory(str(REPOSITORY_ROOT / "backend/migrations")).get_heads() == [
        EXPECTED_SCHEMA_REVISION
    ]


class ProbeConnection:
    def __init__(self, **values):
        self.values = dict(
            version=170011,
            tracking="on",
            guards=3,
            access_guards=17,
            intake_guards=5,
            source_gate_guards=7,
            unsafe=False,
            tls=True,
        )
        self.values.update(values)

    def execute(self, query, params=None):
        assert "statement_timeout" in str(query)
        assert 1000 <= int(params["timeout"]) <= 30000

    def scalars(self, query):
        assert "alembic_version" in str(query)
        return SimpleNamespace(all=lambda: self.values.get("revisions", [EXPECTED_SCHEMA_REVISION]))

    def scalar(self, query):
        sql = str(query)
        if "server_version_num" in sql:
            return self.values["version"]
        if "track_commit_timestamp" in sql:
            return self.values["tracking"]
        if "pg_trigger" in sql:
            if "pilot_source" in sql:
                return self.values["source_gate_guards"]
            if "pilot_intake" in sql:
                return self.values["intake_guards"]
            if "pilot_identity" in sql:
                return self.values["access_guards"]
            return self.values["guards"]
        if "pg_roles" in sql:
            return self.values["unsafe"]
        if "pg_stat_ssl" in sql:
            return self.values["tls"]
        raise AssertionError(sql)


def probe_engine(**values):
    return SimpleNamespace(connect=lambda: nullcontext(ProbeConnection(**values)))


@pytest.mark.parametrize(
    "values,code",
    [
        ({"revisions": ["0001"]}, "schema_revision_mismatch"),
        ({"revisions": []}, "schema_revision_mismatch"),
        ({"version": 160011}, "postgresql_17_required"),
        ({"version": 180000}, "postgresql_17_required"),
        ({"tracking": "off"}, "commit_tracking_required"),
        ({"guards": 2}, "source_guards_unavailable"),
        ({"access_guards": 16}, "access_guards_unavailable"),
        ({"intake_guards": 4}, "intake_guards_unavailable"),
        ({"source_gate_guards": 6}, "source_gate_guards_unavailable"),
        ({"unsafe": True}, "unsafe_application_database_role"),
        ({"tls": False}, "database_tls_required"),
    ],
)
def test_readiness_rejects_unsafe_runtime(values, code):
    with pytest.raises(ReadinessFailure, match=code):
        database_readiness(probe_engine(**values), production_settings())


def test_production_scanner_readiness_checks_schema_guards_privileges_and_tls():
    scanner_database_readiness(probe_engine(), production_settings())
    with pytest.raises(ReadinessFailure, match="scanner_database_not_configured"):
        scanner_database_readiness(None, production_settings())


@pytest.mark.parametrize(
    "values,code",
    [
        ({"revisions": ["0008"]}, "schema_revision_mismatch"),
        ({"revisions": []}, "schema_revision_mismatch"),
        ({"revisions": ["0009", "0008"]}, "schema_revision_mismatch"),
        ({"version": 160011}, "postgresql_17_required"),
        ({"version": 180000}, "postgresql_17_required"),
        ({"tracking": "off"}, "commit_tracking_required"),
        ({"guards": 2}, "source_guards_unavailable"),
        ({"access_guards": 16}, "access_guards_unavailable"),
        ({"intake_guards": 4}, "intake_guards_unavailable"),
        ({"source_gate_guards": 6}, "source_gate_guards_unavailable"),
        ({"unsafe": True}, "unsafe_scanner_database_role"),
        ({"tls": False}, "scanner_database_tls_required"),
    ],
)
def test_production_scanner_readiness_keeps_every_fail_closed_check(values, code):
    with pytest.raises(ReadinessFailure, match=code):
        scanner_database_readiness(probe_engine(**values), production_settings())


def test_scanner_metadata_permission_error_is_controlled(monkeypatch):
    def forbidden_revision(self, query):
        raise SQLAlchemyError("SECRET database credentials and remote permission detail")

    monkeypatch.setattr(ProbeConnection, "scalars", forbidden_revision)
    with pytest.raises(ReadinessFailure) as error:
        scanner_database_readiness(probe_engine(), production_settings())
    assert str(error.value) == "database_or_schema_unavailable"


def test_readiness_requires_bounded_storage_and_scanner_probes_and_no_live_oidc(monkeypatch):
    calls = []
    monkeypatch.setattr("app.intelligence.confinement.healthcheck", lambda: calls.append("parser"))
    readiness(
        probe_engine(),
        production_settings(),
        storage_probe=lambda: calls.append("storage"),
        scanner_probe=lambda: calls.append("scanner"),
    )
    assert calls == ["storage", "scanner", "parser"]
    with pytest.raises(ReadinessFailure, match="storage_unavailable"):
        readiness(probe_engine(), production_settings())
    with pytest.raises(ReadinessFailure, match="scanner_unavailable"):
        readiness(probe_engine(), production_settings(), storage_probe=lambda: None)


def test_probe_failure_never_exposes_remote_error_or_credentials():
    def fail():
        raise OSError("SECRET signed URL / customer-bank-details")

    with pytest.raises(ReadinessFailure) as error:
        readiness(probe_engine(), production_settings(), storage_probe=fail)
    assert str(error.value) == "storage_unavailable"


@pytest.mark.integration
def test_real_postgresql_readiness_fences_old_schema_disabled_guard_and_tracking(db_session):
    engine = SimpleNamespace(connect=lambda: nullcontext(db_session.connection()))
    settings = Settings(_env_file=None, environment="test")
    database_readiness(engine, settings)
    with db_session.begin_nested() as point:
        db_session.execute(text("UPDATE alembic_version SET version_num='0001'"))
        with pytest.raises(ReadinessFailure, match="schema_revision_mismatch"):
            database_readiness(engine, settings)
        point.rollback()
    with db_session.begin_nested() as point:
        db_session.execute(text("ALTER TABLE documents DISABLE TRIGGER recovery_source_guard"))
        with pytest.raises(ReadinessFailure, match="source_guards_unavailable"):
            database_readiness(engine, settings)
        point.rollback()
    with db_session.begin_nested() as point:
        db_session.execute(text("DROP TRIGGER recovery_source_guard ON documents"))
        with pytest.raises(ReadinessFailure, match="source_guards_unavailable"):
            database_readiness(engine, settings)
        point.rollback()
    assert db_session.scalar(text("SHOW track_commit_timestamp")) == "on"
    with db_session.begin_nested() as point:
        db_session.execute(text("ALTER TABLE users DISABLE TRIGGER pilot_identity"))
        with pytest.raises(ReadinessFailure, match="access_guards_unavailable"):
            database_readiness(engine, settings)
        point.rollback()


def test_production_startup_fails_closed_and_never_exposes_generated_docs():
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app(Settings(_env_file=None, environment="production", database_url=None))
    assert not {"/docs", "/redoc", "/openapi.json"}.intersection(
        getattr(route, "path", None) for route in app.routes
    )
    with pytest.raises(ReadinessFailure, match="database_not_configured"):
        with TestClient(app):
            raise AssertionError("unsafe startup accepted")
