import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import MetaData, UniqueConstraint, text

from app.db.base import Base
from tests.test_phase2_migration import legacy_schema as legacy_schema
from tests.test_phase2_migration import migration, seed_legacy

pytestmark = pytest.mark.integration


def test_phase4_complete_chain_preserves_data_and_reverses_without_drift(legacy_schema):
    connection, phase2 = legacy_schema
    seed_legacy(connection)
    phase2.upgrade()
    migration("0003_document_intelligence.py").upgrade()
    phase4 = migration("0004_reviewed_financial_engine.py")
    phase4.upgrade()
    phase4_metadata = MetaData(naming_convention=Base.metadata.naming_convention)
    for name, table in Base.metadata.tables.items():
        if name.startswith("pilot_"):
            continue
        if name.startswith("recovery_"):
            continue
        if not name.startswith("proof_"):
            table.to_metadata(phase4_metadata)
    evidence = phase4_metadata.tables["financial_revision_evidence"]
    for constraint in list(evidence.constraints):
        if isinstance(constraint, UniqueConstraint) and set(constraint.columns.keys()) == {
            "organization_id",
            "id",
        }:
            evidence.constraints.remove(constraint)
    context = MigrationContext.configure(connection, opts={"target_metadata": phase4_metadata})
    assert compare_metadata(context, phase4_metadata) == []
    assert connection.scalar(text("SELECT count(*) FROM documents")) == 1
    phase4.downgrade()
    phase4.upgrade()
    assert compare_metadata(context, phase4_metadata) == []


def test_phase4_downgrade_refuses_financial_history_loss(legacy_schema):
    connection, phase2 = legacy_schema
    user, org = seed_legacy(connection)
    phase2.upgrade()
    migration("0003_document_intelligence.py").upgrade()
    phase4 = migration("0004_reviewed_financial_engine.py")
    phase4.upgrade()
    connection.execute(text("UPDATE organization_memberships SET role='owner'"))
    connection.execute(
        text(
            "INSERT INTO reviewed_financial_sources "
            "(id,organization_id,document_id,kind,created_by) "
            "SELECT gen_random_uuid(),organization_id,id,'invoice',:user FROM documents"
        ),
        {"user": user},
    )
    with pytest.raises(RuntimeError, match="lose Phase 4"):
        phase4.downgrade()
