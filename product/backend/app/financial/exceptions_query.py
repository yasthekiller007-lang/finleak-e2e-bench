"""Bounded PostgreSQL exception reads. No financial policy, writes or cached currentness."""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import ARRAY, String, Text, and_, case, cast, distinct, func, literal, or_, select
from sqlalchemy.dialects.postgresql import JSONB

from app.db.models import Document, Organization
from app.financial import service
from app.financial.models import (
    FinancialAudit,
)
from app.financial.models import (
    FinancialEvaluation as E,
)
from app.financial.models import (
    FinancialFindingDecision as D,
)
from app.financial.models import (
    ReviewedFinancialSource as S,
)

SORTS = Literal["newest", "oldest", "amount_high", "amount_low", "outcome"]
DYNAMIC_LIMIT = 100
_PROCESS_KEY = secrets.token_bytes(32)


class Filters(BaseModel):
    q: str = Field(default="", max_length=160)
    invoice_source_id: UUID | None = None
    invoice_document_id: UUID | None = None
    outcome: str | None = Field(default=None, max_length=32)
    decision_status: Literal["confirmed", "false_positive", "needs_review", "unrecorded"] | None = (
        None
    )
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    supplier: str | None = Field(default=None, min_length=1, max_length=120)
    contract_source_id: UUID | None = None
    missing_contract: bool = False
    created_from: datetime | None = None
    created_to: datetime | None = None
    current: bool = False
    needs_review: bool = False
    sort: SORTS = "newest"

    @model_validator(mode="after")
    def validate_bounds(self):
        self.q = self.q.strip()
        if any(ord(c) < 32 for c in self.q):
            raise ValueError("Control characters are not supported")
        for date in (self.created_from, self.created_to):
            if date is not None and date.utcoffset() is None:
                raise ValueError("Creation dates require a timezone")
        if self.created_from and self.created_to and self.created_from >= self.created_to:
            raise ValueError("Creation period is empty")
        if self.missing_contract and self.contract_source_id:
            raise ValueError("Conflicting contract criteria")
        return self


def binding(org, filters, limit):
    value = {"org": str(org), "filters": filters.model_dump(mode="json"), "limit": limit}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def cursor_key():
    configured = os.environ.get("FLA_EXCEPTIONS_CURSOR_KEY")
    if configured is None:
        return _PROCESS_KEY
    try:
        key = bytes.fromhex(configured)
        if len(key) < 32:
            raise ValueError()
        return key
    except ValueError:
        service.fail("CURSOR_CONFIGURATION", "Exception cursor configuration is unavailable", 503)


def encode_cursor(payload, key):
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    mac = hmac.digest(key, raw, "sha256")
    return base64.urlsafe_b64encode(raw + mac).decode().rstrip("=")


def decode_cursor(token, expected, key, now=None):
    try:
        if (
            len(token) > 2048
            or not token
            or any(
                c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
                for c in token
            )
        ):
            raise ValueError()
        packed = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        raw, mac = packed[:-32], packed[-32:]
        if not hmac.compare_digest(mac, hmac.digest(key, raw, "sha256")):
            raise ValueError()
        value = json.loads(raw)
        if value["v"] != 1 or value["binding"] != expected:
            raise ValueError()
        UUID(value["anchor"])
        if type(value["seen"]) is not int or value["seen"] < 1:
            raise ValueError()
        if type(value["expires"]) is not int or value["expires"] < (
            time.time() if now is None else now
        ):
            raise ValueError()
        if not isinstance(value["generation"], list) or len(value["generation"]) != 2:
            raise ValueError()
        return value
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        service.fail(
            "INVALID_EXCEPTIONS_CURSOR",
            "Cursor expired, invalid or incompatible; restart the query",
            422,
        )


def approved_contract_expression():
    # Mirror UUID(str(value)) normalization used by V1.3, without casting invalid text.
    inputs = E.snapshot["inputs"]
    array = case((func.jsonb_typeof(inputs) == "array", inputs), else_=cast(literal("[]"), JSONB))
    row = func.jsonb_array_elements(array).table_valued("value").alias("association_entry")
    value = row.c.value
    raw = value.op("#>>")(cast(literal("{payload,value,contract_source_id}"), ARRAY(Text)))
    normalized = func.lower(
        func.replace(
            func.btrim(func.replace(func.replace(raw, "urn:", ""), "uuid:", ""), "{}"), "-", ""
        )
    )
    return (
        select(func.min(normalized))
        .select_from(row)
        .where(
            value.op("->>")("kind") == "association",
            value.op("->>")("state") == "approved",
            value.op("->>")("source_id") == cast(E.invoice_source_id, String),
            normalized.op("~")("^[0-9a-f]{32}$"),
        )
        .having(func.count(distinct(normalized)) == 1)
        .correlate(E)
        .scalar_subquery()
    )


