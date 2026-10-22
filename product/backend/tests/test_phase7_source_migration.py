import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text

from app.db.base import Base
from tests.test_phase2_migration import legacy_schema as legacy_schema
from tests.test_phase2_migration import migration, seed_legacy
from tests.test_phase6_migration import phase6

pytestmark = pytest.mark.integration


def test_source_gate_head_preserves_legacy_and_complete_metadata_roundtrip(legacy_schema):
    connection, _ = legacy_schema
    user, org = seed_legacy(connection)
    phase6(connection)
    for name in ("0007_pilot_access.py", "0008_pilot_intake.py"):
        migration(name).upgrade()
    revision = migration("0009_source_quarantine.py")
    revision.upgrade()
    context = MigrationContext.configure(connection, opts={"target_metadata": Base.metadata})
    assert compare_metadata(context, Base.metadata) == []
    assert connection.scalar(text("SELECT id FROM users")) == user
    assert connection.scalar(text("SELECT id FROM organizations")) == org
    assert connection.scalar(text("SELECT count(*) FROM documents")) == 1
    assert connection.scalar(text("SELECT count(*) FROM pilot_source_scans")) == 0
    revision.downgrade()
    revision.upgrade()
    assert compare_metadata(context, Base.metadata) == []


def test_populated_quarantine_history_is_preserved_and_refuses_downgrade(legacy_schema):
    connection, _ = legacy_schema
    user, org = seed_legacy(connection)
    phase6(connection)
    for name in ("0007_pilot_access.py", "0008_pilot_intake.py"):
        migration(name).upgrade()
    revision = migration("0009_source_quarantine.py")
    revision.upgrade()
    doc = connection.execute(text("SELECT id,sha256,file_size FROM documents")).first()
    connection.execute(
        text(
            "INSERT INTO pilot_source_scans(id,organization_id,document_id,actor_id,"
            "request_key,sequence,sha256,file_size,verdict,scanner_profile,reason) "
            "VALUES(gen_random_uuid(),:org,:doc,:actor,gen_random_uuid(),1,:sha,:size,"
            "'UNAVAILABLE','private-clamav/1','Preserved synthetic failed scan')"
        ),
        {"org": org, "doc": doc.id, "actor": user, "sha": doc.sha256, "size": doc.file_size},
    )
    with pytest.raises(RuntimeError, match="quarantine or release history"):
        revision.downgrade()
    assert connection.scalar(text("SELECT count(*) FROM pilot_source_scans")) == 1
