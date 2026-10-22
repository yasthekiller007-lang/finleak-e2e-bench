"""Organization provisioning for trusted database operators, never a public API."""

import argparse
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth.access import tenant_active, user_lock
from app.core.config import Settings
from app.db.models import Organization, OrganizationMembership, User, UserIdentity
from app.db.session import create_database_engine
from app.domain.types import MembershipRole
from app.operations.models import PilotTenantAccess, PilotUserAccess


def operator_context(session, actor_id, reason):
    reason = reason.strip()
    if not reason or len(reason) > 4000 or session.get(User, actor_id) is None:
        raise ValueError("A known operator actor and a 1–4000 character purpose are required")
    if (
        session.scalar(select(PilotUserAccess.active).where(PilotUserAccess.user_id == actor_id))
        is False
    ):
        raise ValueError("The attributed actor is locally deactivated")
    for setting, value in {
        "fla.operator_actor": str(actor_id),
        "fla.operator_reason": reason,
        "fla.operator_request": str(uuid4()),
    }.items():
        session.execute(
            text("SELECT set_config(:setting,:value,true)"), {"setting": setting, "value": value}
        )


def lock_organization(session, organization_id):
    organization = session.scalar(
        select(Organization)
        .where(Organization.id == organization_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if organization is None:
        raise ValueError("Organization does not exist")
    return organization


def checked_identity(session, issuer, subject):
    identity = session.scalar(
        select(UserIdentity).where(UserIdentity.issuer == issuer, UserIdentity.subject == subject)
    )
    if identity is None:
        raise ValueError("Identity must complete verified sign-in before membership is granted")
    return identity


def membership_for(session, organization_id, user_id):
    return session.scalar(
        select(OrganizationMembership)
        .where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def protect_owner(session, membership, new_role=None):
    if membership and membership.role == "owner" and new_role != "owner":
        others = session.scalar(
            select(func.count())
            .select_from(OrganizationMembership)
            .where(
                OrganizationMembership.organization_id == membership.organization_id,
                OrganizationMembership.role == "owner",
                OrganizationMembership.id != membership.id,
            )
        )
        if not others:
            raise ValueError("Transfer ownership before removing the last owner")


def create_organization(session: Session, name: str) -> Organization:
    name = name.strip()
    if not name or len(name) > 200:
        raise ValueError("Organization name must contain 1–200 characters")
    organization = Organization(name=name)
    session.add(organization)
    session.flush()
    return organization


def grant_membership(session: Session, organization_id: UUID, issuer: str, subject: str, role: str):
    if role not in {item.value for item in MembershipRole}:
        raise ValueError("Unknown membership role")
    identity = checked_identity(session, issuer, subject)
    user_lock(session, identity.user_id, exclusive=True)
    lock_organization(session, organization_id)
    tenant_active(session, organization_id)
    if (
        session.scalar(
            select(PilotUserAccess.active).where(PilotUserAccess.user_id == identity.user_id)
        )
        is False
    ):
        raise ValueError("Reactivate access through a separately authorized operator action first")
    membership = membership_for(session, organization_id, identity.user_id)
    protect_owner(session, membership, role)
    if membership is None:
        membership = OrganizationMembership(
            organization_id=organization_id, user_id=identity.user_id, role=role
        )
        session.add(membership)
    else:
        membership.role = role
    session.flush()
    return membership


def revoke_membership(session, organization_id, issuer, subject):
    identity = checked_identity(session, issuer, subject)
    user_lock(session, identity.user_id, exclusive=True)
    lock_organization(session, organization_id)
    membership = membership_for(session, organization_id, identity.user_id)
    protect_owner(session, membership)
    if membership is not None:
        session.delete(membership)
        session.flush()


def transfer_owner(session, organization_id, previous_user, new_user):
    if previous_user == new_user:
        raise ValueError("Ownership transfer requires two distinct users")
    for user_id in sorted({previous_user, new_user}, key=str):
        user_lock(session, user_id, exclusive=True)
    lock_organization(session, organization_id)
    tenant_active(session, organization_id)
    previous = membership_for(session, organization_id, previous_user)
    target = membership_for(session, organization_id, new_user)
    if previous is None or previous.role != "owner" or target is None:
        raise ValueError("Existing owner and enrolled recipient memberships are required")
    if (
        session.scalar(select(PilotUserAccess.active).where(PilotUserAccess.user_id == new_user))
        is False
    ):
        raise ValueError("Ownership recipient is locally deactivated")
    target.role = "owner"
    session.flush()  # establish recipient authority before demoting the prior owner
    previous.role = "admin"
    session.flush()


def deactivate_user(session, user_id):
    if session.get(User, user_id) is None:
        raise ValueError("User does not exist")
    user_lock(session, user_id, exclusive=True)
    memberships = session.scalars(
        select(OrganizationMembership)
        .where(OrganizationMembership.user_id == user_id)
        .order_by(OrganizationMembership.organization_id)
    ).all()
    for membership in memberships:
        lock_organization(session, membership.organization_id)
        protect_owner(session, membership)
    state = session.scalar(select(PilotUserAccess).where(PilotUserAccess.user_id == user_id))
    if state is None:
        session.add(PilotUserAccess(user_id=user_id, active=False))
    else:
        state.active = False
    for membership in memberships:
        session.delete(membership)
    session.flush()


def offboard_tenant(session, organization_id):
    # Same order as admission: wait for full upload/process work before roster removal.
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:org,7005))"),
        {"org": str(organization_id)},
    )
    lock_organization(session, organization_id)
    state = session.scalar(
        select(PilotTenantAccess).where(PilotTenantAccess.organization_id == organization_id)
    )
    if state is None:
        session.add(PilotTenantAccess(organization_id=organization_id, active=False))
    else:
        state.active = False
    session.flush()  # freeze tenant first; explicit offboarding permits last-owner removal
    for membership in session.scalars(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id
        )
    ).all():
        session.delete(membership)
    session.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actor-id", required=True, type=UUID)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--apply", required=True, action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    organization = commands.add_parser("create-organization")
    organization.add_argument("--name", required=True)
    grant = commands.add_parser("grant-membership")
    grant.add_argument("--organization-id", required=True, type=UUID)
    grant.add_argument("--issuer", required=True)
    grant.add_argument("--subject", required=True)
    grant.add_argument("--role", required=True, choices=[item.value for item in MembershipRole])
    revoke = commands.add_parser("revoke-membership")
    revoke.add_argument("--organization-id", required=True, type=UUID)
    revoke.add_argument("--issuer", required=True)
    revoke.add_argument("--subject", required=True)
    transfer = commands.add_parser("transfer-owner")
    transfer.add_argument("--organization-id", required=True, type=UUID)
    transfer.add_argument("--previous-user", required=True, type=UUID)
    transfer.add_argument("--new-user", required=True, type=UUID)
    deactivate = commands.add_parser("deactivate-user")
    deactivate.add_argument("--user-id", required=True, type=UUID)
    offboard = commands.add_parser("offboard-tenant")
    offboard.add_argument("--organization-id", required=True, type=UUID)
    args = parser.parse_args()
    engine = create_database_engine(Settings())
    if engine is None:
        parser.error("Database is not configured")
    try:
        with Session(engine) as session, session.begin():
            operator_context(session, args.actor_id, args.reason)
            if args.command == "create-organization":
                result = str(create_organization(session, args.name).id)
            elif args.command == "grant-membership":
                grant_membership(
                    session, args.organization_id, args.issuer, args.subject, args.role
                )
                result = "Membership saved"
            elif args.command == "revoke-membership":
                revoke_membership(session, args.organization_id, args.issuer, args.subject)
                result = "Membership revoked"
            elif args.command == "transfer-owner":
                transfer_owner(session, args.organization_id, args.previous_user, args.new_user)
                result = "Ownership transferred"
            elif args.command == "deactivate-user":
                deactivate_user(session, args.user_id)
                result = "Local access deactivated; IdP offboarding remains a separate action"
            else:
                offboard_tenant(session, args.organization_id)
                result = "Tenant offboarded; immutable history and originals preserved"
        print(result)
    except ValueError as exc:
        parser.error(str(exc))
    except Exception:
        parser.exit(1, "Operator change failed; use protected diagnostics\n")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
