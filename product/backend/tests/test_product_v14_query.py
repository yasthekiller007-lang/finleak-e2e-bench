"""PostgreSQL compilation and explicitly mocked session boundaries; NOT database integration."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.elements import BooleanClauseList, Grouping

from app.financial import exceptions_query as q
from app.financial.presentation import queue_context

ORG = uuid4()
ACCESS = SimpleNamespace(organization_id=ORG)
KEY = b"SYNTHETIC-UNIT-TEST-CURSOR-KEY-ONLY-32"


def sql(statement):
    return str(statement.compile(dialect=postgresql.dialect()))


def row(n, potential="1000", currency="USD", stale=False):
    return SimpleNamespace(
        id=UUID(int=n),
        invoice_source_id=UUID(int=100),
        potential=Decimal(potential) if potential is not None else None,
        currency=currency,
        created_at=datetime(2026, 10, 19, tzinfo=UTC),
        outcome="POTENTIAL_LEAKAGE" if potential else "NEEDS_REVIEW",
        stale=stale,
    )


def payload(row):
    return {
        "id": str(row.id),
        "invoice_source_id": str(row.invoice_source_id),
        "potential": str(row.potential) if row.potential is not None else None,
        "stale": row.stale,
        "status": "detected",
        "outcome": row.outcome,
        "queue_context": {"contract_source_id": None},
    }


class Result:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class BoundarySession:
    """Returns preselected rows; does not execute SQL or stand in for PostgreSQL."""

    def __init__(self, rows):
        self.rows = rows
        self.statements = []

    def scalar(self, statement):
        self.statements.append(statement)
        compiled = statement.compile()
        if "count(" in str(compiled):
            return len(self.rows)
        if "financial_evaluations" in str(compiled):
            uid = next(
                (v for v in compiled.params.values() if isinstance(v, UUID) and v != ORG), None
            )
            return next((r for r in self.rows if r.id == uid), None)
        return ORG

    def scalars(self, statement):
        self.statements.append(statement)
        return Result(self.rows)

    def execute(self, statement):
        self.statements.append(statement)
        return Result([])


@pytest.fixture
def boundary(monkeypatch):
    monkeypatch.setattr(q, "generation", lambda *_: [8, 2])
    monkeypatch.setattr(q.service, "serialize_evaluation", lambda session, access, r: payload(r))


def test_combined_filters_and_count_have_the_same_tenant_scoped_predicates():
    filters = q.Filters(
        q="literal%_\\'",
        currency="USD",
        supplier="DEMO supplier",
        invoice_source_id=uuid4(),
        invoice_document_id=uuid4(),
        contract_source_id=uuid4(),
        decision_status="confirmed",
        outcome="POTENTIAL_LEAKAGE",
        created_from="2026-10-01T00:00:00Z",
        created_to="2026-11-01T00:00:00Z",
    )
    statement = q.filtered_query(ORG, filters)
    rendered = sql(statement)
    counted = sql(select(func.count()).select_from(statement.subquery()))
    for fragment in [
        "organization_id =",
        "invoice_source_id =",
        "ILIKE",
        "HAVING count(DISTINCT",
        "financial_finding_decisions.organization_id = financial_evaluations.organization_id",
        "created_at >=",
        "created_at <",
    ]:
        assert fragment in rendered and fragment in counted
    assert "literal%" not in rendered and "DEMO supplier" not in rendered
    params = statement.compile(dialect=postgresql.dialect()).params
    assert any(v == "%literal\\%\\_\\\\'%" for v in params.values())
    assert ORG in params.values()


def test_approved_contract_sql_matches_v13_ambiguity_and_invalid_id_guards():
    rendered = sql(q.filtered_query(ORG, q.Filters(contract_source_id=uuid4())))
    assert "jsonb_array_elements" in rendered and "CAST(" in rendered and "TEXT[]" in rendered
    assert "count(DISTINCT" in rendered
    expression = q.approved_contract_expression().compile(dialect=postgresql.dialect())
    assert {"association", "approved", "source_id", "^[0-9a-f]{32}$"}.issubset(
        set(v for v in expression.params.values() if isinstance(v, str))
    )
    invoice = uuid4()
    contract = uuid4()

    def association(cid, state="approved"):
        return {
            "kind": "association",
            "state": state,
            "source_id": str(invoice),
            "payload": {"value": {"contract_source_id": str(cid)}},
        }

    assert (
        queue_context({"inputs": [association(contract), association(uuid4())]}, invoice)[
            "contract_source_id"
        ]
        is None
    )
    assert (
        queue_context({"inputs": [association(contract, "prepared")]}, invoice)[
            "contract_source_id"
        ]
        is None
    )
    assert queue_context({"inputs": [association("invalid"), association(contract)]}, invoice)[
        "contract_source_id"
    ] == str(contract)


@pytest.mark.parametrize("sort", ["newest", "oldest", "amount_high", "amount_low", "outcome"])
def test_every_order_has_a_unique_final_key_and_keyset_equality_branches(sort):
    keys = q.ordering(sort)
    values = q.anchor_values(row(1, "99999999999999.123456"), sort)
    rendered = sql(
        q.filtered_query(ORG, q.Filters())
        .where(q.after_expression(keys, values))
        .order_by(*[c.desc() if desc else c.asc() for c, desc in keys])
        .limit(21)
    )
    assert str(keys[-1][0]) == "FinancialEvaluation.id" and keys[-1][1] is False
    assert "financial_evaluations.id >" in rendered and "LIMIT" in rendered
    if len(keys) > 2:
        assert " OR " in rendered and " = " in rendered
    assert not any(
        isinstance(v, float) for v in q.after_expression(keys, values).compile().params.values()
    )


def test_numeric_currency_and_null_key_values_remain_exact():
    assert q.anchor_values(row(1, "99999999999999.123456"), "amount_high")[3] == Decimal(
        "99999999999999.123456"
    )
    assert q.anchor_values(row(2, None), "amount_high")[:4] == [0, "USD", 1, Decimal("0")]
    assert q.anchor_values(row(3, "1", "EUR"), "amount_high")[:2] == [0, "EUR"]
    statement = sql(
        q.filtered_query(ORG, q.Filters()).order_by(
            *[c.desc() if desc else c.asc() for c, desc in q.ordering("amount_high")]
        )
    )
    assert 'COLLATE "C"' in statement and "coalesce(financial_evaluations.potential" in statement
    assert "FLOAT" not in statement


@pytest.mark.parametrize("sort", ["newest", "oldest", "amount_high", "amount_low", "outcome"])
def test_keyset_predicate_ast_matches_an_independent_exact_order_with_ties(sort):
    """Evaluate the SQL predicate AST in memory, explicitly not a SQL execution test."""

    rows = [
        row(1, "99999999999999.123456"),
        row(2, "99999999999999.123455"),
        row(3, None),
        row(4, "2", "EUR"),
        row(5, "2", "EUR"),
        row(6, None, None),
        row(7, "9999", None),
        row(8, "1", None),
    ]

    def values(r):
        if sort.startswith("amount_"):
            return (
                r.currency is None,
                r.currency or "",
                r.currency is None or r.potential is None,
                (-r.potential if sort == "amount_high" else r.potential)
                if r.currency is not None and r.potential is not None
                else Decimal("0"),
                r.id,
            )
        if sort == "outcome":
            return (r.outcome, r.id)
        # Dates are intentionally identical: ID alone must retain every tie.
        return (r.created_at, r.id)

    ordered = sorted(rows, key=values)

    def matches(expression, record):
        if isinstance(expression, BooleanClauseList):
            results = [matches(c, record) for c in expression.clauses]
            return any(results) if expression.operator.__name__ == "or_" else all(results)
        left = expression.left.element if isinstance(expression.left, Grouping) else expression.left
        actual = next(
            value
            for (column, _), value in zip(
                q.ordering(sort), q.anchor_values(record, sort), strict=True
            )
            if left.compare(column.__clause_element__())
        )
        return expression.operator(actual, expression.right.value)

    for index, anchor in enumerate(ordered):
        predicate = q.after_expression(q.ordering(sort), q.anchor_values(anchor, sort))
        assert [r.id for r in ordered if matches(predicate, r)] == [
            r.id for r in ordered[index + 1 :]
        ]


def test_generation_counters_are_independently_tenant_scoped():
    session = BoundarySession([])
    q.generation(session, ORG)
    assert len(session.statements) == 2
    assert all(set(s.compile().params.values()) == {ORG} for s in session.statements)


@pytest.mark.parametrize(
    "arguments",
    [{"pagination": "cursor", "offset": 1}, {"after": "token"}, {"limit": 101}, {"offset": 100001}],
)
def test_invalid_or_mixed_pagination_is_rejected_before_sql(arguments):
    session = BoundarySession([])
    with pytest.raises(HTTPException) as error:
        q.query_page(session, ACCESS, q.Filters(), key=KEY, **arguments)
    assert error.value.status_code == 422 and session.statements == []


@pytest.mark.parametrize(
    "alter", ["organization", "filters", "sort", "limit", "tamper", "expired", "junk"]
)
def test_opaque_cursor_is_authenticated_and_bound_to_its_query(alter):
    filters = q.Filters(q="demo")
    expected = q.binding(ORG, filters, 20)
    token = q.encode_cursor(
        {
            "v": 1,
            "binding": expected,
            "anchor": str(uuid4()),
            "seen": 20,
            "generation": [2, 3],
            "expires": 200,
        },
        KEY,
    )
    target = expected
    if alter == "organization":
        target = q.binding(uuid4(), filters, 20)
    if alter == "filters":
        target = q.binding(ORG, q.Filters(q="different"), 20)
    if alter == "sort":
        target = q.binding(ORG, q.Filters(q="demo", sort="oldest"), 20)
    if alter == "limit":
        target = q.binding(ORG, filters, 50)
    if alter == "tamper":
        token = token[:8] + ("A" if token[8] != "A" else "B") + token[9:]
    if alter == "junk":
        token = "bad.!"
    with pytest.raises(HTTPException) as error:
        q.decode_cursor(token, target, KEY, now=201 if alter == "expired" else 100)
    assert error.value.status_code == 422


def test_cursor_round_trip_contains_no_money_or_identity_credentials():
    bound = q.binding(ORG, q.Filters(), 20)
    payload = {
        "v": 1,
        "binding": bound,
        "anchor": str(uuid4()),
        "seen": 20,
        "generation": [3, 4],
        "expires": 200,
    }
    assert q.decode_cursor(q.encode_cursor(payload, KEY), bound, KEY, now=100) == payload
    assert "supplier" not in json.dumps(payload) and "amount" not in json.dumps(payload)


def test_current_filter_is_applied_before_total_and_offset(boundary):
    rows = [row(1, stale=True), row(2), row(3, stale=True), row(4)]
    session = BoundarySession(rows)
    result = q.query_page(session, ACCESS, q.Filters(current=True), limit=1, offset=1, key=KEY)
    assert result["total"] == 2 and result["items"][0]["id"] == str(rows[3].id)
    assert result["total_exact"] and not result["has_more"]
    assert any("FOR SHARE" in sql(s) for s in session.statements)


def test_dynamic_filter_refuses_a_large_candidate_set_before_reading_it(boundary):
    session = BoundarySession([row(i) for i in range(1, 102)])
    with pytest.raises(HTTPException) as error:
        q.query_page(session, ACCESS, q.Filters(needs_review=True), key=KEY)
    assert error.value.status_code == 422 and error.value.detail["code"] == "DYNAMIC_FILTER_LIMIT"
    assert not any(s._limit_clause is not None for s in session.statements)


def test_multi_page_dynamic_cursor_keeps_equal_dates_and_amounts_without_duplicates(boundary):
    rows = [row(n) for n in range(1, 6)]
    session = BoundarySession(rows)
    filters = q.Filters(current=True, sort="amount_low")
    seen = []
    after = None
    while True:
        result = q.query_page(
            session, ACCESS, filters, limit=2, pagination="cursor", after=after, key=KEY
        )
        seen.extend(i["id"] for i in result["items"])
        assert result["total"] == 5
        after = result["next_cursor"]
        if after is None:
            break
    assert seen == [str(r.id) for r in rows] and len(set(seen)) == 5


def test_concurrent_financial_change_rejects_continuation_before_count_or_page(
    boundary, monkeypatch
):
    first = q.query_page(
        BoundarySession([row(1), row(2)]),
        ACCESS,
        q.Filters(),
        limit=1,
        pagination="cursor",
        key=KEY,
    )
    monkeypatch.setattr(q, "generation", lambda *_: [9, 2])
    session = BoundarySession([row(1), row(2), row(3)])
    with pytest.raises(HTTPException) as error:
        q.query_page(
            session,
            ACCESS,
            q.Filters(),
            limit=1,
            pagination="cursor",
            after=first["next_cursor"],
            key=KEY,
        )
    assert error.value.status_code == 409 and error.value.detail["code"] == "EXCEPTIONS_CHANGED"
    assert len(session.statements) == 1


def test_legacy_defaults_keep_offset_shape_and_apply_bounded_page_read(boundary):
    session = BoundarySession([row(1), row(2)])
    result = q.query_page(session, ACCESS, q.Filters(), limit=1, offset=0, key=KEY)
    assert result["pagination"] == "offset" and result["next_cursor"] is None
    assert {"items", "total", "limit", "offset", "coverage"}.issubset(result)
    pages = [s for s in session.statements if s._limit_clause is not None]
    assert pages[0]._limit_clause.value == 2 and len(result["items"]) == 1


@pytest.mark.parametrize(
    "filters",
    [
        {"q": "x" * 161},
        {"q": "line\nfeed"},
        {"currency": "usd"},
        {"created_from": "2026-10-19T00:00:00"},
        {"created_from": "2026-11-01T00:00:00Z", "created_to": "2026-10-01T00:00:00Z"},
        {"contract_source_id": str(uuid4()), "missing_contract": True},
    ],
)
def test_filter_validation_is_bounded_and_unambiguous(filters):
    with pytest.raises(ValidationError):
        q.Filters(**filters)


def test_new_filters_are_exposed_in_the_actual_openapi_contract():
    from app.core.config import Settings
    from app.main import create_app

    schema = create_app(Settings(_env_file=None, environment="test")).openapi()
    route = schema["paths"]["/api/v1/organizations/{organization_id}/financial/evaluations"]["get"]
    parameters = {p["name"]: p for p in route["parameters"]}
    assert parameters["q"]["schema"]["maxLength"] == 160
    assert parameters["current"]["schema"]["type"] == "boolean"
    assert {
        "limit",
        "offset",
        "pagination",
        "after",
        "contract_source_id",
        "decision_status",
    } <= parameters.keys()
