"""Read-only business facets over recorded evaluations, never a party master or policy engine."""

import hashlib
import json
import time
from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import ARRAY, Text, and_, case, cast, distinct, func, literal, or_, select
from sqlalchemy.dialects.postgresql import JSONB

from app.db.models import Document, Organization
from app.financial import exceptions_query as q
from app.financial import service
from app.financial.models import FinancialEvaluation as E
from app.financial.models import ReviewedFinancialSource as S

Facet = Literal["supplier", "contract", "invoice"]
OWN_FILTER = {
    "supplier": "supplier",
    "contract": "contract_source_id",
    "invoice": "invoice_source_id",
}


class FacetRequest(BaseModel):
    facet: Facet
    search: str = Field(default="", max_length=120)
    limit: int = Field(default=20, ge=1, le=50)
    after: str | None = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def bounded_search(self):
        self.search = self.search.strip()
        if any(ord(c) < 32 for c in self.search):
            raise ValueError("Control characters are not supported")
        return self


def effective_filters(filters, facet):
    # Disjunctive facet: remove ONLY the facet's own criterion; missing_contract remains active.
    return filters.model_copy(update={OWN_FILTER[facet]: None, "sort": "newest"})


def search_pattern(value):
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def frozen_value(snapshot, source_id, kind):
    """Return a single distinct approved value on this exact contract, or NULL on ambiguity."""
    inputs = snapshot["inputs"]
    array = case((func.jsonb_typeof(inputs) == "array", inputs), else_=cast(literal("[]"), JSONB))
    entry = func.jsonb_array_elements(array).table_valued("value").alias(f"facet_{kind}")
    value = entry.c.value
    payload = value.op("#>")(cast(literal("{payload,value}"), ARRAY(Text)))
    text = cast(payload, Text)
    return cast(
        select(func.min(text))
        .select_from(entry)
        .where(
            value.op("->>")("kind") == kind,
            value.op("->>")("state") == "approved",
            value.op("->>")("source_id") == cast(source_id, Text),
            func.jsonb_typeof(payload) == "object",
        )
        .having(func.count(distinct(text)) == 1)
        .correlate_except(entry)
        .scalar_subquery(),
        JSONB,
    )


