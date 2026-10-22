"""Explicit SQL compilation and mocked session boundaries, never PostgreSQL/OIDC integration."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql
from starlette.requests import Request

from app.api.financial import facet_parameters
from app.core.config import Settings
from app.financial import exceptions_facets as f
from app.financial import exceptions_query as q
from app.financial.presentation import queue_context
from app.main import create_app

ORG = UUID(int=1000)
ACCESS = SimpleNamespace(organization_id=ORG)
KEY = b"SYNTHETIC-FACET-TEST-KEY-ONLY-32-BYTES"


def compiled(statement):
    return statement.compile(dialect=postgresql.dialect())


class Rows:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return self.rows


class Boundary:
    """Returns preselected rows; deliberately does not implement SQL semantics."""

    def __init__(self, rows=(), candidates=()):
        self.rows, self.candidates, self.statements = list(rows), list(candidates), []

    def scalar(self, statement):
        self.statements.append(statement)
        return ORG

    def execute(self, statement):
        self.statements.append(statement)
        return Rows(self.rows)

    def scalars(self, statement):
        self.statements.append(statement)
        return Rows(self.candidates)


@pytest.fixture(autouse=True)
def explicit_generation(monkeypatch):
    monkeypatch.setattr(q, "generation", lambda *_: [4, 8])


@pytest.mark.parametrize("facet", ["supplier", "contract"])
def test_query_is_tenant_scoped_parameterized_bounded_and_has_no_evaluation_counts(facet):
    filters = q.Filters(currency="USD", supplier="Alpha", outcome="NEEDS_REVIEW")
    statement = f.facet_statement(
        ORG, filters, f.FacetRequest(facet=facet, search="q%_'\\", limit=50)
    )
    sql = str(compiled(statement))
    assert "financial_evaluations.organization_id =" in sql
    assert "currency =" in sql and "outcome =" in sql and 'COLLATE "C"' in sql
    assert "q%_" not in sql and "Alpha" not in sql and statement._limit_clause.value == 51
    assert "count(*)" not in sql.lower()
    assert "%q\\%\\_'\\\\%" in compiled(statement).params.values()
    if facet == "contract":
        assert "reviewed_financial_sources.organization_id =" in sql
        assert "documents.organization_id =" in sql
        assert "DISTINCT ON" in sql and "created_at DESC" in sql
        assert "contract" in compiled(statement).params.values()


@pytest.mark.parametrize(
    "facet,ignored,retained",
    [
        ("supplier", "supplier", "contract_source_id"),
        ("contract", "contract_source_id", "supplier"),
    ],
)
def test_only_own_criterion_is_ignored(facet, ignored, retained):
    original = q.Filters(
        supplier="Alpha", contract_source_id=uuid4(), q="usage", current=True, sort="amount_high"
    )
    filters = f.effective_filters(original, facet)
    assert getattr(filters, ignored) is None and getattr(filters, retained) == getattr(
        original, retained
    )
    assert filters.q == "usage" and filters.current and filters.sort == "newest"
    assert original.sort == "amount_high" and original.supplier == "Alpha"


def test_missing_contract_remains_active_and_contract_options_cannot_be_invented():
    for facet in ("supplier", "contract"):
        effective = f.effective_filters(q.Filters(missing_contract=True), facet)
        assert effective.missing_contract
        sql = str(compiled(f.facet_statement(ORG, effective, f.FacetRequest(facet=facet))))
        assert "IS NULL" in sql
        if facet == "contract":
            assert "IS NOT NULL" in sql


def test_supplier_is_a_distinct_exact_snapshot_string_not_a_legal_party():
    statement = f.facet_statement(ORG, q.Filters(), f.FacetRequest(facet="supplier"))
    sql = str(compiled(statement))
    assert "SELECT DISTINCT" in sql and "supplier_party" in compiled(statement).params.values()
    assert "lower(" not in sql and "btrim(" not in sql
    values = [" ACME", "ACME", "Acme", "Acme ", "acme"]
    result = f.facet_page(
        Boundary([{"value": v} for v in values]),
        ACCESS,
        q.Filters(),
        f.FacetRequest(facet="supplier"),
        KEY,
    )
    assert [i["value"] for i in result["items"]] == values
    assert all(i["identity"] == "snapshot_string" for i in result["items"])
    assert "total" not in result


def test_unchanged_association_expression_rejects_ambiguous_or_unapproved_contracts():
    statement = f.facet_statement(ORG, q.Filters(), f.FacetRequest(facet="contract"))
    sql = str(compiled(statement))
    assert (
        "HAVING count(DISTINCT lower(" in sql and "financial_evaluations.invoice_source_id" in sql
    )
    assert "financial_revisions" not in sql
    invoice, one, two = uuid4(), uuid4(), uuid4()

    def entry(contract, state="approved"):
        return {
            "source_id": str(invoice),
            "kind": "association",
            "state": state,
            "payload": {"value": {"contract_source_id": str(contract)}},
        }

    assert queue_context({"inputs": [entry(one), entry(one)]}, invoice)[
        "contract_source_id"
    ] == str(one)
    assert (
        queue_context({"inputs": [entry(one), entry(two)]}, invoice)["contract_source_id"] is None
    )
    assert (
        queue_context({"inputs": [entry(one, "prepared")]}, invoice)["contract_source_id"] is None
    )


def contract_row(n, reference="SAME-REF", filename="Agreement.pdf"):
    return {
        "value": UUID(int=n).hex,
        "reference": reference,
        "filename": filename,
        "document_id": UUID(int=n + 100),
        "source_created_at": datetime(2026, 10, 19, tzinfo=UTC),
        "effective_from": "2026-01-01",
        "effective_to": "2027-01-01",
        "choice_number": n,
    }


def test_equal_references_stay_separate_with_readable_disambiguation():
    result = f.facet_page(
        Boundary([contract_row(1), contract_row(2)]),
        ACCESS,
        q.Filters(),
        f.FacetRequest(facet="contract"),
        KEY,
    )
    one, two = result["items"]
    assert one["label"] == two["label"] == "SAME-REF" and one["value"] != two["value"]
    assert one["description"] != two["description"] and one["value"] not in one["description"]
    assert "supplier" not in one and one["effective_from"] == "2026-01-01"


def test_reference_fallback_uses_real_filename_and_ambiguous_frozen_metadata_is_null():
    item = f.contract_item(contract_row(1, reference=None, filename="Reviewed agreement.pdf"))
    assert item["label"] == "Reviewed agreement.pdf" and item["reference"] is None
    sql = str(compiled(f.facet_statement(ORG, q.Filters(), f.FacetRequest(facet="contract"))))
    assert "HAVING count(DISTINCT CAST(facet_reference.value" in sql
    assert "HAVING count(DISTINCT CAST(facet_packet.value" in sql


@pytest.mark.parametrize("facet", ["supplier", "contract"])
def test_empty_result_has_no_counts_or_cursor(facet):
    result = f.facet_page(
        Boundary(), ACCESS, q.Filters(), f.FacetRequest(facet=facet, search="no match"), KEY
    )
    assert result["items"] == [] and not result["has_more"] and result["next_cursor"] is None
    assert "total" not in result


@pytest.mark.parametrize("facet", ["supplier", "contract"])
def test_pagination_uses_a_strict_anchor_and_does_not_repeat_equal_labels(facet):
    rows = (
        [{"value": x} for x in ("Alpha", "Beta", "Gamma")]
        if facet == "supplier"
        else [contract_row(n) for n in (1, 2, 3)]
    )
    first = f.facet_page(
        Boundary(rows), ACCESS, q.Filters(), f.FacetRequest(facet=facet, limit=2), KEY
    )
    assert len(first["items"]) == 2 and first["has_more"]
    session = Boundary(rows[2:])
    second = f.facet_page(
        session,
        ACCESS,
        q.Filters(),
        f.FacetRequest(facet=facet, limit=2, after=first["next_cursor"]),
        KEY,
    )
    assert not second["has_more"] and len(second["items"]) == 1
    assert rows[1]["value"] in compiled(session.statements[-1]).params.values()
    assert " > " in str(compiled(session.statements[-1]))
    expected = [i["value"] if facet == "supplier" else str(UUID(i["value"])) for i in rows]
    assert [i["value"] for i in first["items"] + second["items"]] == expected


@pytest.mark.parametrize("change", ["tenant", "search", "type", "criteria", "limit", "tamper"])
def test_cursor_cannot_cross_tenant_query_type_or_criteria(change):
    first = f.facet_page(
        Boundary([{"value": "A"}, {"value": "B"}]),
        ACCESS,
        q.Filters(),
        f.FacetRequest(facet="supplier", limit=1),
        KEY,
    )
    request = {"facet": "supplier", "limit": 1, "after": first["next_cursor"]}
    access, filters = ACCESS, q.Filters()
    if change == "tenant":
        access = SimpleNamespace(organization_id=uuid4())
    if change == "search":
        request["search"] = "A"
    if change == "type":
        request["facet"] = "contract"
    if change == "criteria":
        filters = q.Filters(currency="EUR")
    if change == "limit":
        request["limit"] = 2
    if change == "tamper":
        request["after"] = request["after"][:-8] + "a0a0a0a0"
    session = Boundary()
    with pytest.raises(HTTPException) as error:
        f.facet_page(session, access, filters, f.FacetRequest(**request), KEY)
    assert error.value.status_code == 422 and session.statements == []


def test_changed_financial_generation_requires_restart_before_options(monkeypatch):
    first = f.facet_page(
        Boundary([{"value": "A"}, {"value": "B"}]),
        ACCESS,
        q.Filters(),
        f.FacetRequest(facet="supplier", limit=1),
        KEY,
    )
    monkeypatch.setattr(q, "generation", lambda *_: [5, 8])
    session = Boundary()
    with pytest.raises(HTTPException) as error:
        f.facet_page(
            session,
            ACCESS,
            q.Filters(),
            f.FacetRequest(facet="supplier", limit=1, after=first["next_cursor"]),
            KEY,
        )
    assert error.value.status_code == 409 and error.value.detail["code"] == "FACETS_CHANGED"
    assert len(session.statements) == 1


def test_dynamic_cap_applies_after_ignoring_own_criterion_before_serialization(monkeypatch):
    session = Boundary(candidates=[SimpleNamespace(id=UUID(int=n)) for n in range(101)])

    def unexpected(*_):
        pytest.fail("Serialization must not run over the cap")

    monkeypatch.setattr(f.service, "serialize_evaluation", unexpected)
    with pytest.raises(HTTPException) as error:
        f.facet_page(
            session,
            ACCESS,
            q.Filters(current=True, supplier="Selected"),
            f.FacetRequest(facet="supplier"),
            KEY,
        )
    assert error.value.detail["code"] == "DYNAMIC_FILTER_LIMIT"
    assert "Selected" not in compiled(session.statements[-1]).params.values()
    assert session.statements[-1]._limit_clause.value == 101


def test_currentness_review_use_existing_serializer_then_filter_before_distinct(monkeypatch):
    candidates = [SimpleNamespace(id=UUID(int=n), stale=n == 1) for n in range(1, 4)]
    monkeypatch.setattr(
        f.service,
        "serialize_evaluation",
        lambda _s, _a, r: {
            "stale": r.stale,
            "outcome": "POTENTIAL_LEAKAGE",
            "potential": "1000",
            "status": "confirmed" if r.id.int == 2 else "detected",
        },
    )
    session = Boundary([{"value": "A"}], candidates)
    f.facet_page(
        session,
        ACCESS,
        q.Filters(current=True, needs_review=True),
        f.FacetRequest(facet="supplier"),
        KEY,
    )
    assert [UUID(int=3)] in compiled(session.statements[-1]).params.values()


@pytest.mark.parametrize(
    "params",
    [
        {"facet": "party"},
        {"facet": "supplier", "search": "x" * 121},
        {"facet": "supplier", "search": "a\nb"},
        {"facet": "contract", "limit": 51},
        {"facet": "contract", "limit": 0},
        {"facet": "supplier", "after": "x" * 2049},
    ],
)
def test_parameters_are_bounded(params):
    with pytest.raises(ValidationError):
        f.FacetRequest(**params)


@pytest.mark.parametrize(
    "query",
    [
        b"facet=supplier&evil=true",
        b"facet=supplier&facet=contract",
        b"facet=supplier&search=a&search=b",
    ],
)
def test_unknown_or_repeated_params_are_rejected(query):
    with pytest.raises(HTTPException) as error:
        facet_parameters(Request({"type": "http", "query_string": query}))
    assert error.value.status_code == 422


def test_actual_openapi_retains_v14_and_new_route_requires_authentication(tmp_path):
    app = create_app(Settings(_env_file=None, environment="test", storage_root=tmp_path))
    schema = app.openapi()
    prefix = "/api/v1/organizations/{organization_id}/financial"
    assert prefix + "/evaluations/{evaluation_id}" in schema["paths"]
    params = {
        p["name"]: p for p in schema["paths"][prefix + "/exception-facets"]["get"]["parameters"]
    }
    assert params["facet"]["required"] and params["limit"]["schema"]["maximum"] == 50
    assert {
        "current",
        "needs_review",
        "supplier",
        "contract_source_id",
        "missing_contract",
        "search",
    } <= params.keys()
    with TestClient(app) as client:
        assert (
            client.get(
                f"/api/v1/organizations/{ORG}/financial/exception-facets?facet=supplier"
            ).status_code
            == 401
        )
        assert (
            client.get(
                f"/api/v1/organizations/{ORG}/financial/exception-facets?facet=contract",
                headers={"Authorization": "Bearer forged-synthetic-token"},
            ).status_code
            == 503
        )


def test_expired_cursor_is_rejected_before_sql(monkeypatch):
    first = f.facet_page(
        Boundary([{"value": "A"}, {"value": "B"}]),
        ACCESS,
        q.Filters(),
        f.FacetRequest(facet="supplier", limit=1),
        KEY,
    )
    monkeypatch.setattr(q.time, "time", lambda: 99999999999)
    session = Boundary()
    with pytest.raises(HTTPException) as error:
        f.facet_page(
            session,
            ACCESS,
            q.Filters(),
            f.FacetRequest(facet="supplier", limit=1, after=first["next_cursor"]),
            KEY,
        )
    assert error.value.status_code == 422 and not session.statements


def test_all_compatible_v14_criteria_reach_the_facet_query():
    filters = q.Filters(
        invoice_source_id=uuid4(),
        invoice_document_id=uuid4(),
        outcome="NEEDS_REVIEW",
        decision_status="confirmed",
        currency="USD",
        supplier="A",
        contract_source_id=uuid4(),
        created_from="2026-10-01T00:00:00Z",
        created_to="2026-11-01T00:00:00Z",
        q="literal",
    )
    for facet in ("supplier", "contract"):
        effective = f.effective_filters(filters, facet)
        sql = str(compiled(f.facet_statement(ORG, effective, f.FacetRequest(facet=facet))))
        for expected in [
            "created_at >=",
            "created_at <",
            "invoice_source_id =",
            "financial_finding_decisions.organization_id =",
            "ILIKE",
            "documents.organization_id ="
            if facet == "contract"
            else "reviewed_financial_sources.organization_id =",
        ]:
            assert expected in sql


def test_dynamic_work_budget_refuses_excessive_serialization(monkeypatch):
    times = iter([0, 16])
    monkeypatch.setattr(f.time, "monotonic", lambda: next(times))
    session = Boundary(candidates=[SimpleNamespace(id=UUID(int=1))])
    with pytest.raises(HTTPException) as error:
        f.facet_page(
            session, ACCESS, q.Filters(current=True), f.FacetRequest(facet="supplier"), KEY
        )
    assert error.value.status_code == 503 and error.value.detail["code"] == "FACET_QUERY_BUDGET"