def supplier_expression():
    value = E.snapshot["billing_scope"]["supplier_party"]
    return case(
        (and_(func.jsonb_typeof(value) == "string", value.astext != ""), value.astext), else_=None
    )


def latest_status_expression():
    return (
        select(D.status)
        .where(D.organization_id == E.organization_id, D.evaluation_id == E.id)
        .order_by(D.number.desc())
        .limit(1)
        .correlate(E)
        .scalar_subquery()
    )


def filtered_query(org, filters):
    query = select(E).where(E.organization_id == org)
    if filters.invoice_source_id:
        query = query.where(E.invoice_source_id == filters.invoice_source_id)
    if filters.invoice_document_id:
        query = query.where(
            select(S.id)
            .where(
                S.organization_id == org,
                S.id == E.invoice_source_id,
                S.document_id == filters.invoice_document_id,
            )
            .exists()
        )
    if filters.outcome:
        query = query.where(E.outcome == filters.outcome)
    if filters.currency:
        query = query.where(E.currency == filters.currency)
    if filters.supplier:
        query = query.where(supplier_expression().collate("C") == filters.supplier)
    if filters.contract_source_id or filters.missing_contract:
        contract = approved_contract_expression()
        query = query.where(
            contract == filters.contract_source_id.hex
            if filters.contract_source_id
            else contract.is_(None)
        )
    if filters.created_from:
        query = query.where(E.created_at >= filters.created_from)
    if filters.created_to:
        query = query.where(E.created_at < filters.created_to)
    if filters.decision_status:
        status = latest_status_expression()
        query = query.where(
            status.is_(None)
            if filters.decision_status == "unrecorded"
            else status == filters.decision_status
        )
    if filters.q:
        # Literal substring; SQL wildcards are escaped, not promoted to query syntax.
        q = "%" + filters.q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        references = E.snapshot["billing_scope"]["contract_references"]
        safe = case(
            (func.jsonb_typeof(references) == "array", references), else_=cast(literal("[]"), JSONB)
        )
        ref = func.jsonb_array_elements(safe).table_valued("value").alias("reference_entry")
        reference_match = (
            select(literal(1))
            .select_from(ref)
            .where(
                func.jsonb_typeof(ref.c.value) == "string",
                ref.c.value.op("#>>")(cast(literal("{}"), ARRAY(Text))).ilike(q, escape="\\"),
            )
            .correlate(E)
            .exists()
        )
        query = query.where(
            or_(
                E.scope_key.ilike(q, escape="\\"),
                E.explanation.ilike(q, escape="\\"),
                E.snapshot["billing_scope"]["label"].astext.ilike(q, escape="\\"),
                supplier_expression().ilike(q, escape="\\"),
                cast(E.id, String).ilike(q, escape="\\"),
                reference_match,
            )
        )
    return query


def ordering(sort):
    if sort in {"amount_high", "amount_low"}:
        return [
            (case((E.currency.is_(None), 1), else_=0), False),
            (func.coalesce(E.currency, "").collate("C"), False),
            (case((or_(E.currency.is_(None), E.potential.is_(None)), 1), else_=0), False),
            (
                case(
                    (E.currency.is_(None), Decimal("0")),
                    else_=func.coalesce(E.potential, Decimal("0")),
                ),
                sort == "amount_high",
            ),
            (E.id, False),
        ]
    if sort == "outcome":
        return [(E.outcome.collate("C"), False), (E.id, False)]
    return [(E.created_at, sort == "newest"), (E.id, False)]


def anchor_values(row, sort):
    if sort in {"amount_high", "amount_low"}:
        return [
            int(row.currency is None),
            row.currency or "",
            int(row.currency is None or row.potential is None),
            row.potential
            if row.currency is not None and row.potential is not None
            else Decimal("0"),
            row.id,
        ]
    return [row.outcome, row.id] if sort == "outcome" else [row.created_at, row.id]


def after_expression(keys, values):
    equal = []
    branches = []
    for (column, descending), value in zip(keys, values, strict=True):
        branches.append(and_(*equal, column < value if descending else column > value))
        equal.append(column == value)
    return or_(*branches)


def generation(session, org):
    # These append-only relations are written under the same organization lock.
    return [
        session.scalar(select(func.count()).select_from(table).where(table.organization_id == org))
        for table in (FinancialAudit, S)
    ]


def needs_review(item):
    return not item["stale"] and (
        item["outcome"] == "NEEDS_REVIEW"
        or (item["potential"] is not None and item["status"] not in {"confirmed", "false_positive"})
    )


