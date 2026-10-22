import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db.base import Base
from tests.test_phase2_migration import legacy_schema as legacy_schema
from tests.test_phase2_migration import migration, seed_legacy
from tests.test_phase6_migration import phase6

pytestmark = pytest.mark.integration


def access_metadata_only():
    # This historical checkpoint comparison excludes only later admission tables.
    return {
        "include_object": lambda obj, name, type_, reflected, compare_to: (
            not (
                type_ == "table"
                and name
                in {
                    "pilot_intake_profiles",
                    "pilot_intake_attempts",
                    "pilot_source_scans",
                    "pilot_source_releases",
                    "pilot_source_requests",
                }
            )
        )
    }


def test_access_upgrade_preserves_legacy_and_empty_reverse_has_no_schema_drift(legacy_schema):
    connection, _ = legacy_schema
    user, org = seed_legacy(connection)
    phase6(connection)
    revision = migration("0007_pilot_access.py")
    revision.upgrade()
    context = MigrationContext.configure(
        connection, opts={"target_metadata": Base.metadata, **access_metadata_only()}
    )
    assert compare_metadata(context, Base.metadata) == []
    assert connection.scalar(text("SELECT id FROM users")) == user
    assert connection.scalar(text("SELECT id FROM organizations")) == org
    assert connection.scalar(text("SELECT count(*) FROM pilot_access_journal")) == 0
    revision.downgrade()
    revision.upgrade()
    assert compare_metadata(context, Base.metadata) == []
    assert connection.scalar(text("SELECT count(*) FROM documents")) == 1


def test_access_history_refuses_destructive_downgrade_and_owner_edits(legacy_schema):
    connection, _ = legacy_schema
    _, org = seed_legacy(connection)
    phase6(connection)
    revision = migration("0007_pilot_access.py")
    revision.upgrade()
    connection.execute(
        text("UPDATE organizations SET name='Synthetic amended name' WHERE id=:org"), {"org": org}
    )
    assert connection.scalar(text("SELECT count(*) FROM pilot_access_journal")) == 1
    with pytest.raises(RuntimeError, match="operator history"):
        revision.downgrade()
    for statement in (
        "UPDATE pilot_access_journal SET reason='changed'",
        "DELETE FROM pilot_access_journal",
    ):
        with pytest.raises(DBAPIError, match="immutable"):
            with connection.begin_nested():
                connection.execute(text(statement))


def test_deactivated_access_state_cannot_be_erased_to_regain_access(legacy_schema):
    connection, _ = legacy_schema
    user, _ = seed_legacy(connection)
    phase6(connection)
    migration("0007_pilot_access.py").upgrade()
    connection.execute(
        text(
            "INSERT INTO pilot_user_access(id,user_id,active) VALUES(gen_random_uuid(),:user,false)"
        ),
        {"user": user},
    )
    with pytest.raises(DBAPIError, match="cannot be erased"):
        with connection.begin_nested():
            connection.execute(text("DELETE FROM pilot_user_access"))
    assert connection.scalar(text("SELECT active FROM pilot_user_access")) is False
