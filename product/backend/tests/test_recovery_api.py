from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app.financial.models import FinancialAudit
from app.recovery.models import RecoveryCase, RecoveryRecord
from tests.recovery_fixtures import (
    act,
    approve,
    current,
    inspect,
    instrument,
    ok,
    post,
    prepare,
    ready,
    realization,
    report_body,
    root,
    setup,
)
from tests.recovery_fixtures import (
    db_session as db_session,
)
from tests.recovery_fixtures import (
    recovery_engine as recovery_engine,
)
from tests.test_documents import api as api
from tests.test_documents import headers
from tests.test_financial_api import set_role

pytestmark = pytest.mark.integration


def test_full_cash_no_claim_no_automatic_closure_and_report_audit(api):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f)
    receipt = act(api, f, realization(api, f, p, r, i, v))
    view = current(api, f["case"])
    assert view["realized"] == "50000.000000" and view["ratio"] == "100.00"
    assert view["claimed"] is None and view["acknowledged"] is None
    assert view["lifecycle"] == "OPEN" and view["unrealized"] == "0.000000"
    inspect(api, f)
    result = ok(post(api, "/report", report_body()))
    assert Decimal(result["realized_flow"]) == Decimal("50000")
    assert result["ratio"] == "100.00" and result["context"]["record_ids"]
    actions = api["session"].scalars(select(FinancialAudit.action)).all()
    assert actions.count("recovery.realization") == 1
    assert api["session"].scalar(select(func.count()).select_from(RecoveryCase)) == 1
    assert receipt["pins"]["integrity"] == "VERIFIED"


def test_credit_issue_application_redemption_and_budget(api):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "20000", kind="CREDIT")
    view = current(api, f["case"])
    assert Decimal(view["realized"]) == 0 and Decimal(view["pending_credit"]) == 20000
    act(
        api,
        f,
        realization(
            api,
            f,
            p,
            r,
            i,
            v,
            "12000",
            method="APPLIED_CREDIT",
            net_cash=None,
            application_reference="AP-1",
        ),
    )
    act(api, f, realization(api, f, p, r, i, v, "8000"))
    view = current(api, f["case"])
    assert Decimal(view["realized"]) == 20000 and Decimal(view["pending_credit"]) == 0
    proposed = prepare(api, f, realization(api, f, p, r, i, v, "1"))
    assert approve(api, f, proposed).status_code == 409
    assert Decimal(current(api, f["case"])["realized"]) == 20000


@pytest.mark.parametrize(
    "role,status", [("owner", 200), ("admin", 200), ("analyst", 403), ("viewer", 403)]
)
def test_role_final_authority_and_viewer_read(api, role, status):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "15000")
    proposal = prepare(api, f, realization(api, f, p, r, i, v, "15000"))
    set_role(api, role)
    assert approve(api, f, proposal).status_code == status
    assert (
        api["client"].get(root(api) + f"/cases/{f['case']['id']}", headers=headers(api)).status_code
        == 200
    )


def test_missing_confirmation_and_proof_allow_investigation_only(api):
    f = setup(api, confirm=False, complete=False)
    view = current(api, f["case"])
    assert view["readiness"] == "INVESTIGATION" and view["validated"] is None
    assert view["pursuit"] is None and Decimal(view["realized"]) == 0
    assert (
        ok(post(api, "/cases", {"evaluation_id": f["evaluation"]["id"]}))["id"] == f["case"]["id"]
    )


def test_source_tamper_rollback_and_cross_tenant_no_metadata_leak(api):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "10000")
    proposal = prepare(api, f, realization(api, f, p, r, i, v, "10000"))
    from app.db.models import Document

    doc = api["session"].get(Document, f["doc"])
    path = api["app"].state.storage.root / doc.storage_key
    path.write_bytes(b"source corrupted")
    assert approve(api, f, proposal).status_code == 409
    assert Decimal(current(api, f["case"])["realized"]) == 0
    response = api["client"].get(
        root(api, "b") + f"/cases/{f['case']['id']}", headers=headers(api, "b")
    )
    assert response.status_code == 404 and f["doc"] not in response.text


def test_correction_closed_preserves_cash_and_immutable_original(api):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "10000")
    original = act(api, f, realization(api, f, p, r, i, v, "10000"))
    state = current(api, f["case"])
    ok(
        post(
            api,
            f"/cases/{f['case']['id']}/lifecycle",
            {
                "state": "CLOSED",
                "closure_reason": "MANAGEMENT",
                "expected_head": state["head_id"],
                "reason": "Commercial strategy only",
            },
        )
    )
    act(
        api,
        f,
        {
            "kind": "reversal",
            "original_id": original["id"],
            "amount": "3000",
            "reversal_type": "DE_RECOGNITION",
            "economic": {"precision": "DATE", "day": "2026-10-02"},
            "event_reference": "correction-1",
            "discharge": "Independent corrected principal attribution",
        },
    )
    view = current(api, f["case"])
    assert Decimal(view["realized"]) == 7000 and Decimal(view["net_cash"]) == 10000
    with pytest.raises(DBAPIError), api["session"].begin_nested():
        api["session"].execute(
            text("UPDATE recovery_records SET amount=0 WHERE id=:id"), {"id": original["id"]}
        )
    assert (
        api["session"].scalar(
            select(func.count())
            .select_from(RecoveryRecord)
            .where(RecoveryRecord.kind == "reversal")
        )
        == 1
    )


def test_strict_request_boundary_and_unknown_fields(api):
    f = setup(api)
    response = post(
        api, "/cases", {"evaluation_id": f["evaluation"]["id"], "recovered_amount": "9999"}
    )
    assert response.status_code == 422
    response = api["client"].post(
        root(api) + "/cases",
        content=b" " * 1048577,
        headers={
            **headers(api),
            "Content-Type": "application/json",
            "Idempotency-Key": str(uuid4()),
        },
    )
    assert response.status_code == 413
