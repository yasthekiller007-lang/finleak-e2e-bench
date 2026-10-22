import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text

from app.db.base import Base
from tests.test_phase2_migration import legacy_schema as legacy_schema
from tests.test_phase2_migration import migration, seed_legacy
from tests.test_phase6_migration import phase6

pytestmark = pytest.mark.integration


def test_current_intake_head_preserves_legacy_and_empty_roundtrip_has_no_drift(legacy_schema):
    connection, _ = legacy_schema
    user, org = seed_legacy(connection)
    phase6(connection)
    migration("0007_pilot_access.py").upgrade()
    revision = migration("0008_pilot_intake.py")
    revision.upgrade()
    context = MigrationContext.configure(
        connection,
        opts={
            "target_metadata": Base.metadata,
            "include_object": lambda obj, name, type_, reflected, compare_to: (
                not (
                    type_ == "table"
                    and name
                    in {"pilot_source_scans", "pilot_source_releases", "pilot_source_requests"}
                )
            ),
        },
    )
    assert compare_metadata(context, Base.metadata) == []
    assert connection.scalar(text("SELECT id FROM users")) == user
    assert connection.scalar(text("SELECT id FROM organizations")) == org
    assert connection.scalar(text("SELECT count(*) FROM documents")) == 1
    revision.downgrade()
    revision.upgrade()
    assert compare_metadata(context, Base.metadata) == []


def test_intake_history_refuses_destructive_downgrade(legacy_schema):
    import json

    from app.operations.intake_schema import IntakeLimits

    connection, _ = legacy_schema
    user, _ = seed_legacy(connection)
    phase6(connection)
    migration("0007_pilot_access.py").upgrade()
    revision = migration("0008_pilot_intake.py")
    revision.upgrade()
    connection.execute(
        text(
            "INSERT INTO pilot_intake_profiles(id,name,actor_id,configuration) "
            "VALUES(gen_random_uuid(),:name,:actor,cast(:config AS jsonb))"
        ),
        {
            "name": "pilot-intake/1",
            "actor": user,
            "config": json.dumps(IntakeLimits().model_dump()),
        },
    )
    with pytest.raises(RuntimeError, match="admission history"):
        revision.downgrade()
