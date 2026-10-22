"""Operator authority, journal attribution, offboarding and database integrity."""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import DBAPIError

from app.admin import (
    create_organization,
    deactivate_user,
    grant_membership,
    offboard_tenant,
    operator_context,
    revoke_membership,
    transfer_owner,
)
from app.auth.access import tenant_active, user_active
from app.auth.dependencies import resolve_user
from app.auth.oidc import VerifiedIdentity
from app.db.models import Organization, OrganizationMembership
from app.operations.models import PilotAccessJournal, PilotTenantAccess, PilotUserAccess
from app.operations.roles import Roles, bootstrap, grant_runtime
from tests.test_documents import api as api
from tests.test_documents import headers, path, upload


def roster(session):
    users = [
        resolve_user(session, VerifiedIdentity("https://operator.test", name))
        for name in ("owner", "analyst", "viewer")
    ]
    operator_context(session, users[0].id, "Explicit synthetic operator enrollment")
    organization = create_organization(session, "Synthetic controlled tenant")
    for user, role in zip(users, ("owner", "analyst", "viewer"), strict=True):
        grant_membership(
            session,
            organization.id,
            "https://operator.test",
            ("owner", "analyst", "viewer")[users.index(user)],
            role,
        )
    return organization, users


@pytest.mark.integration
def test_last_owner_revoke_demotion_and_deactivation_require_explicit_transfer(db_session):
    organization, users = roster(db_session)
    for action in (
        lambda: revoke_membership(db_session, organization.id, "https://operator.test", "owner"),
        lambda: grant_membership(
            db_session, organization.id, "https://operator.test", "owner", "viewer"
        ),
        lambda: deactivate_user(db_session, users[0].id),
    ):
        with pytest.raises(ValueError, match="last owner"):
            action()
    transfer_owner(db_session, organization.id, users[0].id, users[1].id)
    assert (
        db_session.scalar(
            select(OrganizationMembership.role).where(OrganizationMembership.user_id == users[1].id)
        )
        == "owner"
    )
    assert (
        db_session.scalar(
            select(OrganizationMembership.role).where(OrganizationMembership.user_id == users[0].id)
        )
        == "admin"
    )
    deactivate_user(db_session, users[0].id)
    assert (
        db_session.scalar(
            select(PilotUserAccess.active).where(PilotUserAccess.user_id == users[0].id)
        )
        is False
    )
    with pytest.raises(HTTPException) as failure:
        user_active(db_session, users[0].id)
    assert failure.value.status_code == 403
    with pytest.raises(ValueError, match="Reactivate"):
        grant_membership(db_session, organization.id, "https://operator.test", "owner", "admin")
    entries = db_session.scalars(
        select(PilotAccessJournal).where(
            or_(
                PilotAccessJournal.organization_id == organization.id,
                PilotAccessJournal.user_id.in_([user.id for user in users]),
            )
        )
    ).all()
    assert entries and all(row.actor_id == users[0].id for row in entries)
    assert all(row.db_principal and row.request_id and row.reason for row in entries)
    assert not any("email" in row.detail or "name" in row.detail for row in entries)


@pytest.mark.integration
def test_explicit_tenant_offboarding_preserves_identity_and_journal(db_session):
    organization, users = roster(db_session)
    offboard_tenant(db_session, organization.id)
    before = db_session.scalar(select(func.count()).select_from(PilotAccessJournal))
    assert db_session.get(Organization, organization.id) is not None
    assert db_session.scalar(select(func.count()).select_from(OrganizationMembership)) == 0
    assert db_session.scalar(select(PilotTenantAccess.active)) is False
    with pytest.raises(HTTPException) as failure:
        tenant_active(db_session, organization.id)
    assert failure.value.status_code == 404
    with pytest.raises(HTTPException):
        grant_membership(db_session, organization.id, "https://operator.test", "analyst", "owner")
    offboard_tenant(db_session, organization.id)
    assert db_session.scalar(select(func.count()).select_from(PilotAccessJournal)) == before
    assert users[1].id is not None


@pytest.mark.integration
@pytest.mark.parametrize(
    "table,column",
    [
        ("users", "id"),
        ("organizations", "id"),
        ("organization_memberships", "id"),
        ("organization_memberships", "user_id"),
        ("user_identities", "user_id"),
    ],
)
def test_stable_access_identity_cannot_be_reassigned_even_by_table_owner(db_session, table, column):
    roster(db_session)
    with pytest.raises(DBAPIError, match="identity"):
        with db_session.begin_nested():
            db_session.execute(text(f"UPDATE {table} SET {column}=:other"), {"other": uuid4()})


@pytest.mark.integration
def test_operator_role_cannot_mutate_without_attribution_or_erase_journal(db_session):
    organization, users = roster(db_session)
    suffix = uuid4().hex[:18]
    roles = Roles("app_" + suffix, "migration_" + suffix, "operator_" + suffix)
    bootstrap(db_session.connection(), roles)
    grant_runtime(db_session.connection(), roles)
    db_session.execute(text("SELECT set_config('fla.operator_actor','',true)"))
    with db_session.begin_nested():
        db_session.execute(text(f'SET LOCAL ROLE "{roles.operator}"'))
        with pytest.raises(DBAPIError, match="Attributed operator"):
            with db_session.begin_nested():
                db_session.execute(
                    text("UPDATE organization_memberships SET role='viewer' WHERE user_id=:user"),
                    {"user": users[0].id},
                )
        operator_context(db_session, users[0].id, "Approved owner transfer test")
        transfer_owner(db_session, organization.id, users[0].id, users[1].id)
        with pytest.raises(DBAPIError):
            with db_session.begin_nested():
                db_session.execute(text("DELETE FROM pilot_access_journal"))
        with pytest.raises(DBAPIError, match="last owner"):
            with db_session.begin_nested():
                db_session.execute(
                    text("DELETE FROM organization_memberships WHERE user_id=:user"),
                    {"user": users[1].id},
                )
        db_session.execute(text("RESET ROLE"))
    with pytest.raises(DBAPIError, match="immutable"):
        with db_session.begin_nested():
            db_session.execute(text("UPDATE pilot_access_journal SET reason='replaced'"))


@pytest.mark.integration
def test_deactivated_same_token_cannot_read_or_write_and_history_survives(api):
    document = upload(api).json()
    operator_context(api["session"], api["users"]["b"].id, "Explicit synthetic offboarding")
    deactivate_user(api["session"], api["users"]["a"].id)
    assert api["client"].get(path(api), headers=headers(api)).status_code == 403
    assert upload(api).status_code == 403
    assert len(list(api["root"].rglob("source"))) == 1
    assert document["sha256"]
