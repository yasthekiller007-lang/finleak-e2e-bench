import asyncio
from datetime import datetime
from time import monotonic
from typing import Annotated
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.formparsers import MultiPartException

from app.auth.dependencies import AuthorizedOrganization, DatabaseSession, UploadOrganization
from app.db.models import Document
from app.domain.types import DocumentType, ProcessingStatus
from app.modules.protected_validation import validate_file_isolated
from app.modules.s3_storage import StorageFailure
from app.modules.source_preservation import lock_original
from app.modules.storage import ObjectStorage, document_storage_key
from app.modules.upload_validation import safe_filename

router = APIRouter(prefix="/api/v1/organizations/{organization_id}/documents", tags=["documents"])
BODY_LIMIT_MESSAGE = "Request body exceeds upload limit"
BODY_TIMEOUT_MESSAGE = "Upload receipt work budget exceeded"


class UploadBodyLimit:
    """Count actual received bytes; Content-Length is not a security boundary."""

    def __init__(self, app, max_bytes: int, receipt_seconds: float = 90):
        self.app = app
        self.max_bytes = max_bytes
        self.receipt_seconds = receipt_seconds

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return
        total = 0
        deadline = monotonic() + self.receipt_seconds
        multipart = (
            dict(scope.get("headers", []))
            .get(b"content-type", b"")
            .startswith(b"multipart/form-data")
        )

        async def limited_receive():
            nonlocal total
            if multipart:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise MultiPartException(BODY_TIMEOUT_MESSAGE)
                try:
                    message = await asyncio.wait_for(receive(), remaining)
                except TimeoutError:
                    raise MultiPartException(BODY_TIMEOUT_MESSAGE) from None
            else:
                message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > self.max_bytes:
                    # Starlette closes any partially parsed/spooled files for this exception.
                    raise MultiPartException(BODY_LIMIT_MESSAGE)
            return message

        await self.app(scope, limited_receive, send)


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    original_filename: str
    mime_type: str
    file_size: int
    sha256: str
    document_type: DocumentType
    processing_status: ProcessingStatus
    uploaded_by: UUID | None
    uploaded_at: datetime


class DocumentPage(BaseModel):
    items: list[DocumentResponse]
    total: int
    limit: int
    offset: int


def register_upload(
    session, storage: ObjectStorage, access, file, document_type, max_bytes, limits
):
    filename = safe_filename(file.filename)
    mime = validate_file_isolated(file.file, filename, file.content_type, max_bytes, limits)
    document_id = uuid4()
    key = document_storage_key(access.organization_id, document_id)
    from app.financial.service import lock_authority

    lock_authority(session, access)
    lock_original(session, key)
    stored = storage.put(key, file.file, max_bytes=max_bytes)
    try:
        document = Document(
            id=document_id,
            organization_id=access.organization_id,
            uploaded_by=access.user_id,
            original_filename=filename,
            mime_type=mime,
            file_size=stored.file_size,
            storage_key=stored.key,
            sha256=stored.sha256,
            document_type=document_type,
            processing_status=ProcessingStatus.PENDING,
        )
        session.add(document)
        session.flush()
        response = DocumentResponse.model_validate(document)
        session.commit()
        storage.registered(key)
        return response
    except IntegrityError as exc:
        compensate_upload(session, storage, key)
        duplicate = session.scalar(
            select(Document.id).where(
                Document.organization_id == access.organization_id, Document.sha256 == stored.sha256
            )
        )
        if duplicate is not None:
            raise HTTPException(
                409, "An identical document already exists in this organization"
            ) from exc
        raise
    except Exception:
        compensate_upload(session, storage, key)
        raise


def compensate_upload(session, storage, key):
    try:
        session.rollback()
    except Exception:
        raise StorageFailure("source_upload_commit_uncertain") from None
    storage.delete(key)


def upload_admission(request: Request, access: UploadOrganization, session: DatabaseSession):
    # Authentication's shared transaction lock must end before opening another connection:
    # an operator waiting for its exclusive lock must not deadlock this request.
    session.commit()
    with request.app.state.intake.reserve(
        access, "upload", request.app.state.settings.intake_limits
    ) as attempt:
        yield attempt


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=201,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["file", "document_type"],
                        "properties": {
                            "file": {"type": "string", "format": "binary"},
                            "document_type": {
                                "type": "string",
                                "enum": [item.value for item in DocumentType],
                            },
                        },
                    }
                }
            },
        }
    },
)
async def upload_document(
    request: Request,
    access: UploadOrganization,
    session: DatabaseSession,
    _admission: Annotated[UUID, Depends(upload_admission)],
):
    # Dependencies authenticate and authorize BEFORE invoking the multipart parser.
    if not request.headers.get("content-type", "").startswith("multipart/form-data"):
        raise HTTPException(415, "Use multipart/form-data")
    try:
        async with request.form(max_files=1, max_fields=1, max_part_size=1024) as form:
            file = form.get("file")
            if set(form) != {"file", "document_type"} or not isinstance(file, UploadFile):
                raise HTTPException(422, "Provide one file and a document_type")
            try:
                document_type = DocumentType(form.get("document_type"))
            except (ValueError, TypeError) as exc:
                raise HTTPException(422, "Invalid document type") from exc
            return await run_in_threadpool(
                register_upload,
                session,
                request.app.state.storage,
                access,
                file,
                document_type,
                request.app.state.settings.max_upload_bytes,
                request.app.state.settings.processing_limits,
            )
    except StarletteHTTPException as exc:
        if exc.detail == BODY_TIMEOUT_MESSAGE:
            raise HTTPException(408, "Upload receipt work budget exceeded; retry later") from exc
        if exc.detail == BODY_LIMIT_MESSAGE:
            raise HTTPException(413, "Request exceeds the maximum upload size") from exc
        raise


@router.get("", response_model=DocumentPage)
def list_documents(
    access: AuthorizedOrganization,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    scope = Document.organization_id == access.organization_id
    documents = session.scalars(
        select(Document)
        .where(scope)
        .order_by(Document.uploaded_at.desc(), Document.id)
        .offset(offset)
        .limit(limit)
    ).all()
    total = session.scalar(select(func.count()).select_from(Document).where(scope))
    return DocumentPage(
        items=[DocumentResponse.model_validate(doc) for doc in documents],
        total=total,
        limit=limit,
        offset=offset,
    )


def authorized_document(session, access, document_id):
    document = session.scalar(
        select(Document).where(
            Document.id == document_id, Document.organization_id == access.organization_id
        )
    )
    if document is None:
        raise HTTPException(404, "Document not found")
    return document


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: UUID, access: AuthorizedOrganization, session: DatabaseSession):
    return authorized_document(session, access, document_id)


@router.get("/{document_id}/content")
def download_document(
    document_id: UUID, access: AuthorizedOrganization, session: DatabaseSession, request: Request
):
    document = authorized_document(session, access, document_id)
    from app.operations.source_gate import require_released

    require_released(session, document)
    from app.proof.budget import Budget, verify_source

    status, content = verify_source(
        request.app.state.storage,
        document,
        Budget(request.app.state.settings.proof_limits),
        capture=True,
    )
    if status == "UNAVAILABLE":
        raise HTTPException(404, "Document content is unavailable")
    if status != "AVAILABLE_VERIFIED":
        raise HTTPException(409, "Document integrity mismatch; content is quarantined")
    return Response(
        content,
        media_type=document.mime_type,
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''"
            + quote(document.original_filename, safe=""),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
            "Content-Length": str(document.file_size),
            "Content-Security-Policy": "sandbox",
            "X-Source-SHA256": document.sha256,
        },
    )
