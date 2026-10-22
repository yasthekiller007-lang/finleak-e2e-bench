"""Fresh operational access fencing, separate from approved financial policy."""

from fastapi import HTTPException
from sqlalchemy import select, text

from app.operations.models import PilotTenantAccess, PilotUserAccess


def user_lock(session, user_id, *, exclusive=False):
    function = "pg_advisory_xact_lock" if exclusive else "pg_advisory_xact_lock_shared"
    session.execute(text(f"SELECT {function}(hashtextextended(:key, 7002))"), {"key": str(user_id)})


def user_active(session, user_id):
    user_lock(session, user_id)
    active = session.scalar(
        select(PilotUserAccess.active).where(PilotUserAccess.user_id == user_id)
    )
    if active is False:
        raise HTTPException(403, "Local access is deactivated")


def tenant_active(session, organization_id):
    active = session.scalar(
        select(PilotTenantAccess.active).where(PilotTenantAccess.organization_id == organization_id)
    )
    if active is False:
        raise HTTPException(404, "Organization not found")
