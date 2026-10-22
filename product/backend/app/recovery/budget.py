"""PostgreSQL-shared recovery capacity, quotas and complete-operation bounds."""

import hashlib
import time

from sqlalchemy import event, func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import Pool

from app.proof.budget import Budget as SourceBudget
from app.recovery.models import RecoveryRequest
from app.recovery.values import fail


class Budget(SourceBudget):
    def __init__(self, limits):
        super().__init__(limits)
        self.source_ids, self.binding_ids = set(), set()

    def track(self, sources=(), bindings=()):
        self.source_ids.update(sources)
        self.binding_ids.update(bindings)
        self.bound(len(self.source_ids), "documents")
        self.bound(len(self.binding_ids), "bindings")

    def check(self):
        if time.monotonic() - self.started >= self.limits.work_seconds:
            fail("recovery_work_budget", "Recovery work budget exceeded", 503)

    def bound(self, value, name):
        self.check()
        if value > getattr(self.limits, name):
            fail("recovery_resource_limit", "Recovery operation exceeds its bounded profile", 413)


def lock_key(value):
    return int.from_bytes(hashlib.sha256(value.encode()).digest()[:8], "big", signed=True)


def admit(session, access, budget):
    session.info["recovery_budget"] = budget
    session.connection().info["recovery_budget"] = budget
    budget.check()
    timeout = max(1, int((budget.limits.work_seconds - (time.monotonic() - budget.started)) * 1000))
    session.execute(
        text(
            "SELECT set_config('statement_timeout', :v, true), set_config('lock_timeout', :v, true)"
        ),
        {"v": str(timeout)},
    )
    for slot in range(budget.limits.tenant_concurrency):
        if session.scalar(
            text("SELECT pg_try_advisory_xact_lock(:k)"),
            {"k": lock_key(f"FLA-RECOVERY-SLOT/1:{access.organization_id}:{slot}")},
        ):
            return
    fail("recovery_busy", "Tenant recovery capacity is busy; retry later", 429)


def quota(session, access, budget):
    session.execute(
        text("SELECT pg_advisory_xact_lock(:k)"),
        {"k": lock_key(f"FLA-RECOVERY-ACTOR/1:{access.user_id}")},
    )
    count = session.scalar(
        select(func.count())
        .select_from(RecoveryRequest)
        .where(
            RecoveryRequest.actor_id == access.user_id,
            RecoveryRequest.counted.is_(True),
            RecoveryRequest.created_at >= func.clock_timestamp() - text("interval '1 minute'"),
        )
    )
    budget.check()
    if count >= budget.limits.actor_operations_per_minute:
        fail("recovery_rate_limit", "Recovery authority rate exceeded; retry later", 429)


@event.listens_for(Session, "after_begin")
def attach_sql_budget(session, transaction, connection):
    if "recovery_budget" in session.info:
        connection.info["recovery_budget"] = session.info["recovery_budget"]


@event.listens_for(Engine, "before_cursor_execute")
def remaining_sql_budget(connection, cursor, statement, parameters, context, executemany):
    budget = connection.info.get("recovery_budget")
    if budget is None or statement.lstrip().upper().startswith(("ROLLBACK", "RELEASE SAVEPOINT")):
        return
    budget.check()
    milliseconds = max(
        1, int((budget.limits.work_seconds - (time.monotonic() - budget.started)) * 1000)
    )
    # Direct cursor execution avoids re-entering the SQLAlchemy event. Includes
    # ORM flush INSERTs, raw SQL, lock waits and every worker connection.
    cursor.execute(
        "SELECT set_config('statement_timeout', %s, true), set_config('lock_timeout', %s, true)",
        (str(milliseconds), str(milliseconds)),
    )


@event.listens_for(Pool, "checkin")
def clear_sql_budget(dbapi_connection, connection_record):
    connection_record.info.pop("recovery_budget", None)