def query_page(
    session, access, filters, limit=20, offset=0, pagination="offset", after=None, key=None
):
    started = time.monotonic()

    def serialize(row):
        if time.monotonic() - started > 15:
            service.fail(
                "EXCEPTIONS_QUERY_BUDGET", "Query work budget exceeded; narrow the filters", 503
            )
        return service.serialize_evaluation(session, access, row)

    if (
        not 1 <= limit <= 100
        or not 0 <= offset <= 100000
        or pagination not in {"offset", "cursor"}
        or (after and (pagination != "cursor" or offset))
        or (pagination == "cursor" and offset)
    ):
        service.fail(
            "INVALID_EXCEPTIONS_PAGE", "Use a bounded offset or cursor page, not both", 422
        )
    key = cursor_key() if key is None else key
    bound = binding(access.organization_id, filters, limit)
    cursor = decode_cursor(after, bound, key) if after else None
    # Same lock as financial writers; count, page and business currentness agree within this read.
    session.scalar(
        select(Organization.id)
        .where(Organization.id == access.organization_id)
        .with_for_update(read=True)
    )
    version = generation(session, access.organization_id)
    if cursor and cursor["generation"] != version:
        service.fail(
            "EXCEPTIONS_CHANGED",
            "Financial records changed during pagination; restart the query",
            409,
        )
    query = filtered_query(access.organization_id, filters)
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    keys = ordering(filters.sort)
    order = [column.desc() if descending else column.asc() for column, descending in keys]
    dynamic = filters.current or filters.needs_review
    if dynamic and total > DYNAMIC_LIMIT:
        service.fail(
            "DYNAMIC_FILTER_LIMIT",
            "Currentness/review filtering requires at most 100 SQL candidates; "
            "narrow the recorded-value filters",
            422,
        )
    seen = cursor["seen"] if cursor else offset
    if dynamic:
        # At most 100 candidates, before total and page. No approximate SQL currentness.
        candidates = session.scalars(query.order_by(*order).limit(DYNAMIC_LIMIT)).all()
        mapped = [(r, serialize(r)) for r in candidates]
        mapped = [
            (r, i)
            for r, i in mapped
            if (not filters.current or not i["stale"])
            and (not filters.needs_review or needs_review(i))
        ]
        total = len(mapped)
        if cursor:
            index = next(
                (i for i, (r, _) in enumerate(mapped) if str(r.id) == cursor["anchor"]), None
            )
            if index is None or index + 1 != seen:
                service.fail(
                    "INVALID_EXCEPTIONS_CURSOR", "Cursor no longer matches this query", 422
                )
        page = mapped[seen : seen + limit]
        rows, items = [r for r, _ in page], [i for _, i in page]
        more = seen + len(items) < total
    else:
        page_query = query
        if cursor:
            anchor = session.scalar(query.where(E.id == UUID(cursor["anchor"])).limit(1))
            if anchor is None:
                service.fail("INVALID_EXCEPTIONS_CURSOR", "Cursor anchor is unavailable", 422)
            page_query = page_query.where(
                after_expression(keys, anchor_values(anchor, filters.sort))
            )
        rows = session.scalars(page_query.order_by(*order).offset(offset).limit(limit + 1)).all()
        more = len(rows) > limit
        rows = rows[:limit]
        items = [serialize(row) for row in rows]
    # Batch names for this page only, independently tenant-scoped. No relationship guessing.
    ids = {UUID(i["invoice_source_id"]) for i in items}
    ids.update(
        UUID(i["queue_context"]["contract_source_id"])
        for i in items
        if i["queue_context"]["contract_source_id"]
    )
    names = {}
    if ids:
        for sid, did, filename in session.execute(
            select(S.id, S.document_id, Document.original_filename)
            .join(
                Document,
                and_(Document.id == S.document_id, Document.organization_id == S.organization_id),
            )
            .where(S.organization_id == access.organization_id, S.id.in_(ids))
            .limit(200)
        ).all():
            names[str(sid)] = (str(did), filename)
    for item in items:
        invoice = names.get(item["invoice_source_id"])
        contract = names.get(item["queue_context"]["contract_source_id"])
        item.update(
            invoice_document_id=invoice[0] if invoice else None,
            invoice_filename=invoice[1] if invoice else None,
            contract_filename=contract[1] if contract else None,
        )
    following = None
    if pagination == "cursor" and more and rows:
        following = encode_cursor(
            {
                "v": 1,
                "binding": bound,
                "generation": version,
                "anchor": str(rows[-1].id),
                "seen": seen + len(items),
                "expires": cursor["expires"] if cursor else int(time.time()) + 900,
            },
            key,
        )
    return {
        "items": items,
        "total": total,
        "total_exact": True,
        "limit": limit,
        "offset": seen,
        "has_more": more,
        "next_cursor": following,
        "pagination": pagination,
        "consistency": (
            "Request-coherent; cursor invalidated by financial changes. No cross-request snapshot."
        ),
        "coverage": (
            "Recorded-value filters precede counting and pagination. "
            "Dynamic currentness/review is exact for at most 100 SQL candidates."
        ),
    }
