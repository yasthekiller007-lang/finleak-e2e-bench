import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import MetaData, text

from app.db.base import Base
from tests.test_phase2_migration import legacy_schema as legacy_schema
from tests.test_phase2_migration import migration, seed_legacy
from tests.test_phase5_migration import phase5

pytestmark = pytest.mark.integration


def phase6(connection):
    phase5(connection)
    revision = migration("0006_recovery_ledger.py")
    revision.upgrade()
    return revision


def test_phase6_legacy_preservation_empty_downgrade_reupgrade_and_schema(legacy_schema):
    connection, _ = legacy_schema
    user, org = seed_legacy(connection)
    revision = phase6(connection)
    # Freeze the Phase 6 comparison to tables available at that migration.
    metadata = MetaData(naming_convention=Base.metadata.naming_convention)
    for name, table in Base.metadata.tables.items():
        if not name.startswith("pilot_"):
            table.to_metadata(metadata)
    context = MigrationContext.configure(connection, opts={"target_metadata": metadata})
    assert compare_metadata(context, metadata) == []
    assert connection.scalar(text("SELECT id FROM users")) == user
    assert connection.scalar(text("SELECT id FROM organizations")) == org
    assert connection.scalar(text("SELECT count(*) FROM documents")) == 1
    revision.downgrade()
    revision.upgrade()
    assert compare_metadata(context, metadata) == []


def test_phase6_authoritative_history_refuses_downgrade(legacy_schema):
    connection, _ = legacy_schema
    actor, org = seed_legacy(connection)
    revision = phase6(connection)
    connection.execute(
        text("""
        INSERT INTO recovery_instruments(id,organization_id,actor_id,audit_id,kind,
            namespace,issuer,reference,currency,identity_hash)
        VALUES(gen_random_uuid(),:org,:actor,gen_random_uuid(),'CASH','bank/fixture',
            'supplier-A','synthetic-row','USD',repeat('a',64))
    """),
        {"org": org, "actor": actor},
    )
    assert (
        connection.scalar(
            text("SELECT count(*) FROM financial_audit WHERE action='recovery.instrument.created'")
        )
        == 1
    )
    with pytest.raises(RuntimeError, match="Recovery Ledger"):
        revision.downgrade()
