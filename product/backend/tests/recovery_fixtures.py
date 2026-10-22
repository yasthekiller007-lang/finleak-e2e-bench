"""Independent protected financial sources and manual recovery evidence fixtures."""

import os
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.db.base import Base
from app.proof.canonical import leaves
from app.recovery.schema import Limits, Proposal
from tests.financial_fixtures import bill, packet, term
from tests.test_documents import headers, upload
from tests.test_financial_api import body, create, evaluate, review, set_role
from tests.test_financial_api import root as financial_root
from tests.test_proof_api import issued


def root(api, org="a"):
    return f"/api/v1/organizations/{api['orgs'][org]}/recovery"


def post(api, path, data, key=None, subject="a", org="a"):
    return api["client"].post(
        root(api, org) + path,
        json=data,
        headers={**headers(api, subject), "Idempotency-Key": str(key or uuid4())},
    )


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def current(api, case):
    return ok(api["client"].get(root(api) + f"/cases/{case['id']}", headers=headers(api)))


def setup(api, potential="50000", confirm=True, complete=True):
    api["app"].state.settings.recovery_limits = Limits(actor_operations_per_minute=1000)
    set_role(api, "owner")
    actual = Decimal(potential) + Decimal("1000")
    contract, cdoc = create(
        api,
        "contract",
        f"scope,rate,supplier,customer\nSKU-A,10,supplier-A,buyer-A\nreview-source,{uuid4()}\n".encode(),
    )
    invoice, idoc = create(
        api,
        "invoice",
        f"scope,quantity,unit,amount,currency,tax\nSKU-A,100,unit,{actual},USD,exclusive\ninvoice-reference,{uuid4()}\n".encode(),
    )
    values = [
        (contract, body("term", term(), cdoc)),
        (
            contract,
            body(
                "packet", packet(documents=({"document_id": UUID(cdoc), "role": "master"},)), cdoc
            ),
        ),
        (
            invoice,
            body(
                "billing_scope",
                bill(
                    posted_amount=str(actual),
                    billed_gross=str(actual),
                    billed_rate=str(actual / 100),
                ),
                idoc,
            ),
        ),
        (
            invoice,
            body(
                "association",
                {
                    "contract_source_id": contract,
                    "method": "manual",
                    "identifier": None,
                    "rationale": "Exact obligation",
                },
                idoc,
            ),
        ),
    ]
    for identity, value in values:
        response = review(api, identity, value)
        assert response.status_code == 201, response.text
    evaluation = ok(evaluate(api, invoice))
    assert Decimal(evaluation["potential"]) == Decimal(potential)
    package = issued(api, evaluation) if complete else None
    decision = None
    if confirm:
        response = api["client"].post(
            financial_root(api) + f"/evaluations/{evaluation['id']}/decision",
            headers=headers(api),
            json={
                "status": "confirmed",
                "reason": "Independent approved calculation confirmed",
                "expected_decision": None,
            },
        )
        assert response.status_code == 201, response.text
        decision = response.json()
    case = ok(post(api, "/cases", {"evaluation_id": evaluation["id"]}))
    bank = upload(
        api,
        filename="synthetic-bank.csv",
        content=f"reference,principal,beneficiary,status\n{uuid4()},50000,buyer-A,settled\n".encode(),
    )
    assert bank.status_code == 201, bank.text
    return {
        "case": case,
        "evaluation": evaluation,
        "proof": package,
        "decision": decision,
        "doc": bank.json()["id"],
        "invoice": invoice,
        "idoc": idoc,
        "contract": contract,
        "cdoc": cdoc,
    }


def prepare(api, fixture, value):
    state = current(api, fixture["case"])
    normalized = Proposal.model_validate(
        {
            "value": value,
            "expected_head": state["head_id"],
            "evidence": [],
            "reason": "Synthetic exact economic source review",
        }
    ).value.model_dump(mode="json")
    material = {p: str(v) for p, v in leaves({"value": normalized}).items() if v is not None}
    evidence = {
        "document_id": fixture["doc"],
        "locator": "CSV transaction row 2",
        "quotation": "Synthetic independently reviewed economic transaction",
        "supports": list(material),
        "raw_fields": material,
        "reviewed_fields": material,
    }
    return ok(
        post(
            api,
            f"/cases/{fixture['case']['id']}/proposals",
            {
                "value": normalized,
                "expected_head": state["head_id"],
                "reason": "Explicit source-backed proposed meaning",
                "evidence": [evidence],
            },
        )
    )


def approve(api, fixture, proposal, subject="a", key=None):
    state = current(api, fixture["case"])
    return post(
        api,
        f"/proposals/{proposal['id']}/decision",
        {
            "expected_head": state["head_id"],
            "reason": "Reviewed exact protected source and economic authority",
            "decision": "APPROVE",
        },
        subject=subject,
        key=key,
    )


def act(api, fixture, value):
    return ok(approve(api, fixture, prepare(api, fixture, value)))


