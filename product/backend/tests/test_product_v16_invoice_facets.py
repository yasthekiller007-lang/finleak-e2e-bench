"""Development contracts: compiled PostgreSQL and preselected mock rows, NOT native SQL."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.financial import exceptions_facets as f
from app.financial import exceptions_query as q
from app.financial.schema import Reference
from app.main import create_app
from tests.test_product_v15_facets import ACCESS, KEY, ORG, Boundary, compiled


@pytest.fixture(autouse=True)
def generation(monkeypatch):
    monkeypatch.setattr(q, "generation", lambda *_: [8, 4])


def row(n=1, filename="SAME-invoice.pdf", invoice_date=None):
    return {
        "value": UUID(int=n).hex,
        "filename": filename,
        "document_id": UUID(int=n + 100),
        "source_created_at": datetime(2026, 10, 19, tzinfo=UTC),
        "supplier_party": "SYNTHETIC supplier",
        "context_evaluation_id": UUID(int=n + 200),
        "choice_number": n,
        "invoice_date": invoice_date,
    }


def page(session=None, filters=None, **params):
    return f.facet_page(
        session or Boundary(),
        ACCESS,
        filters or q.Filters(),
        f.FacetRequest(facet="invoice", **params),
        KEY,
    )


def test_document_search_is_literal_bounded_scoped_and_does_not_borrow_legacy_invoice_numbers():
    statement = f.facet_statement(
        ORG,
        q.Filters(supplier="SYNTHETIC"),
        f.FacetRequest(facet="invoice", search="INV%_'\\", limit=50),
    )
    sql = str(compiled(statement))
    params = compiled(statement).params
    assert statement._limit_clause.value == 51 and "%INV\\%\\_'\\\\%" in params.values()
    assert "invoice_labels.filename ILIKE" in sql and "INV%_" not in sql
    assert (
        "JOIN invoices" not in sql
        and "invoice_number" not in sql
        and "contract_reference" not in params.values()
    )
    assert "financial_evaluations.organization_id =" in sql and "documents.organization_id =" in sql
    assert "reviewed_financial_sources.organization_id =" in sql and "invoice" in params.values()
    assert "count(" not in sql.lower()


def test_reviewed_reference_schema_has_no_invoice_number_and_no_field_is_promoted():
    assert set(Reference.model_fields) == {"contract_reference", "po_reference"}
    data = row(filename="CONTRACT-PO-123.pdf")
    data.update(
        invoice_number="LEGACY-SECRET", contract_reference="CONTRACT-123", po_reference="PO-123"
    )
    item = f.invoice_item(data)
    assert item["label"] == "CONTRACT-PO-123.pdf"
    assert item["invoice_reference"] is None and item["reference"] is None
    assert item["reference_basis"] == "not_available_in_reviewed_schema"
    assert "LEGACY-SECRET" not in str(item)


def test_existing_document_designation_is_searchable_but_never_parsed_into_a_number():
    item = f.invoice_item(row(filename="INV-APPROVED-FILE-2042.pdf"))
    assert item["label"] == "INV-APPROVED-FILE-2042.pdf" and item["invoice_reference"] is None
    assert "invoice_reference" not in str(
        compiled(
            f.facet_statement(ORG, q.Filters(), f.FacetRequest(facet="invoice", search="2042"))
        )
    )


def test_homonymous_documents_and_identical_document_references_keep_separate_source_identities():
    result = page(Boundary([row(1), row(2)]))
    one, two = result["items"]
    assert one["label"] == two["label"] and one["value"] != two["value"]
    assert one["document_id"] != two["document_id"] and one["description"] != two["description"]
    assert one["value"] not in one["description"]


def test_many_evaluations_are_reduced_by_source_not_by_name_before_paging():
    sql = str(compiled(f.facet_statement(ORG, q.Filters(), f.FacetRequest(facet="invoice"))))
    assert "DISTINCT ON (financial_evaluations.invoice_source_id)" in sql
    assert (
        "ORDER BY financial_evaluations.invoice_source_id, "
        "financial_evaluations.created_at DESC, financial_evaluations.id" in sql
    )
    assert "DISTINCT ON (documents.original_filename)" not in sql
    assert "latest_invoice_context.context_evaluation_id" in sql


@pytest.mark.parametrize("date_value", [None, "invalid", "2026-02-30", "2026-W01-1", 1234])
def test_missing_or_invalid_date_falls_back_to_explicit_source_creation(date_value):
    item = f.invoice_item(row(invoice_date=date_value))
    assert (
        item["date_type"] == "reviewed_source_created_at"
        and item["date"] == item["source_created_at"]
    )
    assert item["invoice_reference"] is None


def test_reviewed_date_supplier_and_evaluation_provenance_are_identified():
    item = f.invoice_item(row(invoice_date="2026-10-01"))
    assert item["date"] == "2026-10-01" and item["date_type"] == "reviewed_invoice_date"
    assert item["context_evaluation_id"] == str(UUID(int=201))
    assert item["supplier_party"] == "SYNTHETIC supplier"
    assert item["context_basis"] == "latest_matching_evaluation_billing_scope"


def test_missing_supplier_is_not_invented():
    data = row()
    data["supplier_party"] = None
    assert f.invoice_item(data)["supplier_party"] is None
    assert "not returned" in f.invoice_item(data)["description"]


def test_only_source_filter_is_ignored_document_constraint_and_all_others_remain():
    filters = q.Filters(
        invoice_source_id=uuid4(),
        invoice_document_id=uuid4(),
        supplier="Alpha",
        contract_source_id=uuid4(),
        currency="USD",
        decision_status="confirmed",
        current=True,
    )
    effective = f.effective_filters(filters, "invoice")
    assert effective.invoice_source_id is None
    assert (
        effective.invoice_document_id == filters.invoice_document_id
        and effective.supplier == "Alpha"
    )
    assert effective.contract_source_id == filters.contract_source_id and effective.current
    sql = str(compiled(f.facet_statement(ORG, effective, f.FacetRequest(facet="invoice"))))
    assert "reviewed_financial_sources.document_id =" in sql and 'COLLATE "C"' in sql
    assert "HAVING count(DISTINCT" in sql and "financial_finding_decisions.organization_id =" in sql


def test_wrong_source_type_is_excluded_by_an_exact_tenant_scoped_join():
    statement = f.facet_statement(ORG, q.Filters(), f.FacetRequest(facet="invoice"))
    sql = str(compiled(statement))
    params = compiled(statement).params
    assert (
        params["kind_1"] == "invoice"
        and "reviewed_financial_sources.id = latest_invoice_context.invoice_key" in sql
    )
    assert list(params.values()).count(ORG) == 3


def test_empty_result_is_explicit_and_does_not_create_decisions():
    session = Boundary()
    result = page(session, search="no result")
    assert result["items"] == [] and not result["has_more"] and result["next_cursor"] is None
    assert all(str(compiled(s)).startswith("SELECT ") for s in session.statements)
    assert not any(hasattr(session, method) for method in ("add", "commit", "flush"))


def test_invoice_cursor_paging_is_strict_and_deterministic_with_repeated_labels():
    first = page(Boundary([row(1), row(2), row(3)]), limit=2)
    session = Boundary([row(3)])
    second = page(session, limit=2, after=first["next_cursor"])
    assert [i["value"] for i in first["items"] + second["items"]] == [
        str(UUID(int=n)) for n in (1, 2, 3)
    ]
    assert (
        not second["has_more"]
        and UUID(int=2).hex in compiled(session.statements[-1]).params.values()
    )
    assert 'invoice_labels.value COLLATE "C") >' in str(compiled(session.statements[-1]))


@pytest.mark.parametrize(
    "change", ["tenant", "facet", "document", "supplier", "search", "limit", "tamper", "expired"]
)
def test_incompatible_or_expired_cursors_fail_before_sql(change, monkeypatch):
    first = page(Boundary([row(1), row(2)]), limit=1)
    access = ACCESS
    filters = q.Filters()
    params = {"facet": "invoice", "limit": 1, "after": first["next_cursor"]}
    if change == "tenant":
        access = SimpleNamespace(organization_id=uuid4())
    if change == "facet":
        params["facet"] = "contract"
    if change == "document":
        filters = q.Filters(invoice_document_id=uuid4())
    if change == "supplier":
        filters = q.Filters(supplier="Other")
    if change == "search":
        params["search"] = "other"
    if change == "limit":
        params["limit"] = 2
    if change == "tamper":
        params["after"] = "x!"
    if change == "expired":
        monkeypatch.setattr(q.time, "time", lambda: 99999999999)
    session = Boundary()
    with pytest.raises(HTTPException) as e:
        f.facet_page(session, access, filters, f.FacetRequest(**params), KEY)
    assert e.value.status_code == 422 and session.statements == []


def test_changed_financial_data_requires_restart(monkeypatch):
    first = page(Boundary([row(1), row(2)]), limit=1)
    monkeypatch.setattr(q, "generation", lambda *_: [9, 4])
    session = Boundary()
    with pytest.raises(HTTPException) as e:
        page(session, limit=1, after=first["next_cursor"])
    assert e.value.status_code == 409 and e.value.detail["code"] == "FACETS_CHANGED"
    assert len(session.statements) == 1


def test_dynamic_cap_removes_only_invoice_source_before_guard_and_never_serializes_101(monkeypatch):
    session = Boundary(candidates=[SimpleNamespace(id=UUID(int=n)) for n in range(101)])

    def forbidden(*_):
        pytest.fail("Must refuse before serialization")

    monkeypatch.setattr(f.service, "serialize_evaluation", forbidden)
    with pytest.raises(HTTPException) as e:
        page(
            session,
            q.Filters(
                invoice_source_id=UUID(int=666), invoice_document_id=UUID(int=777), current=True
            ),
        )
    assert e.value.detail["code"] == "DYNAMIC_FILTER_LIMIT"
    assert UUID(int=666) not in compiled(session.statements[-1]).params.values()
    assert UUID(int=777) in compiled(session.statements[-1]).params.values()


def test_dynamic_currentness_filters_ids_before_invoice_distinct(monkeypatch):
    candidates = [SimpleNamespace(id=UUID(int=n)) for n in (1, 2)]
    monkeypatch.setattr(
        f.service,
        "serialize_evaluation",
        lambda _s, _a, r: {
            "stale": r.id.int == 1,
            "outcome": "NEEDS_REVIEW",
            "status": "needs_review",
            "potential": None,
        },
    )
    session = Boundary([row(2)], candidates)
    page(session, q.Filters(needs_review=True))
    assert [UUID(int=2)] in compiled(session.statements[-1]).params.values()


def test_openapi_advertises_invoice_with_old_types_and_endpoint_stays_authenticated(tmp_path):
    app = create_app(Settings(_env_file=None, environment="test", storage_root=tmp_path))
    schema = app.openapi()
    p = "/api/v1/organizations/{organization_id}/financial/exception-facets"
    params = {v["name"]: v for v in schema["paths"][p]["get"]["parameters"]}
    assert params["facet"]["schema"]["enum"] == ["supplier", "contract", "invoice"]
    assert params["limit"]["schema"]["maximum"] == 50
    with TestClient(app) as c:
        assert (
            c.get(
                f"/api/v1/organizations/{ORG}/financial/exception-facets?facet=invoice"
            ).status_code
            == 401
        )
