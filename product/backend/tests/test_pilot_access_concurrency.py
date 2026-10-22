from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.admin import deactivate_user, grant_membership, operator_context, revoke_membership
from app.auth.access import user_active
from app.db.models import OrganizationMembership
from app.operations.models import PilotUserAccess
from tests.recovery_fixtures import db_session as db_session
from tests.recovery_fixtures import recovery_engine as recovery_engine
from tests.test_pilot_access import roster

pytestmark = pytest.mark.integration


def test_concurrent_last_owner_removals_leave_exactly_one_owner(db_session, recovery_engine):
    organization, users = roster(db_session)
    grant_membership(db_session, organization.id, "https://operator.test", "analyst", "owner")
    org_id, actor_id = organization.id, users[0].id
    db_session.commit()
    barrier = Barrier(2)

    def revoke(subject):
        with Session(recovery_engine) as session:
            operator_context(session, actor_id, "Concurrent controlled roster test")
            barrier.wait(5)
            try:
                revoke_membership(session, org_id, "https://operator.test", subject)
                session.commit()
                return "revoked"
            except ValueError:
                session.rollback()
                return "last-owner-blocked"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(revoke, ("owner", "analyst")))
    assert sorted(results) == ["last-owner-blocked", "revoked"]
    with Session(recovery_engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(OrganizationMembership)
                .where(
                    OrganizationMembership.organization_id == org_id,
                    OrganizationMembership.role == "owner",
                )
            )
            == 1
        )


def test_deactivation_serializes_with_current_authority_and_blocks_later_requests(
    db_session, recovery_engine
):
    organization, users = roster(db_session)
    actor, target = users[0].id, users[1].id
    org_id = organization.id
    db_session.commit()
    held, attempting = Event(), Event()

    def authorized_transaction():
        with Session(recovery_engine) as session:
            user_active(session, target)
            held.set()
            assert attempting.wait(5)
            grant = session.scalar(
                select(OrganizationMembership.role).where(
                    OrganizationMembership.organization_id == org_id,
                    OrganizationMembership.user_id == target,
                )
            )
            assert grant == "analyst"
            session.commit()

    def deactivate():
        assert held.wait(5)
        with Session(recovery_engine) as session:
            operator_context(session, actor, "Explicit concurrent local offboarding")
            attempting.set()
            deactivate_user(session, target)
            session.commit()

    with ThreadPoolExecutor(max_workers=2) as pool:
        work = pool.submit(authorized_transaction)
        offboard = pool.submit(deactivate)
        work.result(10)
        offboard.result(10)
    with Session(recovery_engine) as session:
        assert (
            session.scalar(select(PilotUserAccess.active).where(PilotUserAccess.user_id == target))
            is False
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(OrganizationMembership)
                .where(OrganizationMembership.user_id == target)
            )
            == 0
        )
        with pytest.raises(HTTPException) as failure:
            user_active(session, target)
        assert failure.value.status_code == 403
        with pytest.raises(ValueError, match="Reactivate"):
            grant_membership(session, org_id, "https://operator.test", "analyst", "admin")