def party(api, fixture, **changes):
    value = {
        "kind": "party",
        "supplier": "supplier-A",
        "customer": "buyer-A",
        "payer": "supplier-A",
        "payee": "buyer-A",
        "beneficiary": "buyer-A",
        "valid_from": "2026-01-01",
        "relationship": "DIRECT",
        "discharge": "Vendor principal discharged to invoice customer",
    }
    return act(api, fixture, value | changes)


def ready(api, fixture, pursuit=None, **changes):
    p = party(api, fixture)
    value = {
        "kind": "readiness",
        "proof_id": fixture["proof"]["id"],
        "decision_id": fixture["decision"]["id"],
        "party_id": p["id"],
        "pursuit": pursuit or fixture["evaluation"]["potential"],
        "quantum": "0.01",
        "currency": "USD",
        "tax_basis": "EXCLUSIVE",
        "scope": "SKU-A",
        "reconciliation": "COMPLETE",
    }
    return p, act(api, fixture, value | changes)


def instrument(api, fixture, amount="50000", kind="CASH", reference=None, **changes):
    identity = ok(
        post(
            api,
            "/instruments",
            {
                "kind": kind,
                "namespace": "bank/fixture" if kind == "CASH" else "supplier/fixture",
                "issuer": "supplier-A",
                "reference": reference or str(uuid4()),
                "currency": changes.get("currency", "USD"),
            },
        )
    )
    value = {
        "kind": "instrument",
        "instrument_id": identity["id"],
        "principal": amount,
        "gross": amount,
        "tax": "0",
        "other": "0",
        "tax_basis": "EXCLUSIVE",
        "reconciliation": "COMPLETE",
        "economic": {"precision": "DATE", "day": "2026-10-01"},
        "payer": "supplier-A",
        "payee": "buyer-A",
        "beneficiary": "buyer-A",
        "scope": "SKU-A",
        "related_cases": [fixture["case"]["id"]],
        "origin": "POST_FINDING_REMEDY",
        "status": "ISSUED" if kind == "CREDIT" else "SETTLED" if kind == "CASH" else "POSTED",
    }
    changes.pop("currency", None)
    return identity, act(api, fixture, value | changes)


def realization(api, fixture, p, r, identity, reviewed, amount="50000", **changes):
    value = {
        "kind": "realization",
        "instrument_id": identity["id"],
        "instrument_review_id": reviewed["id"],
        "party_id": p["id"],
        "readiness_id": r["id"],
        "method": "CASH",
        "economic": {"precision": "DATE", "day": "2026-10-01"},
        "amount": amount,
        "principal": amount,
        "gross": amount,
        "tax": "0",
        "fees": "0",
        "withholding": "0",
        "net_cash": amount,
        "other": "0",
        "tax_basis": "EXCLUSIVE",
        "reconciliation": "COMPLETE",
        "currency": "USD",
        "quantum": "0.01",
        "event_reference": str(uuid4()),
        "payer": "supplier-A",
        "payee": "buyer-A",
        "beneficiary": "buyer-A",
        "scope": "SKU-A",
        "completed": True,
        "discharge": "Actual settled compatible principal discharged",
    }
    return value | changes


def inspect(api, fixture):
    state = current(api, fixture["case"])
    return ok(
        post(
            api,
            f"/cases/{fixture['case']['id']}/inspect",
            {"expected_head": state["head_id"], "reason": "Explicit current authority observation"},
        )
    )


def report_body(**changes):
    return {
        "known_at": datetime.now(UTC).isoformat(),
        "start": {"precision": "DATE", "day": "2026-01-01"},
        "end": {"precision": "DATE", "day": "2027-01-01"},
        "currency": "USD",
        "customer": "buyer-A",
        "tax_basis": "EXCLUSIVE",
    } | changes


@pytest.fixture
def recovery_engine():
    """Real commits and independent connections, never savepoint-as-commit."""
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set isolated TEST_DATABASE_URL")
    admin = create_engine(url)
    schema = "recovery_test_" + uuid4().hex
    with admin.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA {schema}"))
        connection.execute(text(f"SET LOCAL search_path TO {schema}"))
        with Operations.context(
            MigrationContext.configure(connection, opts={"target_metadata": Base.metadata})
        ):
            from tests.test_phase2_migration import migration

            for name in [
                "0001_initial_tenant_scoped_financial_schema.py",
                "0002_identity_membership_uploads.py",
                "0003_document_intelligence.py",
                "0004_reviewed_financial_engine.py",
                "0005_leakage_proof_engine.py",
                "0006_recovery_ledger.py",
                "0007_pilot_access.py",
                "0008_pilot_intake.py",
                "0009_source_quarantine.py",
            ]:
                migration(name).upgrade()
    engine = create_engine(
        url, connect_args={"options": f"-c search_path={schema} -c timezone=UTC"}
    )
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        admin.dispose()


@pytest.fixture
def db_session(recovery_engine):
    with Session(recovery_engine) as session:
        yield session
