from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func
from sqlalchemy.exc import DBAPIError

from app.auth.dependencies import AuthorizedOrganization, DatabaseSession
from app.core.errors import error_response
from app.db.models import Document
from app.financial.service import get_evaluation, lock_authority
from app.proof import service
from app.proof.budget import Budget, ProofError, verify_source
from app.proof.canonical import CanonicalError, strict_loads
from app.proof.models import ProofArtifact, ProofEvent, ProofFamily, ProofPackage
from app.proof.schema import Event, Export, Generate, Successor

router = APIRouter(prefix="/api/v1/organizations/{organization_id}/proof", tags=["proof"])
Key = Annotated[UUID, Header(alias="Idempotency-Key")]


class ProofBodyGuard:
    """Bounds actual JSON bytes before parsing, including chunked/lying-length requests."""

    def __init__(self, app, max_bytes):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or "/proof/" not in scope.get("path", "")
        ):
            return await self.app(scope, receive, send)
        chunks, total = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            total += len(chunk)
            if total > self.max_bytes:
                request = Request(scope)
                return await error_response(
                    request, 413, "proof_request_limit", "Proof request is too large"
                )(scope, receive, send)
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        raw = b"".join(chunks)
        try:
            strict_loads(raw)
        except (CanonicalError, RecursionError):
            return await error_response(
                Request(scope), 422, "proof_invalid_json", "Proof request JSON is invalid"
            )(scope, receive, send)
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": raw, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


def operation(request, session, access, command, target, body, key):
    try:
        result = service.execute(
            session,
            access,
            command,
            target,
            body,
            key,
            request.app.state.storage,
            request.app.state.settings.proof_limits,
        )
        session.commit()
    except ProofError as exc:
        # Admission failure happens before issuance; no financial artifact is committed.
        session.rollback()
        return error_response(request, exc.status, exc.code, exc.message)
    except DBAPIError:
        session.rollback()
        return error_response(
            request,
            503,
            "proof_transaction_retry",
            "Proof transaction could not complete safely; retry later",
        )
    if "error" in result:
        error = result["error"]
        response = error_response(request, error["status"], error["code"], error["message"])
        if error["status"] == 429:
            response.headers["Retry-After"] = "60"
        return response
    return JSONResponse(result, headers={"Idempotency-Key": str(key), "Cache-Control": "no-store"})


