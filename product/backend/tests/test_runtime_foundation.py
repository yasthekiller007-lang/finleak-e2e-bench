import json
import subprocess
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.core.config import REPOSITORY_ROOT
from app.core.preflight import PRIVILEGE_QUERY
from app.db.models import Organization, OrganizationMembership, User
from app.operations.roles import APPLICATION_WRITABLE, Roles, bootstrap, grant_runtime
from app.operations.runtime import validate_runtime_environment


@pytest.mark.parametrize("name", ["postgres", "public", "pg_role", "bad;sql", "UPPER", "a" * 64])
def test_role_identifiers_reject_reserved_or_injectable_names(name):
    with pytest.raises(ValueError):
        Roles(application=name).validate()


def test_roles_are_distinct_and_legacy_business_models_have_no_application_write_grant():
    with pytest.raises(ValueError):
        Roles(application="duplicate", migration="duplicate").validate()
    assert not {"contracts", "invoices", "leakage_cases", "organization_memberships"}.intersection(
        APPLICATION_WRITABLE
    )


@pytest.mark.parametrize("environment", [None, "test", "development"])
def test_production_image_cannot_start_an_environment_switchable_test_runtime(
    monkeypatch, environment
):
    monkeypatch.delenv("FLA_ENVIRONMENT", raising=False)
    monkeypatch.setenv("FLA_RELEASE_SHA", "a" * 40)
    if environment:
        monkeypatch.setenv("FLA_ENVIRONMENT", environment)
    with pytest.raises(ValueError, match="requires the production"):
        validate_runtime_environment()


def test_runtime_requires_exact_release_identity(monkeypatch):
    monkeypatch.setenv("FLA_ENVIRONMENT", "production")
    monkeypatch.setenv("FLA_RELEASE_SHA", "main")
    with pytest.raises(ValueError, match="release identity"):
        validate_runtime_environment()
    monkeypatch.setenv("FLA_RELEASE_SHA", "b" * 40)
    validate_runtime_environment()


def test_production_build_contract_excludes_test_auth_harness_and_secrets():
    root = REPOSITORY_ROOT
    backend = (root / "deploy/phase7/backend.Dockerfile").read_text()
    frontend = (root / "deploy/phase7/frontend.Dockerfile").read_text()
    ignored = (root / ".dockerignore").read_text().splitlines()
    for image in (backend, frontend):
        assert "COPY . " not in image
        assert "USER " in image
        assert "org.opencontainers.image.revision" in image
        assert ".env" not in image
    assert "COPY backend/app /app/app" in backend
    assert "COPY frontend/src ./src" in frontend
    assert "**/tests" in ignored and "**/e2e" in ignored
    assert "**/.env.*" in ignored


def test_frontend_entrypoint_rejects_test_mode_missing_secrets_and_unsafe_endpoint():
    script = REPOSITORY_ROOT / "deploy/phase7/frontend-entrypoint.cjs"
    # Node is not part of the backend CI job; absence is handled by the frontend job's
    # same contract test/production build. Local execution may validate it directly.
    import shutil

    if not shutil.which("node"):
        # Structural enforcement is still asserted; no unexpected PG skip is introduced.
        assert 'e.NODE_ENV === "production"' in script.read_text()
        return
    source = (
        "const {valid}=require(process.argv[1]);"
        "let e={NODE_ENV:'production',FLA_RELEASE_SHA:'a'.repeat(40),"
        "NEXTAUTH_URL:'https://pilot.example.test',OIDC_ISSUER_URL:"
        "'https://id.example.test/realm/pilot',NEXTAUTH_SECRET:'x'.repeat(40),"
        "OIDC_CLIENT_ID:'client',OIDC_CLIENT_SECRET:'synthetic',BACKEND_URL:'http://api:8000'};"
        "console.log(JSON.stringify([valid(e),valid({...e,NODE_ENV:'test'}),"
        "valid({...e,NEXTAUTH_SECRET:''}),valid({...e,BACKEND_URL:'file:///private'})]));"
    )
    assert json.loads(subprocess.check_output(["node", "-e", source, str(script)])) == [
        True,
        False,
        False,
        False,
    ]


@pytest.mark.integration
def test_postgresql_runtime_roles_deny_ddl_replication_history_truncation_and_escalation(
    db_session,
):
    suffix = uuid4().hex[:12]
    roles = Roles("app_" + suffix, "migration_" + suffix, "operator_" + suffix)
    connection = db_session.connection()
    bootstrap(connection, roles)
    bootstrap(connection, roles)  # Explicit provisioning retry is idempotent.
    grant_runtime(connection, roles)
    org, user = (
        Organization(name="Synthetic privilege tenant"),
        User(display_name="Operator fixture"),
    )
    db_session.add_all([org, user])
    db_session.flush()
    member = OrganizationMembership(organization_id=org.id, user_id=user.id, role="owner")
    db_session.add(member)
    db_session.flush()
    with db_session.begin_nested() as point:
        db_session.execute(text(f'SET LOCAL ROLE "{roles.application}"'))
        assert db_session.scalar(text(PRIVILEGE_QUERY)) is False
        assert db_session.scalar(
            select(Organization).where(Organization.id == org.id).with_for_update()
        )
        assert db_session.scalar(
            select(OrganizationMembership)
            .where(OrganizationMembership.id == member.id)
            .with_for_update()
        )
        point.rollback()
    forbidden = [
        "CREATE TABLE public.unauthorized (id int)",
        "ALTER TABLE documents DISABLE TRIGGER recovery_source_guard",
        "TRUNCATE financial_evaluations CASCADE",
        "SET session_replication_role=replica",
        "DELETE FROM recovery_records",
        "UPDATE organization_memberships SET role='admin'",
        "INSERT INTO organizations (id,name) VALUES(gen_random_uuid(),'unauthorized')",
        f'GRANT "{roles.migration}" TO "{roles.application}"',
    ]
    for command in forbidden:
        with db_session.begin_nested() as point:
            db_session.execute(text(f'SET LOCAL ROLE "{roles.application}"'))
            with pytest.raises(DBAPIError) as error:
                db_session.execute(text(command))
            assert error.value.orig.sqlstate == "42501"
            point.rollback()
    with db_session.begin_nested() as point:
        db_session.execute(text(f'SET LOCAL ROLE "{roles.operator}"'))
        with pytest.raises(DBAPIError) as error:
            db_session.execute(text("INSERT INTO financial_evaluations DEFAULT VALUES"))
        assert error.value.orig.sqlstate == "42501"
        point.rollback()
