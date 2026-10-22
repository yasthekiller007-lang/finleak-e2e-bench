"""Real PostgreSQL admission, without worker-local counters or expiring leases."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier, Event
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.admin import deactivate_user, offboard_tenant, operator_context
from app.auth.dependencies import OrganizationAccess
from app.db.models import Organization, OrganizationMembership
from app.domain.types import MembershipRole
from app.operations.intake import IntakeCoordinator, IntakeError
from app.operations.intake_schema import IntakeLimits
from app.operations.models import PilotIntakeAttempt, PilotIntakeProfile
from tests.recovery_fixtures import recovery_engine as recovery_engine
from tests.test_pilot_access import roster


@pytest.fixture
def intake_access(recovery_engine):
    with Session(recovery_engine) as session:
        organization, users = roster(session)
        access = OrganizationAccess(organization.id, users[1].id, MembershipRole.ANALYST)
        owner, viewer = users[0].id, users[2].id
        session.commit()
    return recovery_engine, access, owner, viewer


@pytest.fixture
def second_worker(intake_access):
    engine = intake_access[0]
    with engine.connect() as connection:
        schema = connection.scalar(text("SELECT current_schema()"))
    assert schema.replace("_", "").isalnum()
    worker = create_engine(
        engine.url, connect_args={"options": f"-c search_path={schema} -c statement_timeout=5000"}
    )
    try:
        yield worker
    finally:
        worker.dispose()


@pytest.mark.integration
@pytest.mark.parametrize("operation,slots", [("upload", 2), ("process", 1)])
def test_tenant_capacity_is_shared_between_independent_worker_pools(
    intake_access, second_worker, operation, slots
):
    from contextlib import ExitStack

    engine, access, _, _ = intake_access
    limits = IntakeLimits()
    first, second = IntakeCoordinator(engine), IntakeCoordinator(second_worker)
    with ExitStack() as active:
        for _ in range(slots):
            active.enter_context(first.reserve(access, operation, limits))
        with pytest.raises(IntakeError, match="intake_tenant_busy"):
            with second.reserve(access, operation, limits):
                pytest.fail("A second worker multiplied the tenant capacity")
    with second.reserve(access, operation, limits):
        pass
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(PilotIntakeAttempt)) == slots + 1
        assert not session.scalar(
            text(
                "SELECT EXISTS(SELECT 1 FROM pg_locks WHERE locktype='advisory' "
                "AND pid=pg_backend_pid() AND objsubid=1)"
            )
        )


@pytest.mark.integration
def test_actor_quota_is_atomic_across_simultaneous_workers_and_operations(intake_access):
    engine, access, _, _ = intake_access
    limits = IntakeLimits(upload_slots=4, process_slots=4, actor_operations_per_minute=2)
    ready = Barrier(3)

    def submit(index):
        ready.wait(5)
        try:
            with IntakeCoordinator(engine).reserve(
                access, "process" if index else "upload", limits
            ):
                return "admitted"
        except IntakeError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(submit, range(3)))
    assert sorted(results) == ["admitted", "admitted", "intake_actor_rate_limit"]
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(PilotIntakeAttempt)) == 2


@pytest.mark.integration
def test_actor_quota_cannot_be_multiplied_by_switching_tenant(intake_access):
    engine, access, _, _ = intake_access
    limits = IntakeLimits(actor_operations_per_minute=1)
    with Session(engine) as session:
        other = Organization(name="Another authorized synthetic tenant")
        session.add(other)
        session.flush()
        session.add(
            OrganizationMembership(organization_id=other.id, user_id=access.user_id, role="analyst")
        )
        other_access = OrganizationAccess(other.id, access.user_id, MembershipRole.ANALYST)
        session.commit()
    with IntakeCoordinator(engine).reserve(access, "upload", limits):
        pass
    with pytest.raises(IntakeError, match="intake_actor_rate_limit"):
        with IntakeCoordinator(engine).reserve(other_access, "process", limits):
            pytest.fail("Changing tenant bypassed the actor quota")


@pytest.mark.integration
def test_failed_operation_still_counts_and_releases_every_capacity_lock(intake_access):
    engine, access, _, _ = intake_access
    limits = IntakeLimits(actor_operations_per_minute=2)
    with pytest.raises(ValueError, match="Synthetic business failure"):
        with IntakeCoordinator(engine).reserve(access, "process", limits):
            raise ValueError("Synthetic business failure")
    with IntakeCoordinator(engine).reserve(access, "process", limits):
        pass
    with pytest.raises(IntakeError, match="intake_actor_rate_limit"):
        with IntakeCoordinator(engine).reserve(access, "process", limits):
            pytest.fail("A failed operation erased its committed admission counter")


@pytest.mark.integration
def test_worker_cannot_reinterpret_an_existing_profile(intake_access, second_worker):
    engine, access, _, _ = intake_access
    with IntakeCoordinator(engine).reserve(access, "upload", IntakeLimits()):
        pass
    with pytest.raises(IntakeError, match="intake_profile_mismatch"):
        with IntakeCoordinator(second_worker).reserve(
            access, "upload", IntakeLimits(upload_slots=4)
        ):
            pytest.fail("A worker changed the profile without a versioned deployment decision")
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(PilotIntakeProfile)) == 1
        assert session.scalar(select(PilotIntakeProfile.configuration))["upload_slots"] == 2


@pytest.mark.integration
def test_stale_viewer_or_removed_membership_never_obtains_admission(intake_access):
    engine, access, _, viewer = intake_access
    stale = OrganizationAccess(access.organization_id, viewer, MembershipRole.OWNER)
    with pytest.raises(HTTPException) as error:
        with IntakeCoordinator(engine).reserve(stale, "upload", IntakeLimits()):
            pytest.fail("Stale role was trusted")
    assert error.value.status_code == 403
    missing = OrganizationAccess(uuid4(), access.user_id, MembershipRole.OWNER)
    with pytest.raises(HTTPException) as error:
        with IntakeCoordinator(engine).reserve(missing, "upload", IntakeLimits()):
            pytest.fail("Absent membership was trusted")
    assert error.value.status_code == 404
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(PilotIntakeAttempt)) == 0


@pytest.mark.integration
def test_offboarding_waits_for_actual_admitted_work_not_just_counter_commit(intake_access):
    engine, access, owner, _ = intake_access
    admitted, attempting, may_finish, finished = Event(), Event(), Event(), Event()

    def operate():
        with IntakeCoordinator(engine).reserve(access, "process", IntakeLimits()):
            admitted.set()
            assert may_finish.wait(5)

    def offboard():
        assert admitted.wait(5)
        with Session(engine) as session:
            operator_context(session, owner, "Synthetic admitted operation fencing")
            attempting.set()
            offboard_tenant(session, access.organization_id)
            session.commit()
        finished.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        work = pool.submit(operate)
        removal = pool.submit(offboard)
        try:
            assert attempting.wait(5)
            assert not finished.wait(0.1)
        finally:
            may_finish.set()
        work.result(10)
        removal.result(10)
    assert finished.is_set()
    with pytest.raises(HTTPException) as error:
        with IntakeCoordinator(engine).reserve(access, "process", IntakeLimits()):
            pytest.fail("Offboarded tenant could submit more work")
    assert error.value.status_code == 404


@pytest.mark.integration
def test_revocation_between_business_commits_cannot_deadlock_a_second_connection(intake_access):
    from app.financial.service import lock_authority

    engine, access, owner, _ = intake_access
    with IntakeCoordinator(engine).reserve(access, "process", IntakeLimits()):
        with ThreadPoolExecutor(max_workers=1) as pool:

            def revoke():
                with Session(engine) as session:
                    operator_context(session, owner, "Explicit mid-operation revocation")
                    deactivate_user(session, access.user_id)
                    session.commit()

            pool.submit(revoke).result(5)
        with Session(engine) as session:
            with pytest.raises(HTTPException) as error:
                lock_authority(session, access)
            assert error.value.status_code == 403


@pytest.mark.integration
def test_database_rejects_missing_slot_quota_backdating_and_history_mutation(intake_access):
    engine, access, _, _ = intake_access
    limits = IntakeLimits(actor_operations_per_minute=1)
    with IntakeCoordinator(engine).reserve(access, "process", limits):
        pass
    with Session(engine) as session:
        for statement in (
            "UPDATE pilot_intake_profiles SET configuration='{}'::jsonb",
            "DELETE FROM pilot_intake_profiles",
            "UPDATE pilot_intake_attempts SET created_at='2000-01-01'",
            "DELETE FROM pilot_intake_attempts",
        ):
            with pytest.raises(DBAPIError, match="immutable"):
                with session.begin_nested():
                    session.execute(text(statement))
        fields = dict(
            organization_id=access.organization_id,
            actor_id=access.user_id,
            profile=limits.profile,
            operation="process",
            slot=0,
            created_at=datetime(2000, 1, 1, tzinfo=UTC),
        )
        with pytest.raises(DBAPIError, match="slot must be held"):
            with session.begin_nested():
                session.add(PilotIntakeAttempt(**fields))
                session.flush()
        key = f"{access.organization_id}:process:0"
        session.execute(text("SELECT pg_advisory_lock(hashtextextended(:key,7003))"), {"key": key})
        try:
            with pytest.raises(DBAPIError, match="Shared actor admission limit reached"):
                with session.begin_nested():
                    session.add(PilotIntakeAttempt(**fields))
                    session.flush()
        finally:
            assert session.scalar(
                text("SELECT pg_advisory_unlock(hashtextextended(:key,7003))"), {"key": key}
            )


def test_unconfigured_admission_is_explicitly_unavailable():
    with pytest.raises(IntakeError, match="intake_database_unavailable"):
        with IntakeCoordinator(None).reserve(None, "upload", IntakeLimits()):
            pytest.fail("Unconfigured admission silently fell back to worker-local state")
