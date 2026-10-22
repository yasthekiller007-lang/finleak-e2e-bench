from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import ValidationError
from sqlalchemy import func, select

from app.auth.dependencies import AuthorizedOrganization, DatabaseSession
from app.db.models import Organization
from app.financial import service
from app.financial.engine import COMPILER_VERSION, RULE_VERSION, compile_terms
from app.financial.exceptions_facets import FacetRequest, facet_page
from app.financial.exceptions_query import Filters, query_page
from app.financial.models import FinancialAudit, FinancialEvaluation, FinancialRevision
from app.financial.schema import (
    BillingScope,
    CreateSource,
    Evaluate,
    FindingDecision,
    Packet,
    Review,
    Term,
)

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/financial", tags=["financial review"]
)
PageLimit = Annotated[int, Query(ge=1, le=100)]
PageOffset = Annotated[int, Query(ge=0)]


def serialize_source(row):
    return {
        "id": str(row.id),
        "document_id": str(row.document_id),
        "kind": row.kind,
        "created_at": row.created_at.isoformat(),
    }


def serialize_revision(row):
    return service.inputs_snapshot([row])[0]


@router.post("/sources", status_code=201)
def create_source(body: CreateSource, access: AuthorizedOrganization, session: DatabaseSession):
    row = service.create_source(session, access, body)
    result = serialize_source(row)
    session.commit()
    return result