@router.get("/evaluations/{evaluation_id}/packages")
def list_packages(
    evaluation_id: UUID,
    access: AuthorizedOrganization,
    session: DatabaseSession,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    budget = Budget(request.app.state.settings.proof_limits)
    service.admit(session, access, budget)
    service.read_authority(session, access)
    get_evaluation(session, access, evaluation_id)
    budget.bound(limit, "history_page")
    rows = session.scalars(
        service.query(ProofPackage, access)
        .join(ProofFamily, ProofFamily.id == ProofPackage.family_id)
        .where(ProofFamily.evaluation_id == evaluation_id)
        .order_by(ProofPackage.number.desc())
        .offset(offset)
        .limit(limit + 1)
    ).all()
    return {
        "items": [service.summary(session, access, row, budget) for row in rows[:limit]],
        "has_more": len(rows) > limit,
        "offset": offset,
        "limit": limit,
    }


@router.post("/evaluations/{evaluation_id}/generate")
def generate(
    evaluation_id: UUID,
    body: Generate,
    key: Key,
    request: Request,
    access: AuthorizedOrganization,
    session: DatabaseSession,
):
    return operation(request, session, access, "generate", evaluation_id, body, key)


@router.get("/packages/{package_id}")
def get_package(
    package_id: UUID, request: Request, access: AuthorizedOrganization, session: DatabaseSession
):
    budget = Budget(request.app.state.settings.proof_limits)
    service.admit(session, access, budget)
    service.read_authority(session, access, exclusive=True)
    package = service.get(session, access, ProofPackage, package_id)
    result = service.detail(session, access, package, request.app.state.storage, budget)
    session.commit()
    return result


@router.get("/packages/{package_id}/history")
def history(
    package_id: UUID,
    access: AuthorizedOrganization,
    session: DatabaseSession,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    budget = Budget(request.app.state.settings.proof_limits)
    service.admit(session, access, budget)
    service.read_authority(session, access)
    service.get(session, access, ProofPackage, package_id)
    budget.bound(limit, "history_page")
    rows = session.scalars(
        service.query(ProofEvent, access)
        .where(ProofEvent.package_id == package_id)
        .order_by(ProofEvent.number.desc())
        .offset(offset)
        .limit(limit + 1)
    ).all()
    budget.check()
    return {
        "items": [
            {
                "id": str(row.id),
                "number": row.number,
                "kind": row.kind,
                "actor_id": str(row.actor_id),
                "created_at": row.created_at.isoformat(),
                "previous_id": str(row.previous_id) if row.previous_id else None,
                "audit_id": str(row.audit_id),
                "detail": row.detail,
            }
            for row in rows[:limit]
        ],
        "has_more": len(rows) > limit,
        "offset": offset,
        "limit": limit,
    }


@router.post("/packages/{package_id}/events")
def add_event(
    package_id: UUID,
    body: Event,
    key: Key,
    request: Request,
    access: AuthorizedOrganization,
    session: DatabaseSession,
):
    return operation(request, session, access, body.kind, package_id, body, key)


@router.post("/packages/{package_id}/export")
def export(
    package_id: UUID,
    body: Export,
    key: Key,
    request: Request,
    access: AuthorizedOrganization,
    session: DatabaseSession,
):
    return operation(request, session, access, "export", package_id, body, key)


@router.get("/packages/{package_id}/artifacts")
def artifacts(
    package_id: UUID,
    access: AuthorizedOrganization,
    session: DatabaseSession,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    budget = Budget(request.app.state.settings.proof_limits)
    service.admit(session, access, budget)
    lock_authority(session, access, final=True)
    service.get(session, access, ProofPackage, package_id)
    budget.bound(limit, "history_page")
    rows = session.execute(
        service.query(ProofArtifact, access)
        .with_only_columns(
            ProofArtifact.id,
            ProofArtifact.package_id,
            ProofArtifact.disclosure_id,
            ProofArtifact.actor_id,
            ProofArtifact.created_at,
            ProofArtifact.content_hash,
            func.octet_length(ProofArtifact.content).label("size_bytes"),
        )
        .where(ProofArtifact.package_id == package_id)
        .order_by(ProofArtifact.created_at.desc(), ProofArtifact.id)
        .offset(offset)
        .limit(limit + 1)
    ).all()
    budget.check()
    return {
        "items": [
            {
                "id": str(row.id),
                "package_id": str(row.package_id),
                "disclosure_id": str(row.disclosure_id) if row.disclosure_id else None,
                "actor_id": str(row.actor_id),
                "created_at": row.created_at.isoformat(),
                "content_hash": row.content_hash,
                "size_bytes": row.size_bytes,
                "format_version": "proof-json/1",
            }
            for row in rows[:limit]
        ],
        "has_more": len(rows) > limit,
        "limit": limit,
        "offset": offset,
    }


@router.post("/packages/{package_id}/successor")
def successor(
    package_id: UUID,
    body: Successor,
    key: Key,
    request: Request,
    access: AuthorizedOrganization,
    session: DatabaseSession,
):
    return operation(request, session, access, "successor", package_id, body, key)


@router.get("/artifacts/{artifact_id}/download")
def download_artifact(
    artifact_id: UUID, access: AuthorizedOrganization, session: DatabaseSession, request: Request
):
    import hashlib

    budget = Budget(request.app.state.settings.proof_limits)
    service.admit(session, access, budget)
    lock_authority(session, access, final=True)
    artifact = service.get(session, access, ProofArtifact, artifact_id)
    package = service.get(session, access, ProofPackage, artifact.package_id)
    service.assert_package(session, access, package)
    budget.bound(len(artifact.content), "canonical_bytes")
    valid = hashlib.sha256(artifact.content).hexdigest() == artifact.content_hash
    service.event_record(
        session,
        access,
        package,
        "artifact.downloaded",
        {
            "artifact_id": str(artifact.id),
            "content_hash": artifact.content_hash,
            "integrity": "VERIFIED" if valid else "MISMATCH",
        },
    )
    # Authorization is held through byte capture and audit commit immediately before response.
    session.commit()
    if not valid:
        return error_response(
            request, 409, "proof_integrity_failure", "Artifact checksum disagrees"
        )
    return Response(
        bytes(artifact.content),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="proof-{artifact.id}.json"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
            "X-Artifact-SHA256": artifact.content_hash,
        },
    )


@router.get("/packages/{package_id}/sources/{document_id}/download")
def download_source(
    package_id: UUID,
    document_id: UUID,
    access: AuthorizedOrganization,
    session: DatabaseSession,
    request: Request,
):
    budget = Budget(request.app.state.settings.proof_limits)
    service.admit(session, access, budget)
    service.read_authority(session, access, exclusive=True)
    package = service.get(session, access, ProofPackage, package_id)
    service.assert_package(session, access, package)
    pinned = next(
        (s for s in package.core["sources"] if s["document_id"] == str(document_id)), None
    )
    if pinned is None:
        from fastapi import HTTPException

        raise HTTPException(404, "Proof source not found")
    document = session.scalar(
        service.query(Document, access).where(Document.id == document_id).with_for_update(read=True)
    )
    if document is None:
        status, content = "UNAVAILABLE", None
    elif document.sha256 != pinned["sha256"]:
        status, content = "MISMATCH", None
    else:
        status, content = verify_source(request.app.state.storage, document, budget, capture=True)
    service.event_record(
        session,
        access,
        package,
        "source.downloaded",
        {"document_id": str(document_id), "sha256": pinned["sha256"], "integrity": status},
    )
    session.commit()
    if status != "AVAILABLE_VERIFIED":
        return error_response(
            request,
            409,
            "proof_source_unavailable",
            "Pinned source is unavailable or its integrity disagrees",
        )
    return Response(
        content,
        media_type=document.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="source-{document_id}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
            "X-Source-SHA256": pinned["sha256"],
        },
    )
