"""Persist actual PostgreSQL commit timestamps without editing economic history.

The immutable row's insertion timestamp is never a historical known-at cutoff.
Capture runs after financial commit. A crash before capture is repaired from
PostgreSQL commit provenance; unavailable provenance fails closed, never guessed.
"""

from uuid import uuid4

from sqlalchemy import select, text

from app.recovery.models import RecoveryCase, RecoveryPublication, RecoveryRecord
from app.recovery.values import fail


def capture(session, access, budget):
    if session.scalar(text("SELECT current_setting('track_commit_timestamp')")) != "on":
        fail("recovery_known_at_unavailable", "Actual commit provenance is unavailable", 503)
    session.execute(
        text("SELECT id FROM organizations WHERE id=:org FOR UPDATE"),
        {"org": access.organization_id},
    )
    for table, column in ((RecoveryCase, "case_id"), (RecoveryRecord, "record_id")):
        rows = session.execute(
            text(
                f"SELECT s.id, pg_xact_commit_timestamp(s.xmin) AS committed "
                f"FROM {table.__tablename__} s LEFT JOIN recovery_publications p "
                f"ON p.organization_id=s.organization_id AND p.{column}=s.id "
                "WHERE s.organization_id=:org AND p.id IS NULL LIMIT :maximum"
            ),
            {"org": access.organization_id, "maximum": budget.limits.projection_records + 1},
        ).all()
        budget.bound(len(rows), "projection_records")
        for identity, committed in rows:
            if committed is None:
                fail(
                    "recovery_known_at_unavailable", "Actual commit provenance is unavailable", 503
                )
            session.add(
                RecoveryPublication(
                    organization_id=access.organization_id,
                    actor_id=access.user_id,
                    audit_id=uuid4(),
                    committed_at=committed,
                    **{column: identity},
                )
            )
        session.flush()
    budget.check()


def committed(session, access, identity, column="record_id"):
    return session.scalar(
        select(RecoveryPublication.committed_at).where(
            RecoveryPublication.organization_id == access.organization_id,
            getattr(RecoveryPublication, column) == identity,
        )
    )
