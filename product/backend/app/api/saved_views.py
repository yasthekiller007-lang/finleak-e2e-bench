from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.auth.dependencies import AuthorizedOrganization, DatabaseSession
from app.financial.service import fail
from app.saved_views import service
from app.saved_views.schema import CreateView, DeleteView, UpdateView, clean_name

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/financial/saved-views",
    tags=["personal exception views"],
)


@router.get("")
def list_views(
    request: Request,
    access: AuthorizedOrganization,
    session: DatabaseSession,
    search: Annotated[str, Query(max_length=80)] = "",
    view_type: Literal["anomalies", "review"] | None = None,
    limit: Annotated[int, Query(ge=1, le=20)] = 10,
    after: UUID | None = None,
):
    pairs = list(request.query_params.multi_items())
    if any(k not in {"search", "view_type", "limit", "after"} for k, _ in pairs) or len(
        {k for k, _ in pairs}
    ) != len(pairs):
        fail("SAVED_VIEW_QUERY", "Unknown or repeated personal view query", 422)
    try:
        if search:
            clean_name(search)
    except ValueError:
        fail("SAVED_VIEW_SEARCH", "Invalid personal view search", 422)
    return service.listing(session, access, search, view_type, limit, after)


@router.post("", status_code=201)
def create_view(body: CreateView, access: AuthorizedOrganization, session: DatabaseSession):
    result = service.serialize(service.create(session, access, body))
    session.commit()
    return result


@router.get("/{view_id}")
def read_view(view_id: UUID, access: AuthorizedOrganization, session: DatabaseSession):
    return service.serialize(service.detail(session, access, view_id))


@router.patch("/{view_id}")
def update_view(
    view_id: UUID, body: UpdateView, access: AuthorizedOrganization, session: DatabaseSession
):
    result = service.serialize(service.change(session, access, view_id, body))
    session.commit()
    return result


@router.delete("/{view_id}")
def delete_view(
    view_id: UUID, body: DeleteView, access: AuthorizedOrganization, session: DatabaseSession
):
    result = service.remove(session, access, view_id, body)
    session.commit()
    return result
