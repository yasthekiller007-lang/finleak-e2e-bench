"""Presentation contract tests with explicit in-memory snapshots; no database E2E."""

from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.financial import service
from app.financial.presentation import queue_context


def context_fixture():
    invoice, contract = uuid4(), uuid4()
    snapshot = {
        "billing_scope": {"supplier_party": "DEMO supplier", "contract_references": ["DEMO-2026"]},
        "inputs": [
            {
                "source_id": str(invoice),
                "kind": "association",
                "state": "approved",
                "payload": {"value": {"contract_source_id": str(contract)}},
            }
        ],
    }
    return invoice, contract, snapshot


def test_context_is_frozen_snapshot_data_without_mutation():
    invoice, contract, snapshot = context_fixture()
    before = deepcopy(snapshot)
    assert queue_context(snapshot, invoice) == {
        "supplier_party": "DEMO supplier",
        "contract_source_id": str(contract),
        "contract_references": ["DEMO-2026"],
    }
    assert before == snapshot


@pytest.mark.parametrize(
    "change", ["prepared", "revoked", "wrong_source", "invalid_id", "ambiguous"]
)
def test_context_does_not_guess_an_unapproved_or_ambiguous_contract(change):
    invoice, _, snapshot = context_fixture()
    record = snapshot["inputs"][0]
    if change in {"prepared", "revoked"}:
        record["state"] = change
    elif change == "wrong_source":
        record["source_id"] = str(uuid4())
    elif change == "invalid_id":
        record["payload"]["value"]["contract_source_id"] = "not-a-source-id"
    else:
        duplicate = deepcopy(record)
        duplicate["payload"]["value"]["contract_source_id"] = str(uuid4())
        snapshot["inputs"].append(duplicate)
    assert queue_context(snapshot, invoice)["contract_source_id"] is None


def test_absent_context_is_unknown_not_an_inferred_supplier():
    assert queue_context({}, uuid4()) == {
        "supplier_party": None,
        "contract_source_id": None,
        "contract_references": [],
    }


def test_actual_serializer_exposes_context_on_list_and_detail_without_changing_money(monkeypatch):
    invoice, contract, snapshot = context_fixture()
    monkeypatch.setattr(service, "latest_decision", lambda *_: None)
    monkeypatch.setattr(service, "is_stale", lambda *_: False)
    row = SimpleNamespace(
        id=uuid4(),
        invoice_source_id=invoice,
        scope_key="demo-line",
        outcome="POTENTIAL_OVERCHARGE",
        reason_code="SUPPORTED_DISCREPANCY",
        explanation="Synthetic fixture",
        currency="USD",
        expected=Decimal("5000"),
        actual=Decimal("6000"),
        discrepancy=Decimal("1000"),
        potential=Decimal("1000"),
        created_at=datetime(2026, 10, 19, tzinfo=UTC),
        snapshot=snapshot,
        fingerprint="f" * 64,
    )
    for detail in (False, True):
        result = service.serialize_evaluation(None, None, row, detail=detail)
        assert result["queue_context"]["contract_source_id"] == str(contract)
        assert (result["expected"], result["actual"], result["potential"]) == (
            "5000.000000",
            "6000.000000",
            "1000.000000",
        )
        assert ("snapshot" in result) == detail
