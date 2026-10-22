"""Ordinary product tests; no PostgreSQL/OIDC session qualification claim."""

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from acceptance.product_v11 import guard, preflight, scenario, source_material
from app.core.config import Settings
from app.financial.engine import evaluate
from app.main import create_app
from tests.financial_fixtures import packet


def test_synthetic_100_units_scenario_obeys_the_existing_engine():
    t, b = scenario()
    result = evaluate((t,), b, packet())
    assert result.expected == Decimal("5000")
    assert result.actual == Decimal("6000")
    assert result.potential == Decimal("1000") and result.currency == "USD"


def test_manual_fixture_contains_the_exact_typed_financial_conditions():
    import csv
    import io
    import json

    ids, originals, t, b, governing = source_material()
    decoded = {}
    for kind, raw in originals.items():
        rows = list(csv.reader(io.StringIO(raw.decode())))
        assert rows[0][0] == "SYNTHETIC_SOURCE_SECTION"
        assert len(raw) < 4096 and len(raw.decode()) < 10000
        decoded[kind] = {name: json.loads(value) for name, value in rows[1:]}
    assert decoded["contract"]["term"] == t.model_dump(mode="json")
    assert decoded["contract"]["packet"] == governing.model_dump(mode="json")
    assert decoded["invoice"]["billing_scope"] == b.model_dump(mode="json")
    assert decoded["invoice"]["association_basis"]["contract_document_id"] == str(ids["contract"])


def test_missing_acceptance_configuration_blocks_before_any_connection(monkeypatch):
    for name in [
        "PRODUCT_V11_ACCEPTANCE",
        "PRODUCT_SYNTHETIC_ACCOUNTS_ONLY",
        "FLA_DATABASE_URL",
        "OIDC_ISSUER_URL",
    ]:
        monkeypatch.delenv(name, raising=False)
    assert preflight()["status"] == "BLOCKED"
    assert preflight()["e2e"] == "NOT_EXECUTED"


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://test:secret@production.example/main",
        "sqlite:///test.db",
        "postgresql+psycopg://test:secret@localhost/financial_leakage",
    ],
)
def test_fixture_rejects_non_dedicated_or_remote_database(monkeypatch, url):
    for name, value in {
        "PRODUCT_V11_ACCEPTANCE": "1",
        "PRODUCT_SYNTHETIC_ACCOUNTS_ONLY": "1",
        "FLA_ENVIRONMENT": "test",
        "FLA_DATABASE_URL": url,
        "OIDC_ISSUER_URL": "http://127.0.0.1:9001",
        "PRODUCT_OWNER_SUBJECT": "synthetic-owner",
        "PRODUCT_ANALYST_SUBJECT": "synthetic-analyst",
    }.items():
        monkeypatch.setenv(name, value)
    assert guard()["status"] == "BLOCKED"
    assert "secret" not in str(guard())


def test_no_session_cannot_read_or_write_financial_records_without_database(tmp_path):
    app = create_app(Settings(_env_file=None, environment="test", storage_root=tmp_path))
    with TestClient(app) as client:
        base = f"/api/v1/organizations/{uuid4()}/financial"
        assert client.get(base + "/summary").status_code == 401
        assert (
            client.post(
                base + f"/evaluations/{uuid4()}/decision",
                json={"status": "confirmed", "reason": "synthetic", "expected_decision": None},
            ).status_code
            == 401
        )
