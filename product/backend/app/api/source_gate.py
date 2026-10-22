"""Explicit operational scan/release routes; no financial, proof or extraction action."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.documents import authorized_document
from app.auth.dependencies import AuthorizedOrganization, DatabaseSession
from app.domain.types import MembershipRole
from app.operations import source_service
from app.operations.source_gate import SourceGateError, gate

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/documents", tags=["source availability"]
)


class SourceAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=4000)


class SourceReleaseAction(SourceAction):
    scan_id: UUID


@router.get("/{document_id}/source-status")
def source_status(document_id: UUID, access: AuthorizedOrganization, session: DatabaseSession):
    document = authorized_document(session, access, document_id)
    return gate(session, document)


@router.post("/{document_id}/scan")
def scan_source(
    request: Request,
    document_id: UUID,
    body: SourceAction,
    access: AuthorizedOrganization,
    session: DatabaseSession,
    idempotency_key: Annotated[UUID, Header()],
):
    if access.role == MembershipRole.VIEWER:
        raise HTTPException(403, "Your role cannot scan sources")
    authorized_document(session, access, document_id)
    session.commit()
    engine = request.app.state.scanner_engine
    if engine is None:
        raise SourceGateError("source_scanner_database_unavailable", 503)
    with request.app.state.intake.reserve(
        access, "process", request.app.state.settings.intake_limits
    ):
        with Session(engine, join_transaction_mode="create_savepoint") as scan_session:
            result = source_service.scan(
                scan_session,
                request.app.state.raw_storage,
                request.app.state.scanner,
                access,
                document_id,
                idempotency_key,
                body.reason,
                request.app.state.settings.proof_limits,
            )
            response = {"scan_id": str(result.id), "verdict": result.verdict}
            scan_session.commit()
    document = authorized_document(session, access, document_id)
    return response | {"source": gate(session, document)}


@router.post("/{document_id}/release")
def release_source(
    request: Request,
    document_id: UUID,
    body: SourceReleaseAction,
    access: AuthorizedOrganization,
    session: DatabaseSession,
    idempotency_key: Annotated[UUID, Header()],
):
    if access.role not in {MembershipRole.OWNER, MembershipRole.ADMIN}:
        raise HTTPException(403, "Owner/admin controls clean-source release")
    authorized_document(session, access, document_id)
    session.commit()
    with request.app.state.intake.reserve(
        access, "process", request.app.state.settings.intake_limits
    ):
        result = source_service.release(
            session,
            request.app.state.raw_storage,
            access,
            document_id,
            body.scan_id,
            idempotency_key,
            body.reason,
            request.app.state.settings.proof_limits,
        )
        response = {"release_id": str(result.id), "scan_id": str(result.scan_id)}
        session.commit()
    document = authorized_document(session, access, document_id)
    return response | {"source": gate(session, document)}
