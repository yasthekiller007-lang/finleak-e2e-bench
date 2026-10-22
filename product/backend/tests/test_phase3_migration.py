import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import MetaData, UniqueConstraint, text

from app.db.base import Base
from tests.test_phase2_migration import legacy_schema as legacy_schema
from tests.test_phase2_migration import migration, seed_legacy

pytestmark = pytest.mark.integration


def test_phase3_preserves_baseline_and_reverses_without_drift(legacy_schema):
    connection, phase2 = legacy_schema
    user, organization = seed_legacy(connection)
    phase2.upgrade()
    phase3 = migration("0003_document_intelligence.py")
    phase3.upgrade()
    assert connection.scalar(text("SELECT count(*) FROM documents")) == 1
    assert connection.scalar(text("SELECT id FROM users")) == user
    assert connection.scalar(text("SELECT id FROM organizations")) == organization
    assert connection.scalar(text("SELECT processing_status FROM documents")) == "pending"
    # Check the exact Phase 3 schema independently of later migrations.
    phase3_metadata = MetaData(naming_convention=Base.metadata.naming_convention)
    for name, table in Base.metadata.tables.items():
        if name.startswith("pilot_"):
            continue
        if name.startswith("recovery_"):
            continue
        if not name.startswith(("financial_", "reviewed_financial_", "proof_")):
            table.to_metadata(phase3_metadata)
    fields = phase3_metadata.tables["extracted_fields"]
    for constraint in list(fields.constraints):
        if isinstance(constraint, UniqueConstraint) and set(constraint.columns.keys()) == {
            "organization_id",
            "document_id",
            "extraction_run_id",
            "id",
        }:
            fields.constraints.remove(constraint)
    context = MigrationContext.configure(connection, opts={"target_metadata": phase3_metadata})
    assert compare_metadata(context, phase3_metadata) == []
    phase3.downgrade()
    phase3.upgrade()
    assert compare_metadata(context, phase3_metadata) == []
    assert connection.scalar(text("SELECT count(*) FROM documents")) == 1


@pytest.mark.parametrize("status", ["needs_review", "needs_ocr"])
def test_phase3_downgrade_refuses_data_loss(legacy_schema, status):
    connection, phase2 = legacy_schema
    seed_legacy(connection)
    phase2.upgrade()
    phase3 = migration("0003_document_intelligence.py")
    phase3.upgrade()
    connection.execute(text("UPDATE documents SET processing_status = :status"), {"status": status})
    with pytest.raises(RuntimeError, match="lose Phase 3 data"):
        phase3.downgrade()
    assert connection.scalar(text("SELECT processing_status FROM documents")) == status