@router.get("/sources")
def list_sources(
    access: AuthorizedOrganization,
    session: DatabaseSession,
    limit: PageLimit = 20,
    offset: PageOffset = 0,
):
    query = service.sources_query(access)
    rows = session.scalars(
        query.order_by(query.selected_columns.created_at.desc(), query.selected_columns.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [serialize_source(r) for r in rows],
        "total": session.scalar(query.with_only_columns(func.count())),
        "limit": limit,
        "offset": offset,
    }


@router.get("/sources/{source_id}")
def source_detail(source_id: UUID, access: AuthorizedOrganization, session: DatabaseSession):
    row = service.source(session, access, source_id)
    heads = service.revisions(session, access, [source_id], authoritative=False)
    inputs = (
        service.pinned_inputs(session, access, row)
        if row.kind == "invoice"
        else (service.revisions(session, access, [source_id]))
    )
    return {
        **serialize_source(row),
        "reviews": [serialize_revision(r) for r in heads],
        "approved_inputs": [serialize_revision(r) for r in inputs],
        "revision_ids": [str(r.id) for r in inputs],
    }


@router.get("/sources/{source_id}/history")
def source_history(
    source_id: UUID,
    access: AuthorizedOrganization,
    session: DatabaseSession,
    limit: PageLimit = 20,
    offset: PageOffset = 0,
):
    service.source(session, access, source_id)
    query = select(FinancialRevision).where(
        FinancialRevision.organization_id == access.organization_id,
        FinancialRevision.source_id == source_id,
    )
    rows = session.scalars(
        query.order_by(FinancialRevision.created_at.desc(), FinancialRevision.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [serialize_revision(r) for r in rows],
        "total": session.scalar(query.with_only_columns(func.count())),
        "limit": limit,
        "offset": offset,
    }


@router.post("/sources/{source_id}/reviews", status_code=201)
def review_source(
    source_id: UUID,
    body: Review,
    access: AuthorizedOrganization,
    session: DatabaseSession,
    idempotency_key: Annotated[UUID, Header()],
):
    row = service.review(session, access, source_id, body, idempotency_key)
    result = serialize_revision(row)
    session.commit()
    return result


@router.get("/sources/{source_id}/compile")
def compile_source(
    source_id: UUID,
    invoice_source_id: UUID,
    scope_key: str,
    access: AuthorizedOrganization,
    session: DatabaseSession,
):
    contract = service.source(session, access, source_id)
    invoice = service.source(session, access, invoice_source_id)
    rows = service.pinned_inputs(session, access, invoice)
    packet = service.active_value([r for r in rows if r.source_id == contract.id], "packet")
    bill = service.active_value(rows, "billing_scope", scope_key)
    if packet is None or bill is None:
        return {"status": "BLOCKED", "reason_code": "UNAPPROVED_FACT", "terms": []}
    terms = tuple(
        Term.model_validate(r.payload["value"])
        for r in rows
        if r.kind == "term" and r.source_id == contract.id and r.state == "approved"
    )
    selected, error = compile_terms(
        terms,
        BillingScope.model_validate(bill.payload["value"]),
        Packet.model_validate(packet.payload["value"]),
    )
    return {
        "status": "BLOCKED" if error else "COMPILED",
        "reason_code": error.reason if error else None,
        "compiler_version": COMPILER_VERSION,
        "rule_version": RULE_VERSION,
        "terms": [t.model_dump(mode="json") for t in selected],
        "revision_ids": [str(r.id) for r in rows],
    }


@router.post("/sources/{source_id}/evaluate")
def evaluate_source(
    source_id: UUID, body: Evaluate, access: AuthorizedOrganization, session: DatabaseSession
):
    row = service.evaluate_scope(session, access, source_id, body)
    result = service.serialize_evaluation(session, access, row, detail=True)
    session.commit()
    return result


def exception_filters(request: Request):
    try:
        return Filters.model_validate(dict(request.query_params))
    except ValidationError:
        service.fail(
            "INVALID_EXCEPTION_FILTERS", "Invalid exception filters or creation period", 422
        )


@router.get(
    "/evaluations",
    openapi_extra={
        "parameters": [
            {"name": name, "in": "query", "required": False, "schema": schema}
            for name, schema in Filters.model_json_schema()["properties"].items()
        ]
    },
)
def list_evaluations(
    access: AuthorizedOrganization,
    session: DatabaseSession,
    filters: Annotated[Filters, Depends(exception_filters)],
    limit: PageLimit = 20,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
    pagination: Annotated[str, Query(pattern="^(offset|cursor)$")] = "offset",
    after: Annotated[str | None, Query(max_length=2048)] = None,
):
    return query_page(session, access, filters, limit, offset, pagination, after)


def facet_parameters(request: Request):
    allowed = set(Filters.model_fields) | set(FacetRequest.model_fields)
    pairs = list(request.query_params.multi_items())
    if any(name not in allowed for name, _ in pairs) or len({n for n, _ in pairs}) != len(pairs):
        service.fail("INVALID_FACET_PARAMETERS", "Unknown or repeated facet parameter", 422)
    try:
        return FacetRequest.model_validate(dict(pairs))
    except ValidationError:
        service.fail("INVALID_FACET_PARAMETERS", "Invalid facet type, search, limit or cursor", 422)


@router.get(
    "/exception-facets",
    openapi_extra={
        "parameters": [
            {"name": name, "in": "query", "required": name == "facet", "schema": schema}
            for name, schema in {
                **Filters.model_json_schema()["properties"],
                **FacetRequest.model_json_schema()["properties"],
            }.items()
        ]
    },
)
def exception_facets(
    access: AuthorizedOrganization,
    session: DatabaseSession,
    filters: Annotated[Filters, Depends(exception_filters)],
    parameters: Annotated[FacetRequest, Depends(facet_parameters)],
):
    return facet_page(session, access, filters, parameters)


@router.get("/evaluations/{evaluation_id}")
def evaluation_detail(
    evaluation_id: UUID, access: AuthorizedOrganization, session: DatabaseSession
):
    row = service.get_evaluation(session, access, evaluation_id)
    return service.serialize_evaluation(session, access, row, detail=True)


@router.post("/evaluations/{evaluation_id}/decision", status_code=201)
def finding_decision(
    evaluation_id: UUID,
    body: FindingDecision,
    access: AuthorizedOrganization,
    session: DatabaseSession,
):
    decision = service.decide(session, access, evaluation_id, body)
    result = {"id": str(decision.id), "status": decision.status, "reason": decision.reason}
    session.commit()
    return result


@router.get("/summary")
def summary(access: AuthorizedOrganization, session: DatabaseSession):
    # Coherent read view; immutable history remains unchanged.
    session.scalar(
        select(Organization)
        .where(Organization.id == access.organization_id)
        .with_for_update(read=True)
    )
    rows = session.scalars(
        service.evaluation_query(access).order_by(FinancialEvaluation.created_at.desc()).limit(1001)
    ).all()
    from decimal import Decimal

    totals = {}
    by_rule = {}
    counts = {"findings": 0, "blocked": 0, "assessed": 0, "stale": 0, "dismissed": 0}
    claimed = {}
    for row in rows[:1000]:
        item = service.serialize_evaluation(session, access, row)
        if item["stale"]:
            counts["stale"] += 1
            continue
        if row.potential is None:
            counts["blocked" if row.outcome == "NEEDS_REVIEW" else "assessed"] += 1
            continue
        if item["status"] == "false_positive":
            counts["dismissed"] += 1
            continue
        members = set((row.snapshot.get("billing_scope") or {}).get("members", []))
        invoice_claimed = claimed.setdefault(row.invoice_source_id, set())
        if members & invoice_claimed:
            counts["blocked"] += 1
            continue
        invoice_claimed.update(members)
        counts["findings"] += 1
        key = row.currency
        bundle = "+".join(sorted((row.snapshot.get("calculation") or {}).get("rules", [])))
        group = by_rule.setdefault(bundle, {})
        group[key] = group.get(key, Decimal("0")) + row.potential
        totals[key] = totals.get(key, Decimal("0")) + row.potential
    return {
        "potential_by_currency": {k: str(v) for k, v in totals.items()},
        "potential_by_rule": {
            rule: {k: str(v) for k, v in values.items()} for rule, values in by_rule.items()
        },
        "counts": counts,
        "limited": len(rows) > 1000,
        "coverage": "Current, undismissed, non-overlapping assessed scopes only. "
        "Blocked and unassessed amounts are unknown. Undercharges are not netted. "
        "Potential leakage is not recovered cash or guaranteed savings.",
    }


@router.get("/audit")
def list_audit(
    access: AuthorizedOrganization,
    session: DatabaseSession,
    limit: PageLimit = 20,
    offset: PageOffset = 0,
):
    query = select(FinancialAudit).where(FinancialAudit.organization_id == access.organization_id)
    rows = session.scalars(
        query.order_by(FinancialAudit.created_at.desc(), FinancialAudit.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [
            {
                "id": str(r.id),
                "actor_id": str(r.actor_id),
                "action": r.action,
                "target_id": str(r.target_id),
                "created_at": r.created_at.isoformat(),
                "detail": r.detail,
            }
            for r in rows
        ],
        "total": session.scalar(query.with_only_columns(func.count())),
        "limit": limit,
        "offset": offset,
    }
