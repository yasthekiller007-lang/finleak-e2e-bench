from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError, StatementError

from app.core.config import Settings
from app.db.models import (
    Contract,
    ContractVersion,
    Document,
    Invoice,
    InvoiceLineItem,
    LeakageCase,
    LeakageEvidence,
    Organization,
    OrganizationMembership,
    User,
    leakage_case_documents,
)
from app.domain.types import DocumentType, VersionKind
from app.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
def tenants(db_session):
    data = {}
    for name in ("a", "b"):
        org = Organization(name=f"Tenant {name}")
        db_session.add(org)
        db_session.flush()
        document = Document(
            organization_id=org.id,
            original_filename="contract.pdf",
            mime_type="application/pdf",
            file_size=10,
            storage_key=f"{org.id}/{uuid4()}/source",
            sha256="a" * 64,
            document_type=DocumentType.CONTRACT,
        )
        contract = Contract(organization_id=org.id, title="Agreement", counterparty_name="Vendor")
        db_session.add_all([document, contract])
        db_session.flush()
        invoice = Invoice(
            organization_id=org.id,
            document_id=document.id,
            contract_id=contract.id,
            invoice_number="INV-1",
            supplier_name="Vendor",
            issued_on=date(2026, 1, 1),
            total_amount=Decimal("0.300001"),
            currency="USD",
        )
        db_session.add(invoice)
        db_session.flush()
        case = LeakageCase(
            organization_id=org.id,
            invoice_id=invoice.id,
            contract_id=contract.id,
            category="contract_to_invoice",
            potential_exposure=Decimal("0.100001"),
            currency="USD",
            explanation="Test fixture, not a detected anomaly",
        )
        db_session.add(case)
        db_session.flush()
        data[name] = {
            "org": org.id,
            "document": document.id,
            "contract": contract.id,
            "invoice": invoice.id,
            "case": case.id,
        }
    return data


def row_values(tenants, table):
    tenant = tenants["a"]
    common = {"id": uuid4(), "organization_id": tenant["org"]}
    if table is ContractVersion:
        return {
            **common,
            "contract_id": tenant["contract"],
            "document_id": tenant["document"],
            "version_number": 1,
            "kind": VersionKind.ORIGINAL,
            "effective_from": date(2026, 1, 1),
        }
    if table is Invoice:
        return {
            **common,
            "contract_id": tenant["contract"],
            "document_id": tenant["document"],
            "invoice_number": "INV-2",
            "supplier_name": "Vendor",
            "issued_on": date(2026, 1, 1),
            "total_amount": Decimal("10"),
            "currency": "USD",
        }
    if table is InvoiceLineItem:
        return {
            **common,
            "invoice_id": tenant["invoice"],
            "line_number": 1,
            "description": "Service",
            "quantity": Decimal("1"),
            "unit_amount": Decimal("10"),
            "line_amount": Decimal("10"),
            "currency": "USD",
        }
    if table is LeakageCase:
        return {
            **common,
            "contract_id": tenant["contract"],
            "invoice_id": tenant["invoice"],
            "category": "contract_to_invoice",
            "potential_exposure": Decimal("10"),
            "currency": "USD",
            "explanation": "Fixture",
        }
    if table is LeakageEvidence:
        return {
            **common,
            "case_id": tenant["case"],
            "document_id": tenant["document"],
            "page_number": 1,
            "currency": "USD",
        }
    if table is leakage_case_documents:
        return {
            "organization_id": tenant["org"],
            "case_id": tenant["case"],
            "document_id": tenant["document"],
        }
    raise AssertionError("Unknown fixture table")


@pytest.mark.parametrize(
    ("table", "field", "other_key"),
    [
        (ContractVersion, "contract_id", "contract"),
        (ContractVersion, "document_id", "document"),
        (Invoice, "contract_id", "contract"),
        (Invoice, "document_id", "document"),
        (InvoiceLineItem, "invoice_id", "invoice"),
        (LeakageCase, "contract_id", "contract"),
        (LeakageCase, "invoice_id", "invoice"),
        (LeakageEvidence, "case_id", "case"),
        (LeakageEvidence, "document_id", "document"),
        (leakage_case_documents, "case_id", "case"),
        (leakage_case_documents, "document_id", "document"),
    ],
)
def test_postgres_rejects_cross_tenant_links(db_session, tenants, table, field, other_key):
    values = row_values(tenants, table)
    values[field] = tenants["b"][other_key]
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(insert(table).values(**values))


