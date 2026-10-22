import pytest
from sqlalchemy import func, select

from app.admin import create_organization, grant_membership
from app.auth.dependencies import resolve_user
from app.auth.oidc import VerifiedIdentity
from app.db.models import OrganizationMembership

pytestmark = pytest.mark.integration


def test_provisioning_requires_existing_verified_identity_and_updates_in_place(db_session):
    organization = create_organization(db_session, "New organization")
    with pytest.raises(ValueError, match="verified sign-in"):
        grant_membership(db_session, organization.id, "https://issuer.test", "new-sub", "owner")
    user = resolve_user(db_session, VerifiedIdentity("https://issuer.test", "new-sub"))
    membership = grant_membership(
        db_session, organization.id, "https://issuer.test", "new-sub", "owner"
    )
    assert membership.user_id == user.id and membership.role == "owner"
    # A real role update cannot leave the tenant without an owner.
    successor = resolve_user(db_session, VerifiedIdentity("https://issuer.test", "successor"))
    grant_membership(db_session, organization.id, "https://issuer.test", "successor", "owner")
    again = grant_membership(
        db_session, organization.id, "https://issuer.test", "new-sub", "viewer"
    )
    assert again.id == membership.id and again.role == "viewer"
    assert db_session.scalar(select(func.count()).select_from(OrganizationMembership)) == 2
    assert successor.id != user.id
