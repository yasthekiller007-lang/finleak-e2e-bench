import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.access import tenant_active, user_active
from app.auth.oidc import (
    IdentityProviderUnavailable,
    InvalidIdentityToken,
    VerifiedIdentity,
)
from app.db.models import OrganizationMembership, User, UserIdentity
from app.domain.tenancy import OrganizationContext
from app.domain.types import MembershipRole

bearer = HTTPBearer(auto_error=False)


def verify_identity(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> VerifiedIdentity:
    if credentials is None:
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
    verifier = request.app.state.token_verifier
    if verifier is None:
        raise HTTPException(503, "Identity provider is not configured")
    try:
        return verifier.verify(credentials.credentials)
    except InvalidIdentityToken as exc:
        logging.getLogger("financial_leakage").warning(
            "identity_rejected", extra={"component": "identity", "reason_code": "identity_rejected"}
        )
        raise HTTPException(
            401, "Invalid or expired access token", headers={"WWW-Authenticate": "Bearer"}
        ) from exc
    except IdentityProviderUnavailable as exc:
        logging.getLogger("financial_leakage").warning(
            "identity_unavailable",
            extra={"component": "identity", "reason_code": "identity_unavailable"},
        )
        raise HTTPException(503, "Identity provider is temporarily unavailable") from exc


def get_database_session(request: Request) -> Iterator[Session]:
    engine = request.app.state.database_engine
    if engine is None:
        raise HTTPException(503, "Database is not configured")
    with Session(engine) as session:
        yield session


DatabaseSession = Annotated[Session, Depends(get_database_session)]


def resolve_user(session: Session, identity: VerifiedIdentity) -> User:
    query = (
        select(User)
        .join(UserIdentity, UserIdentity.user_id == User.id)
        .where(UserIdentity.issuer == identity.issuer, UserIdentity.subject == identity.subject)
    )
    user = session.scalar(query)
    if user is not None:
        return user
    try:
        # A losing concurrent login rolls back its new user together with its identity.
        with session.begin_nested():
            user = User(email=identity.email, display_name=identity.display_name)
            session.add(user)
            session.flush()
            session.add(
                UserIdentity(user_id=user.id, issuer=identity.issuer, subject=identity.subject)
            )
            session.flush()
        session.commit()
    except IntegrityError:
        user = session.scalar(query)
        if user is None:
            raise
    return user


def get_authenticated_user(
    identity: Annotated[VerifiedIdentity, Depends(verify_identity)], session: DatabaseSession
) -> User:
    user = resolve_user(session, identity)
    user_active(session, user.id)
    return user


AuthenticatedUser = Annotated[User, Depends(get_authenticated_user)]


@dataclass(frozen=True)
class OrganizationAccess(OrganizationContext):
    role: MembershipRole


def get_organization_access(
    organization_id: UUID, user: AuthenticatedUser, session: DatabaseSession
) -> OrganizationAccess:
    tenant_active(session, organization_id)
    membership = session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user.id,
        )
    )
    # Hide whether an unknown or inaccessible organization exists.
    if membership is None:
        raise HTTPException(404, "Organization not found")
    return OrganizationAccess(organization_id, user.id, MembershipRole(membership.role))


AuthorizedOrganization = Annotated[OrganizationAccess, Depends(get_organization_access)]


def require_document_upload(access: AuthorizedOrganization) -> OrganizationAccess:
    if access.role == MembershipRole.VIEWER:
        raise HTTPException(403, "Your role cannot upload documents")
    return access


UploadOrganization = Annotated[OrganizationAccess, Depends(require_document_upload)]
