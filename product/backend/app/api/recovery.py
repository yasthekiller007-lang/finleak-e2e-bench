"""Internal explicit commands only; no Recovery Ledger export route."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError

from app.auth.dependencies import AuthorizedOrganization, DatabaseSession
from app.core.errors import error_response
from app.proof.budget import ProofError
from app.proof.service import read_authority
from app.recovery import publication, reporting, service
from app.recovery.budget import Budget, admit
from app.recovery.models import (
    RecoveryCase,
    RecoveryInstrument,
    RecoveryProposal,
    RecoveryRecord,
)
from app.recovery.schema import (
    Approve,
    CreateCase,
    Instrument,
    Lifecycle,
    Note,
    Proposal,
    Report,
    Strict,
    Text,
    Workflow,
)

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/recovery", tags=["recovery ledger"]
)
Key = Annotated[UUID, Header(alias="Idempotency-Key")]


class Inspect(Strict):
    expected_head: UUID | None
    reason: Text


def operation(request, session, access, command, target, body, key):
    budget = Budget(request.app.state.settings.recovery_limits)
    request.state.recovery_session = session
    try:
        result = service.execute(
            session,
            access,
            command,
            target,
            body,
            key,
            request.app.state.storage,
            request.app.state.settings.recovery_limits,
            budget,
        )
        session.commit()
    except ProofError as exc:
        session.rollback()
        return error_response(request, exc.status, exc.code, exc.message)
    except DBAPIError:
        session.rollback()
        return error_response(
            request,
            503,
            "recovery_transaction_retry",
            "Recovery transaction could not safely complete; reload and retry",
        )
    if "error" not in result:
        # Financial history is already committed. Publication is independently
        # retryable metadata: never roll back or mislabel the original success.
        try:
            admit(session, access, budget)
            publication.capture(session, access, budget)
            session.commit()
            if "recorded_at" in result:
                stamp = publication.committed(session, access, UUID(result["id"]))
                result = dict(result, known_at=stamp.isoformat() if stamp else None)
            result = dict(result, known_at_status="VERIFIED_COMMIT")
        except (ProofError, DBAPIError):
            session.rollback()
            logging.getLogger("financial_leakage").error(
                "recovery_provenance_unresolved",
                extra={
                    "component": "recovery",
                    "reason_code": "recovery_known_at_unavailable",
                },
            )
            result = dict(result, known_at_status="UNRESOLVED_COMMIT_PROVENANCE")
    if "error" in result:
        error = result["error"]
        response = error_response(request, error["status"], error["code"], error["message"])
        if error["status"] == 429:
            response.headers["Retry-After"] = "60"
        return response
    return JSONResponse(result, headers={"Cache-Control": "no-store", "Idempotency-Key": str(key)})


def reading(request, session, access):
    budget = Budget(request.app.state.settings.recovery_limits)
    request.state.recovery_session = session
    admit(session, access, budget)
    service.require_guards(session)
    publication.capture(session, access, budget)
    session.commit()
    admit(session, access, budget)
    read_authority(session, access)
    return budget


@router.post("/cases")
def create_case(
    body: CreateCase,
    key: Key,
    request: Request,
    access: AuthorizedOrganization,
    session: DatabaseSession,
):
    return operation(request, session, access, "create_case", None, body, key)


@router.post("/instruments")
def instrument(
    body: Instrument,
    key: Key,
    request: Request,
    access: AuthorizedOrganization,
    session: DatabaseSession,
):
    return operation(request, session, access, "create_instrument", None, body, key)


@router.get("/cases")
def cases(
    request: Request,
    access: AuthorizedOrganization,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    budget = reading(request, session, access)
    budget.bound(limit, "history_page")
    rows = session.scalars(
        service.query(RecoveryCase, access)
        .order_by(RecoveryCase.created_at.desc(), RecoveryCase.id)
        .offset(offset)
        .limit(limit + 1)
    ).all()
    for row in rows[:limit]:
        service.assert_origin(session, access, row)
    return {
        "items": [
            reporting.detail(session, access, row, request.app.state.storage, budget)
            for row in rows[:limit]
        ],
        "has_more": len(rows) > limit,
        "offset": offset,
        "limit": limit,
        "coverage": "Case page; financial totals require a complete bounded report",
    }


@router.get("/cases/{case_id}")
def case_detail(
    case_id: UUID, request: Request, access: AuthorizedOrganization, session: DatabaseSession
):
    budget = reading(request, session, access)
    return reporting.detail(
        session,
        access,
        service.get(session, access, RecoveryCase, case_id),
        request.app.state.storage,
        budget,
    )


@router.get("/instruments")
def instruments(
    request: Request,
    access: AuthorizedOrganization,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    budget = reading(request, session, access)
    budget.bound(limit, "history_page")
    rows = session.scalars(
        service.query(RecoveryInstrument, access)
        .order_by(RecoveryInstrument.created_at.desc(), RecoveryInstrument.id)
        .offset(offset)
        .limit(limit + 1)
    ).all()
    for row in rows[:limit]:
        service.assert_origin(session, access, row)
    return {
        "items": [service.serialize(row) for row in rows[:limit]],
        "has_more": len(rows) > limit,
        "offset": offset,
        "limit": limit,
    }


@router.post("/cases/{case_id}/proposals")
def proposal(
    case_id: UUID,
    body: Proposal,
    key: Key,
    request: Request,
    access: AuthorizedOrganization,
    session: DatabaseSession,
):
    return operation(request, session, access, "prepare", case_id, body, key)


@router.post("/proposals/{proposal_id}/decision")
def decision(
    proposal_id: UUID,
    body: Approve,
    key: Key,
    request: Request,
    access: AuthorizedOrganization,
    session: DatabaseSession,
):
    return operation(request, session, access, "approve", proposal_id, body, key)


@router.post("/cases/{case_id}/lifecycle")
def lifecycle(
    case_id: UUID,
    body: Lifecycle,
    key: Key,
    request: Request,
    access: AuthorizedOrganization,
    session: DatabaseSession,
):
    return operation(request, session, access, "lifecycle", case_id, body, key)


@router.post("/cases/{case_id}/workflow")
def workflow(
    case_id: UUID,
    body: Workflow,
    key: Key,
    request: Request,
    access: AuthorizedOrganization,
    session: DatabaseSession,
):
    return operation(request, session, access, "workflow", case_id, body, key)


@router.post("/cases/{case_id}/notes")
def note(
    case_id: UUID,
    body: Note,
    key: Key,
    request: Request,
    access: AuthorizedOrganization,
    session: DatabaseSession,
):
    return operation(request, session, access, "note", case_id, body, key)


@router.post("/cases/{case_id}/inspect")
def inspect(
    case_id: UUID,
    body: Inspect,
    key: Key,
    request: Request,
    access: AuthorizedOrganization,
    session: DatabaseSession,
):
    return operation(request, session, access, "inspect", case_id, body, key)


@router.get("/cases/{case_id}/history")
def history(
    case_id: UUID,
    request: Request,
    access: AuthorizedOrganization,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    proposals: bool = False,
):
    budget = reading(request, session, access)
    service.get(session, access, RecoveryCase, case_id)
    budget.bound(limit, "history_page")
    model = RecoveryProposal if proposals else RecoveryRecord
    rows = session.scalars(
        service.query(model, access)
        .where(model.case_id == case_id)
        .order_by(model.created_at.desc(), model.id)
        .offset(offset)
        .limit(limit + 1)
    ).all()
    for row in rows[:limit]:
        service.assert_origin(session, access, row)
    items = [service.serialize(row) for row in rows[:limit]]
    if not proposals:
        for item in items:
            stamp = publication.committed(session, access, UUID(item["id"]))
            item["known_at"] = stamp.isoformat() if stamp else None
    result = {"items": items, "has_more": len(rows) > limit, "offset": offset, "limit": limit}
    budget.bound(len(service.canonical(result)), "response_bytes")
    return result


@router.get("/proposals/{proposal_id}/evidence")
def evidence(
    proposal_id: UUID, request: Request, access: AuthorizedOrganization, session: DatabaseSession
):
    budget = reading(request, session, access)
    service.get(session, access, RecoveryProposal, proposal_id)
    rows = service.bindings(session, access, proposal_id)
    budget.bound(len(rows), "bindings")
    # Routine views exclude private raw bank fields; originals retain protected access.
    return {
        "items": [
            {
                "document_id": str(r.document_id),
                "sha256": r.sha256,
                "file_size": r.file_size,
                "media_type": r.media_type,
                "locator": r.detail["locator"],
                "supports": r.detail["supports"],
            }
            for r in rows
        ]
    }


@router.post("/report")
def report(
    body: Report, request: Request, access: AuthorizedOrganization, session: DatabaseSession
):
    budget = reading(request, session, access)
    return reporting.report(session, access, body, budget)


class RecoveryBodyGuard:
    def __init__(self, app, max_bytes):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or "/recovery/" not in scope.get("path", ""):
            return await self.app(scope, receive, send)
        messages, size = [], 0
        settings = scope["app"].state.settings.recovery_limits

        async def bounded_send(message):
            nonlocal size
            if message["type"] == "http.response.body":
                size += len(message.get("body", b""))
            if size <= settings.response_bytes:
                messages.append(message)

        try:
            await self.body(scope, receive, bounded_send)
            if size > settings.response_bytes:
                return await error_response(
                    Request(scope),
                    413,
                    "recovery_resource_limit",
                    "Recovery response exceeds its bounded profile",
                )(scope, receive, send)
            for message in messages:
                await send(message)
        finally:
            session = scope.get("state", {}).get("recovery_session")
            if session is not None:
                session.info.pop("recovery_budget", None)
                if session.in_transaction():
                    session.connection().info.pop("recovery_budget", None)

    async def body(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or "/recovery/" not in scope.get("path", "")
        ):
            return await self.app(scope, receive, send)
        from app.proof.canonical import CanonicalError, strict_loads

        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            data = message.get("body", b"")
            size += len(data)
            if size > self.max_bytes:
                return await error_response(
                    Request(scope),
                    413,
                    "recovery_request_limit",
                    "Recovery request exceeds its bounded profile",
                )(scope, receive, send)
            chunks.append(data)
            if not message.get("more_body", False):
                break
        raw = b"".join(chunks)
        try:
            strict_loads(raw)
        except (CanonicalError, RecursionError):
            return await error_response(
                Request(scope), 422, "recovery_invalid_json", "Recovery request JSON is invalid"
            )(scope, receive, send)
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": raw, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