@pytest.mark.parametrize("table", [InvoiceLineItem, LeakageCase, LeakageEvidence])
def test_related_money_cannot_change_currency(db_session, tenants, table):
    values = row_values(tenants, table)
    values["currency"] = "EUR"
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(insert(table).values(**values))


def test_valid_financial_graph_decimal_roundtrip_and_utc(db_session, tenants):
    for table in (ContractVersion, InvoiceLineItem, LeakageEvidence, leakage_case_documents):
        db_session.execute(insert(table).values(**row_values(tenants, table)))
    db_session.expire_all()
    invoice = db_session.get(Invoice, tenants["a"]["invoice"])
    assert invoice.total_amount == Decimal("0.300001")
    assert isinstance(invoice.total_amount, Decimal)
    assert invoice.created_at.utcoffset().total_seconds() == 0
    assert invoice.updated_at.utcoffset().total_seconds() == 0
    assert (
        db_session.scalar(
            select(LeakageEvidence).where(LeakageEvidence.organization_id == tenants["a"]["org"])
        ).page_number
        == 1
    )


@pytest.mark.parametrize(
    ("table", "changes"),
    [
        (ContractVersion, {"effective_to": date(2025, 1, 1)}),
        (ContractVersion, {"version_number": 0}),
        (ContractVersion, {"agreed_amount": Decimal("10"), "currency": None}),
        (InvoiceLineItem, {"quantity": Decimal("0")}),
        (LeakageCase, {"confidence_score": Decimal("1.0001")}),
        (LeakageCase, {"potential_exposure": Decimal("-1")}),
        (LeakageEvidence, {"page_number": 0}),
    ],
)
def test_invalid_financial_metadata_is_rejected(db_session, tenants, table, changes):
    values = row_values(tenants, table) | changes
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(insert(table).values(**values))


@pytest.mark.parametrize("value", [0.1, Decimal("0.0000001"), Decimal("100000000000000")])
def test_orm_rejects_float_scale_rounding_and_overflow(db_session, tenants, value):
    values = row_values(tenants, Invoice) | {"total_amount": value}
    with pytest.raises(StatementError), db_session.begin_nested():
        db_session.execute(insert(Invoice).values(**values))


def test_contract_amendments_have_distinct_effective_dates(db_session, tenants):
    original = row_values(tenants, ContractVersion)
    amendment = original | {
        "id": uuid4(),
        "version_number": 2,
        "kind": VersionKind.AMENDMENT,
        "effective_from": date(2026, 3, 1),
    }
    db_session.execute(insert(ContractVersion).values(**original))
    db_session.execute(insert(ContractVersion).values(**amendment))
    versions = db_session.scalars(
        select(ContractVersion)
        .where(ContractVersion.organization_id == tenants["a"]["org"])
        .order_by(ContractVersion.version_number)
    ).all()
    assert [version.kind for version in versions] == [VersionKind.ORIGINAL, VersionKind.AMENDMENT]
    assert versions[1].effective_from == date(2026, 3, 1)


def test_membership_is_unique_within_organization(db_session, tenants):
    user = User(email=f"{uuid4()}@example.test", display_name="Test user")
    db_session.add(user)
    db_session.flush()
    member = {"organization_id": tenants["a"]["org"], "user_id": user.id}
    db_session.execute(insert(OrganizationMembership).values(id=uuid4(), **member))
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(insert(OrganizationMembership).values(id=uuid4(), **member))


def test_readiness_checks_migrated_postgres(db_session):
    import os

    settings = Settings(_env_file=None, database_url=os.environ["TEST_DATABASE_URL"])
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/health/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"