def facet_statement(org, filters, request, last=None, candidate_ids=None):
    """One parameterized SELECT, <=51 rows returned. SQL scan/sort cost is not row-bounded."""
    base = q.filtered_query(org, filters)
    if candidate_ids is not None:
        base = base.where(E.id.in_(candidate_ids))
    if request.facet == "supplier":
        party = q.supplier_expression().collate("C")
        values = base.with_only_columns(party.label("value")).where(party.is_not(None)).distinct()
        values = values.subquery("supplier_values")
        key = values.c.value.collate("C")
        statement = select(values.c.value)
        if request.search:
            statement = statement.where(key.ilike(search_pattern(request.search), escape="\\"))
        if last is not None:
            statement = statement.where(key > last)
        return statement.order_by(key).limit(request.limit + 1)

    if request.facet == "invoice":
        # One row per source, not per evaluation or filename. No link to the legacy Invoice model.
        recent = (
            base.with_only_columns(
                E.invoice_source_id.label("invoice_key"),
                E.snapshot,
                E.id.label("context_evaluation_id"),
                q.supplier_expression().label("supplier_party"),
            )
            .distinct(E.invoice_source_id)
            .order_by(E.invoice_source_id, E.created_at.desc(), E.id)
            .subquery("latest_invoice_context")
        )
        metadata = (
            select(
                func.replace(cast(recent.c.invoice_key, Text), "-", "").label("value"),
                func.row_number().over(order_by=recent.c.invoice_key).label("choice_number"),
                S.document_id,
                S.created_at.label("source_created_at"),
                Document.original_filename.label("filename"),
                recent.c.supplier_party,
                recent.c.context_evaluation_id,
                recent.c.snapshot["billing_scope"]["invoice_date"].astext.label("invoice_date"),
            )
            .select_from(recent)
            .join(
                S, and_(S.organization_id == org, S.kind == "invoice", S.id == recent.c.invoice_key)
            )
            .join(Document, and_(Document.organization_id == org, Document.id == S.document_id))
            .subquery("invoice_labels")
        )
        statement = select(metadata)
        if request.search:
            statement = statement.where(
                metadata.c.filename.ilike(search_pattern(request.search), escape="\\")
            )
        if last is not None:
            statement = statement.where(metadata.c.value.collate("C") > last)
        return statement.order_by(metadata.c.value.collate("C")).limit(request.limit + 1)

    contract = q.approved_contract_expression()
    # The most recent matching evaluation supplies frozen display context, never current revisions.
    recent = (
        base.with_only_columns(
            contract.label("contract_key"), E.snapshot, E.created_at, E.id.label("evaluation_id")
        )
        .where(contract.is_not(None))
        .distinct(contract)
        .order_by(contract, E.created_at.desc(), E.id)
        .subquery("latest_contract_context")
    )
    ref = frozen_value(recent.c.snapshot, S.id, "reference")["contract_reference"]
    reference = case(
        (and_(func.jsonb_typeof(ref) == "string", ref.astext != ""), ref.astext), else_=None
    )
    packet = frozen_value(recent.c.snapshot, S.id, "packet")
    metadata = (
        select(
            recent.c.contract_key.label("value"),
            func.row_number()
            .over(order_by=recent.c.contract_key.collate("C"))
            .label("choice_number"),
            reference.label("reference"),
            S.document_id,
            S.created_at.label("source_created_at"),
            Document.original_filename.label("filename"),
            packet["effective_from"].astext.label("effective_from"),
            packet["effective_to"].astext.label("effective_to"),
        )
        .select_from(recent)
        .join(
            S,
            and_(
                S.organization_id == org,
                S.kind == "contract",
                func.replace(cast(S.id, Text), "-", "") == recent.c.contract_key,
            ),
        )
        .join(Document, and_(Document.organization_id == org, Document.id == S.document_id))
        .subquery("contract_labels")
    )
    statement = select(metadata)
    if request.search:
        pattern = search_pattern(request.search)
        statement = statement.where(
            or_(
                metadata.c.reference.ilike(pattern, escape="\\"),
                metadata.c.filename.ilike(pattern, escape="\\"),
            )
        )
    if last is not None:
        statement = statement.where(metadata.c.value.collate("C") > last)
    # Stable source identity order avoids filenames or repeated references moving page boundaries.
    return statement.order_by(metadata.c.value.collate("C")).limit(request.limit + 1)


def contract_item(row):
    reference, filename = row["reference"], row["filename"]
    created = row["source_created_at"].isoformat()
    return {
        "value": str(UUID(row["value"])),
        "label": reference or filename,
        "reference": reference,
        "filename": filename,
        "document_id": str(row["document_id"]),
        "source_created_at": created,
        "effective_from": row["effective_from"],
        "effective_to": row["effective_to"],
        "description": (
            f"{filename} · reviewed source created {created} · choice {row['choice_number']}"
        ),
        # No legal supplier identity inferred from a billing scope or a filename.
    }


def invoice_item(row):
    # Reviewed Reference has only contract_reference / po_reference. Never relabel either.
    reviewed_date = row["invoice_date"]
    try:
        if not isinstance(reviewed_date, str) or len(reviewed_date) != 10:
            raise ValueError()
        if date.fromisoformat(reviewed_date).isoformat() != reviewed_date:
            raise ValueError()
    except ValueError:
        reviewed_date = None
    created = row["source_created_at"].isoformat()
    supplier = row["supplier_party"]
    return {
        "value": str(UUID(row["value"])),
        "label": row["filename"],
        "filename": row["filename"],
        "reference": None,
        "invoice_reference": None,
        "reference_basis": "not_available_in_reviewed_schema",
        "document_id": str(row["document_id"]),
        "source_created_at": created,
        "date": reviewed_date or created,
        "date_type": "reviewed_invoice_date" if reviewed_date else "reviewed_source_created_at",
        "supplier_party": supplier,
        "context_evaluation_id": str(row["context_evaluation_id"]),
        "context_basis": "latest_matching_evaluation_billing_scope",
        "description": (
            f"Recorded supplier: {supplier if supplier is not None else 'not returned'} · "
            f"source created {created} · choice {row['choice_number']}"
        ),
    }


