from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.auth.dependencies import AuthenticatedUser, DatabaseSession
from app.db.models import Organization, OrganizationMembership
from app.domain.types import MembershipRole

router = APIRouter(prefix="/api/v1", tags=["identity"])


class OrganizationSummary(BaseModel):
    id: UUID
    name: str
    role: MembershipRole


class CurrentUser(BaseModel):
    id: UUID
    email: str | None
    display_name: str
    organizations: list[OrganizationSummary]
    max_upload_bytes: int


@router.get("/me", response_model=CurrentUser)
def current_user(
    user: AuthenticatedUser, session: DatabaseSession, request: Request
) -> CurrentUser:
    rows = session.execute(
        select(Organization, OrganizationMembership.role)
        .join(OrganizationMembership, OrganizationMembership.organization_id == Organization.id)
        .where(OrganizationMembership.user_id == user.id)
        .order_by(Organization.name, Organization.id)
    ).all()
    return CurrentUser(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        organizations=[
            OrganizationSummary(id=org.id, name=org.name, role=role) for org, role in rows
        ],
        max_upload_bytes=request.app.state.settings.max_upload_bytes,
    )
