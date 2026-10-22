import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import MetaData, text

from app.db.base import Base
from tests.test_phase2_migration import legacy_schema as legacy_schema
from tests.test_phase2_migration import migration, seed_legacy

pytestmark = pytest.mark.integration


def phase5(connection):
    migration("0002_identity_membership_uploads.py").upgrade()
    migration("0003_document_intelligence.py").upgrade()
    migration("0004_reviewed_financial_engine.py").upgrade()
    result = migration("0005_leakage_proof_engine.py")
    result.upgrade()
    return result


def test_phase5_populated_legacy_preservation_and_empty_reverse_without_drift(legacy_schema):
    connection, _ = legacy_schema
    user, org = seed_legacy(connection)
    revision = phase5(connection)
    metadata = MetaData(naming_convention=Base.metadata.naming_convention)
    for name, table in Base.metadata.tables.items():
        if name.startswith("pilot_"):
            continue
        if not name.startswith("recovery_"):
            table.to_metadata(metadata)
    context = MigrationContext.configure(connection, opts={"target_metadata": metadata})
    assert compare_metadata(context, metadata) == []
    assert connection.scalar(text("SELECT id FROM users")) == user
    assert connection.scalar(text("SELECT id FROM organizations")) == org
    assert connection.scalar(text("SELECT count(*) FROM documents")) == 1
    revision.downgrade()
    revision.upgrade()
    assert compare_metadata(context, metadata) == []


def test_database_canonical_matches_independent_wire_profile(legacy_schema):
    connection, _ = legacy_schema
    seed_legacy(connection)
    phase5(connection)
    raw = '{"z":"\\n\\t\\"\\\\/","a":"é😀é","n":null,"i":7}'
    expected = '{"a":"é😀é","i":7,"n":null,"z":"\\u000a\\u0009\\"\\\\/"}'
    assert (
        connection.scalar(text("SELECT proof_canonical(CAST(:raw AS jsonb))"), {"raw": raw})
        == expected
    )


def test_phase5_failed_operation_history_refuses_downgrade(legacy_schema):
    connection, _ = legacy_schema
    user, org = seed_legacy(connection)
    revision = phase5(connection)
    connection.execute(
        text(
            "INSERT INTO proof_requests(id,organization_id,actor_id,audit_id,"
            "request_key,request_hash,command,counted,result) "
            "VALUES(gen_random_uuid(),:org,:actor,gen_random_uuid(),"
            "gen_random_uuid()::text,repeat('a',64),'generate',true,"
            '\'{"error":{"code":"proof_integrity_failure"}}\')'
        ),
        {"org": org, "actor": user},
    )
    with pytest.raises(RuntimeError, match="lose Phase 5"):
        revision.downgrade()
    assert (
        connection.scalar(
            text("SELECT count(*) FROM financial_audit WHERE action='proof.operation.failed'")
        )
        == 1
    )