def facet_page(session, access, filters, request, key=None):
    filters = effective_filters(filters, request.facet)
    identity = {
        "purpose": "exception-facets-v1",
        "organization": str(access.organization_id),
        "facet": request.facet,
        "search": request.search,
        "filters": filters.model_dump(mode="json"),
        "limit": request.limit,
    }
    binding = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    key = q.cursor_key() if key is None else key
    cursor = q.decode_cursor(request.after, binding, key) if request.after else None
    last = cursor.get("last") if cursor else None
    if cursor:
        try:
            if not isinstance(last, str) or not last or len(last) > 120:
                raise ValueError()
            if request.facet in {"contract", "invoice"} and (
                len(last) != 32 or UUID(last).hex != last
            ):
                raise ValueError()
        except ValueError:
            service.fail("INVALID_FACET_CURSOR", "Invalid facet cursor; restart the choices", 422)
    session.scalar(
        select(Organization.id)
        .where(Organization.id == access.organization_id)
        .with_for_update(read=True)
    )
    version = q.generation(session, access.organization_id)
    if cursor and cursor["generation"] != version:
        service.fail("FACETS_CHANGED", "Financial records changed; restart the choices", 409)
    ids = None
    if filters.current or filters.needs_review:
        # No COUNT needed: reading 101 candidates is enough to enforce the unchanged 100 cap.
        candidates = session.scalars(
            q.filtered_query(access.organization_id, filters)
            .order_by(E.id)
            .limit(q.DYNAMIC_LIMIT + 1)
        ).all()
        if len(candidates) > q.DYNAMIC_LIMIT:
            service.fail(
                "DYNAMIC_FILTER_LIMIT",
                "Facet currentness/review requires at most 100 SQL candidates after removing "
                "the facet's own criterion; narrow other recorded-value filters",
                422,
            )
        ids = []
        started = time.monotonic()
        for row in candidates:
            if time.monotonic() - started > 15:
                service.fail("FACET_QUERY_BUDGET", "Narrow the criteria and retry the choices", 503)
            item = service.serialize_evaluation(session, access, row)
            if (not filters.current or not item["stale"]) and (
                not filters.needs_review or q.needs_review(item)
            ):
                ids.append(row.id)
    rows = (
        session.execute(facet_statement(access.organization_id, filters, request, last, ids))
        .mappings()
        .all()
    )
    more, rows = len(rows) > request.limit, rows[: request.limit]
    items = (
        [
            {"value": row["value"], "label": row["value"], "identity": "snapshot_string"}
            for row in rows
        ]
        if request.facet == "supplier"
        else [
            invoice_item(row) if request.facet == "invoice" else contract_item(row) for row in rows
        ]
    )
    following = None
    if more and rows:
        following = q.encode_cursor(
            {
                "v": 1,
                "binding": binding,
                "anchor": str(UUID(int=0)),
                "last": rows[-1]["value"],
                "generation": version,
                "seen": (cursor["seen"] if cursor else 0) + len(rows),
                "expires": cursor["expires"] if cursor else int(time.time()) + 900,
            },
            key,
        )
    return {
        "facet": request.facet,
        "items": items,
        "limit": request.limit,
        "has_more": more,
        "next_cursor": following,
        "order": "snapshot_string_C" if request.facet == "supplier" else "stable_source_id",
        "ignored_filter": OWN_FILTER[request.facet],
        "coverage": "Other V1.4 filters apply, including missing_contract. No evaluation counts. "
        "Currentness/review exact only within 100 SQL candidates after ignoring the own criterion.",
        "consistency": "Request-coherent; financial changes invalidate the cursor. "
        "New searches may return changed labels. No cross-request snapshot.",
    }
