"""Scoped PostgreSQL repository. No writes to financial/source/decision tables."""

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from app.auth.access import tenant_active
from app.db.models import OrganizationMembership
from app.financial.service import fail
from app.saved_views.models import SavedExceptionView as V
from app.saved_views.schema import MAX_REVISION, CreateView, Definition, normalized_name


def scope(access):
    return (V.organization_id == access.organization_id, V.user_id == access.user_id)


def scoped_query(access, view_id):
    return select(V).where(*scope(access), V.id == view_id)


def lock_membership(session, access):
    # Serialize personal writes and fence membership deletion. Identity is backend-derived.
    member = session.scalar(
        select(OrganizationMembership.id)
        .where(
            OrganizationMembership.organization_id == access.organization_id,
            OrganizationMembership.user_id == access.user_id,
        )
        .with_for_update()
    )
    tenant_active(session, access.organization_id)
    if member is None:
        fail("SAVED_VIEW_ACCESS", "Organization not found", 404)


def detail(session, access, view_id):
    row = session.scalar(scoped_query(access, view_id))
    if (
        row is None
        or row.organization_id != access.organization_id
        or row.user_id != access.user_id
    ):
        fail("SAVED_VIEW_NOT_FOUND", "Personal view not found", 404)
    return row


def serialize(row):
    # Stored versions and criteria are validated on read too; never silently drop unknown fields.
    definition = Definition.model_validate(
        {
            "view_type": row.view_type,
            "format_version": row.format_version,
            "criteria": row.criteria,
            "page_size": row.page_size,
        }
    )
    return {
        "id": str(row.id),
        "organization_id": str(row.organization_id),
        "user_id": str(row.user_id),
        "name": row.name,
        **definition.model_dump(mode="json", exclude_none=True),
        "revision": row.revision,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def list_statement(access, search, view_type, limit, after):
    stmt = select(V).where(*scope(access))
    if search:
        pattern = (
            normalized_name(search).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        stmt = stmt.where(V.normalized_name.like("%" + pattern + "%", escape="\\"))
    if view_type:
        stmt = stmt.where(V.view_type == view_type)
    if after:
        stmt = stmt.where(V.id > after)
    return stmt.order_by(V.id.asc()).limit(limit + 1)


def listing(session, access, search, view_type, limit, after):
    rows = list(session.scalars(list_statement(access, search, view_type, limit, after)).all())
    more = len(rows) > limit
    rows = rows[:limit]
    return {
        "items": [serialize(r) for r in rows],
        "limit": limit,
        "has_more": more,
        "next_after": str(rows[-1].id) if more else None,
        "max_views": 50,
    }


def flush(session):
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        fail(
            "SAVED_VIEW_DUPLICATE",
            "Personal view name or quota conflict. Reload your views.",
            409,
        )


def create(session, access, body: CreateView):
    lock_membership(session, access)
    slots = set(session.scalars(select(V.slot).where(*scope(access)).limit(50)).all())
    slot = next((n for n in range(1, 51) if n not in slots), None)
    if slot is None:
        fail(
            "SAVED_VIEW_LIMIT",
            "The limit is 50 personal views per organization, across both view types.",
            409,
        )
    row = V(
        organization_id=access.organization_id,
        user_id=access.user_id,
        slot=slot,
        name=body.name,
        normalized_name=normalized_name(body.name),
        view_type=body.view_type,
        format_version=body.format_version,
        criteria=body.criteria.model_dump(mode="json", exclude_none=True),
        page_size=body.page_size,
        revision=1,
    )
    session.add(row)
    flush(session)
    return row


def change(session, access, view_id, body):
    lock_membership(session, access)
    current = detail(session, access, view_id)
    if body.expected_revision != current.revision or current.revision >= MAX_REVISION:
        fail(
            "SAVED_VIEW_CONFLICT",
            "This personal view changed. Re-read it before applying your draft.",
            409,
        )
    values = {"revision": V.revision + 1, "updated_at": func.now()}
    if body.name is not None:
        values.update(name=body.name, normalized_name=normalized_name(body.name))
    if body.definition is not None:
        if body.definition.view_type != current.view_type:
            fail("SAVED_VIEW_TYPE", "Save a separate view to change its type", 422)
        values.update(
            criteria=body.definition.criteria.model_dump(mode="json", exclude_none=True),
            format_version=body.definition.format_version,
            page_size=body.definition.page_size,
        )
    try:
        row = session.scalar(
            update(V)
            .where(*scope(access), V.id == view_id, V.revision == body.expected_revision)
            .values(**values)
            .returning(V)
            .execution_options(populate_existing=True)
        )
        flush(session)
    except IntegrityError:
        session.rollback()
        fail("SAVED_VIEW_DUPLICATE", "A personal view with this name already exists", 409)
    if row is None:
        fail(
            "SAVED_VIEW_CONFLICT",
            "This personal view changed. Re-read it before applying your draft.",
            409,
        )
    return row


def remove(session, access, view_id, body):
    lock_membership(session, access)
    detail(session, access, view_id)
    deleted = session.scalar(
        delete(V)
        .where(*scope(access), V.id == view_id, V.revision == body.expected_revision)
        .returning(V.id)
    )
    if deleted is None:
        fail("SAVED_VIEW_CONFLICT", "This personal view changed. Re-read it before deleting.", 409)
    return {"id": str(deleted), "deleted": True}
