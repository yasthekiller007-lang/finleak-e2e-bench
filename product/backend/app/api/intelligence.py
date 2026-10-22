from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request
from sqlalchemy import func

from app.api.documents import authorized_document
from app.auth.dependencies import AuthorizedOrganization, DatabaseSession
from app.db.models import ExtractionRun
from app.domain.types import MembershipRole
from app.intelligence.service import process, scoped_runs, serialize_run
from app.operations.source_gate import require_released

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/documents", tags=["document intelligence"]
)


def start(request, document_id, access, session, key, reprocess=False):
    if access.role == MembershipRole.VIEWER:
        raise HTTPException(403, "Your role cannot process documents")
    session.commit()
    with request.app.state.intake.reserve(
        access, "process", request.app.state.settings.intake_limits
    ):
        require_released(session, authorized_document(session, access, document_id))
        run = process(
            session,
            request.app.state.storage,
            access,
            document_id,
            key,
            request.app.state.settings,
            reprocess,
        )
    return {"run": serialize_run(session, run)}


@router.post("/{document_id}/process")
def process_document(
    request: Request,
    document_id: UUID,
    access: AuthorizedOrganization,
    session: DatabaseSession,
    idempotency_key: Annotated[UUID, Header()],
):
    return start(request, document_id, access, session, idempotency_key)


@router.post("/{document_id}/reprocess")
def reprocess_document(
    request: Request,
    document_id: UUID,
    access: AuthorizedOrganization,
    session: DatabaseSession,
    idempotency_key: Annotated[UUID, Header()],
):
    return start(request, document_id, access, session, idempotency_key, True)


@router.get("/{document_id}/extraction")
def get_extraction(document_id: UUID, access: AuthorizedOrganization, session: DatabaseSession):
    authorized_document(session, access, document_id)
    # Explicit descending order gives the latest audited attempt, including failures.
    run = session.scalar(
        scoped_runs(access, document_id).order_by(ExtractionRun.version_number.desc()).limit(1)
    )
    return {"run": serialize_run(session, run) if run else None}


@router.get("/{document_id}/extraction-runs")
def list_runs(
    document_id: UUID,
    access: AuthorizedOrganization,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    authorized_document(session, access, document_id)
    query = scoped_runs(access, document_id)
    runs = session.scalars(
        query.order_by(ExtractionRun.version_number.desc()).offset(offset).limit(limit)
    ).all()
    total = session.scalar(query.with_only_columns(func.count()).order_by(None))
    return {
        "items": [serialize_run(session, run, include_fields=False) for run in runs],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{document_id}/extraction-runs/{run_id}")
def get_run(
    document_id: UUID, run_id: UUID, access: AuthorizedOrganization, session: DatabaseSession
):
    authorized_document(session, access, document_id)
    run = session.scalar(scoped_runs(access, document_id).where(ExtractionRun.id == run_id))
    if run is None:
        raise HTTPException(404, "Extraction not found")
    return {"run": serialize_run(session, run)}
