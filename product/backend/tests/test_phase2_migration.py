import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

from app.db.base import Base

pytestmark = pytest.mark.integration


def migration(name):
    file = Path(__file__).parents[1] / "migrations" / "versions" / name
    spec = importlib.util.spec_from_file_location("migration_under_test", file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def legacy_schema():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set isolated TEST_DATABASE_URL")
    engine = create_engine(url)
    with engine.connect() as connection:
        transaction = connection.begin()
        schema = "migration_" + uuid4().hex
        connection.execute(text(f"CREATE SCHEMA {schema}"))
        connection.execute(text(f"SET LOCAL search_path TO {schema}"))
        context = MigrationContext.configure(connection, opts={"target_metadata": Base.metadata})
        with Operations.context(context):
            migration("0001_initial_tenant_scoped_financial_schema.py").upgrade()
            yield connection, migration("0002_identity_membership_uploads.py")
        transaction.rollback()
    engine.dispose()


def seed_legacy(connection, duplicate=False):
    user_id, org_id = uuid4(), uuid4()
    connection.execute(
        text("INSERT INTO users (id,email,display_name) VALUES (:id,'old@example.test','Legacy')"),
        {"id": user_id},
    )
    connection.execute(
        text("INSERT INTO organizations (id,name) VALUES (:id,'Legacy tenant')"), {"id": org_id}
    )
    connection.execute(
        text(
            "INSERT INTO organization_memberships (id,organization_id,user_id,role) "
            "VALUES (:id,:org,:user,'member')"
        ),
        {"id": uuid4(), "org": org_id, "user": user_id},
    )
    for _ in range(2 if duplicate else 1):
        connection.execute(
            text(
                "INSERT INTO documents (id,organization_id,original_filename,mime_type,"
                "file_size,storage_key,sha256,document_type,processing_status) "
                "VALUES (:id,:org,'old.csv','text/csv',20,:key,:hash,'invoice','pending')"
            ),
            {"id": uuid4(), "org": org_id, "key": str(uuid4()), "hash": "a" * 64},
        )
    return user_id, org_id


def test_upgrade_preserves_legacy_documents_memberships_and_reverses_safely(legacy_schema):
    connection, revision = legacy_schema
    user_id, org_id = seed_legacy(connection)
    revision.upgrade()
    assert connection.scalar(text("SELECT role FROM organization_memberships")) == "analyst"
    assert connection.scalar(text("SELECT count(*) FROM documents")) == 1
    assert connection.scalar(text("SELECT uploaded_by FROM documents")) is None
    assert connection.scalar(text("SELECT id FROM users")) == user_id
    assert connection.scalar(text("SELECT id FROM organizations")) == org_id
    revision.downgrade()
    assert connection.scalar(text("SELECT role FROM organization_memberships")) == "member"
    revision.upgrade()
    assert connection.scalar(text("SELECT role FROM organization_memberships")) == "analyst"


def test_upgrade_refuses_duplicates_without_discarding_data(legacy_schema):
    connection, revision = legacy_schema
    seed_legacy(connection, duplicate=True)
    with pytest.raises(RuntimeError, match="duplicate"):
        revision.upgrade()
    assert connection.scalar(text("SELECT count(*) FROM documents")) == 2
    assert connection.scalar(text("SELECT role FROM organization_memberships")) == "member"


def test_downgrade_refuses_loss_of_real_external_identity(legacy_schema):
    connection, revision = legacy_schema
    user_id, _ = seed_legacy(connection)
    revision.upgrade()
    connection.execute(
        text(
            "INSERT INTO user_identities (id,user_id,issuer,subject) "
            "VALUES (:id,:user,'https://issuer.test','verified-sub')"
        ),
        {"id": uuid4(), "user": user_id},
    )
    with pytest.raises(RuntimeError, match="lose Phase 2 data"):
        revision.downgrade()
    assert connection.scalar(text("SELECT count(*) FROM user_identities")) == 1
    assert connection.scalar(text("SELECT role FROM organization_memberships")) == "analyst"
