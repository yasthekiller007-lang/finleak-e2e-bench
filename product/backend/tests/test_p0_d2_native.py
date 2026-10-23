"""Prepared native checks. Require an explicitly supplied disposable migrated DB.

Not executed in Work Cloud; no identity simulation or role elevation is used.
"""

from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.admin import operator_context
from app.db.models import Organization, OrganizationMembership, User
from app.operations.models import PilotAccessJournal, PilotUserAccess

pytestmark = pytest.mark.integration


def checked_migrator(session):
    assert session.scalar(text("SELECT current_database()")) == "finleak_product_v11_test"
    assert session.scalar(text("SELECT current_user")) == "p0_migrator"
    assert (
        session.scalar(
            text(
                "SELECT rolsuper OR rolcreaterole OR rolcreatedb "
                "FROM pg_roles WHERE rolname=current_user"
            )
        )
        is False
    )


def test_native_attributed_fixture_writes_and_audit_share_transaction(db_session):
    checked_migrator(db_session)
    owner = User(display_name="DEMO D2 operator", email=None)
    db_session.add(owner)
    db_session.flush()
    operator_context(db_session, owner.id, "DEMO D2 native attribution test")
    request = db_session.scalar(text("SELECT current_setting('fla.operator_request')"))
    for _ in range(2):
        organization = Organization(name="DEMO D2 tenant")
        db_session.add(organization)
        db_session.flush()
        db_session.add(
            OrganizationMembership(organization_id=organization.id, user_id=owner.id, role="owner")
        )
        db_session.flush()
        assert db_session.scalar(text("SELECT current_setting('fla.operator_actor')")) == str(
            owner.id
        )
    journal = db_session.scalars(
        select(PilotAccessJournal).where(PilotAccessJournal.actor_id == owner.id)
    ).all()
    assert len(journal) == 4 and {str(r.request_id) for r in journal} == {request}
    assert all(r.db_principal == "p0_migrator" for r in journal)
    # db_session rolls back its outer transaction; immutable audit is not deleted.


def test_native_missing_attribution_is_rejected_without_elevation(db_session):
    checked_migrator(db_session)
    with pytest.raises(DBAPIError), db_session.begin_nested():
        db_session.execute(text("SELECT set_config('fla.operator_actor','',true)"))
        db_session.execute(text("SELECT set_config('fla.operator_reason','',true)"))
        db_session.add(Organization(name="DEMO must be rejected"))
        db_session.flush()


def test_native_unknown_and_disabled_operator_are_rejected(db_session):
    checked_migrator(db_session)
    with pytest.raises(ValueError):
        operator_context(db_session, uuid4(), "DEMO unknown operator")
    owner = User(display_name="DEMO active operator", email=None)
    disabled = User(display_name="DEMO disabled operator", email=None)
    db_session.add_all([owner, disabled])
    db_session.flush()
    operator_context(db_session, owner.id, "DEMO disable synthetic actor")
    db_session.add(PilotUserAccess(user_id=disabled.id, active=False))
    db_session.flush()
    with pytest.raises(ValueError):
        operator_context(db_session, disabled.id, "DEMO rejected disabled operator")
