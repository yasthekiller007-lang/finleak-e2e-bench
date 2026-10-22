"""PostgreSQL worker-shared admission; counters are operational, never financial totals."""

from contextlib import contextmanager, nullcontext

from sqlalchemy import Connection, func, select, text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth.access import tenant_active, user_active
from app.db.models import OrganizationMembership
from app.operations.models import PilotIntakeAttempt, PilotIntakeProfile


class IntakeError(Exception):
    def __init__(self, code, status=429):
        self.code, self.status = code, status
        super().__init__(code)


class IntakeCoordinator:
    def __init__(self, engine):
        self.engine = engine

    @contextmanager
    def reserve(self, access, operation, limits):
        if operation not in {"upload", "process"}:
            raise ValueError("Unsupported intake operation")
        if self.engine is None:
            raise IntakeError("intake_database_unavailable", 503)
        # Explicit externally owned connections support isolated transactional fixtures.
        # Application startup always supplies its real Engine; no environment bypass exists.
        held = []
        admitted = False
        try:
            connection_scope = (
                nullcontext(self.engine)
                if isinstance(self.engine, Connection)
                else self.engine.connect()
            )
            with connection_scope as connection:
                try:
                    with Session(connection, join_transaction_mode="create_savepoint") as session:
                        # Tenant offboarding does not take the user fence until work drains.
                        # Hold only its session fence. User authority is transaction-fenced:
                        # a second connection must not queue behind revocation while this
                        # connection itself keeps that revocation waiting.
                        for namespace, identity in ((7005, access.organization_id),):
                            session.execute(
                                text(
                                    "SELECT pg_advisory_lock_shared("
                                    "hashtextextended(:key,:namespace))"
                                ),
                                {"key": str(identity), "namespace": namespace},
                            )
                            held.append(("shared", str(identity), namespace))
                        user_active(session, access.user_id)
                        tenant_active(session, access.organization_id)
                        membership = session.scalar(
                            select(OrganizationMembership).where(
                                OrganizationMembership.organization_id == access.organization_id,
                                OrganizationMembership.user_id == access.user_id,
                            )
                        )
                        from fastapi import HTTPException

                        if membership is None:
                            raise HTTPException(404, "Organization not found")
                        if membership.role == "viewer":
                            raise HTTPException(403, "Your role cannot submit documents")
                        for slot in range(getattr(limits, operation + "_slots")):
                            key = f"{access.organization_id}:{operation}:{slot}"
                            if session.scalar(
                                text("SELECT pg_try_advisory_lock(hashtextextended(:key,7003))"),
                                {"key": key},
                            ):
                                held.append(("exclusive", key, 7003))
                                break
                        else:
                            raise IntakeError("intake_tenant_busy")
                        session.execute(
                            text("SELECT pg_advisory_xact_lock(hashtextextended(:profile,7006))"),
                            {"profile": limits.profile},
                        )
                        configured = session.scalar(
                            select(PilotIntakeProfile).where(
                                PilotIntakeProfile.name == limits.profile
                            )
                        )
                        value = limits.model_dump(mode="json")
                        if configured is None:
                            session.add(
                                PilotIntakeProfile(
                                    name=limits.profile,
                                    actor_id=access.user_id,
                                    configuration=value,
                                )
                            )
                            session.flush()
                        elif configured.configuration != value:
                            raise IntakeError("intake_profile_mismatch", 503)
                        session.execute(
                            text("SELECT pg_advisory_xact_lock(hashtextextended(:actor,7004))"),
                            {"actor": str(access.user_id)},
                        )
                        count = session.scalar(
                            select(func.count())
                            .select_from(PilotIntakeAttempt)
                            .where(
                                PilotIntakeAttempt.actor_id == access.user_id,
                                PilotIntakeAttempt.created_at
                                >= func.clock_timestamp() - text("interval '1 minute'"),
                            )
                        )
                        if count >= limits.actor_operations_per_minute:
                            raise IntakeError("intake_actor_rate_limit")
                        attempt = PilotIntakeAttempt(
                            organization_id=access.organization_id,
                            actor_id=access.user_id,
                            profile=limits.profile,
                            operation=operation,
                            slot=slot,
                        )
                        session.add(attempt)
                        session.flush()
                        identifier = attempt.id
                        # Counters survive errors/rollbacks in the actual operation.
                        session.commit()
                        admitted = True
                    yield identifier
                finally:
                    try:
                        # Roll back any failed admission transaction before releasing session locks.
                        if connection.in_transaction() and not isinstance(self.engine, Connection):
                            connection.rollback()
                        for mode, key, namespace in reversed(held):
                            function = (
                                "pg_advisory_unlock_shared"
                                if mode == "shared"
                                else "pg_advisory_unlock"
                            )
                            released = connection.scalar(
                                text(f"SELECT {function}(hashtextextended(:key,:namespace))"),
                                {"key": key, "namespace": namespace},
                            )
                            if not released:
                                raise IntakeError("intake_lock_release_unavailable", 503)
                        if not isinstance(self.engine, Connection):
                            connection.rollback()
                    except Exception:
                        connection.invalidate()  # never return a locked backend to the pool
                        raise IntakeError("intake_lock_release_unavailable", 503) from None
        except DBAPIError as error:
            if admitted:
                raise
            if getattr(error.orig, "sqlstate", None) == "P7001":
                raise IntakeError("intake_actor_rate_limit") from None
            raise IntakeError("intake_database_unavailable", 503) from None
        except SQLAlchemyError:
            if admitted:
                raise
            raise IntakeError("intake_database_unavailable", 503) from None
