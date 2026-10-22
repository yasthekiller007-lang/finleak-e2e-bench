"""RW-01–RW-56: independent economic references through protected real APIs.

Amounts and expected outcomes come from the approved examples, never from the
implementation calculator. Every database test uses real commits in an isolated
PostgreSQL schema. Race examples additionally use independent connections.
"""

from datetime import UTC, datetime
from decimal import Decimal as D
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.db.models import Document
from app.financial.models import FinancialRevision
from tests.financial_fixtures import term
from tests.recovery_fixtures import (
    act,
    approve,
    current,
    inspect,
    instrument,
    ok,
    party,
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
from tests.test_financial_api import body, evaluate, review, set_role
from tests.test_financial_api import root as financial_root
from tests.test_proof_api import issued
from tests.test_proof_api import post as proof_post

pytestmark = pytest.mark.integration
DAY = {"precision": "DATE", "day": "2026-10-01"}


def cash(api, f, amount="10000", **changes):
    p, r = ready(api, f)
    i, v = instrument(api, f, amount)
    return p, r, i, v, act(api, f, realization(api, f, p, r, i, v, amount, **changes))


def close(api, f, state="CLOSED", reason="MANAGEMENT"):
    return ok(
        post(
            api,
            f"/cases/{f['case']['id']}/lifecycle",
            {
                "state": state,
                "closure_reason": reason if state == "CLOSED" else None,
                "expected_head": current(api, f["case"])["head_id"],
                "reason": "Explicit strategy change",
            },
        )
    )


def response(api, f, p, **changes):
    return act(
        api,
        f,
        dict(
            kind="vendor",
            state="ACKNOWLEDGED",
            acknowledged="50000",
            disputed=None,
            agreed_gross=None,
            currency="USD",
            tax_basis="EXCLUSIVE",
            party_id=p["id"],
            economic=DAY,
            scope="SKU-A",
            conditional=False,
        )
        | changes,
    )


def claim(api, f, amount="50000", state="RECORDED_ACTION"):
    return act(
        api,
        f,
        dict(
            kind="claim",
            state=state,
            principal=amount,
            currency="USD",
            tax_basis="EXCLUSIVE",
            economic=DAY,
            scope="SKU-A",
            action_reference=str(uuid4()),
        ),
    )


def decision(api, f, status):
    result = api["client"].post(
        financial_root(api) + f"/evaluations/{f['evaluation']['id']}/decision",
        headers=headers(api),
        json={
            "status": status,
            "reason": "Independent financial decision",
            "expected_decision": f["decision"]["id"] if f["decision"] else None,
        },
    )
    assert result.status_code == 201, result.text
    return result.json()


def revise(api, f, kind="term", value=None, state="approved"):
    source = f["contract"] if kind == "term" else f["invoice"]
    doc = f["cdoc"] if kind == "term" else f["idoc"]
    old = api["session"].scalar(
        select(FinancialRevision)
        .where(FinancialRevision.source_id == UUID(source), FinancialRevision.kind == kind)
        .order_by(FinancialRevision.number.desc())
    )
    result = review(api, source, body(kind, value or term(rate="60"), doc, str(old.id), state))
    assert result.status_code == 201, result.text
    return result.json()


def negative(api, f, original, amount="3000", **changes):
    return act(
        api,
        f,
        dict(
            kind="reversal",
            original_id=original["id"],
            amount=amount,
            reversal_type="DE_RECOGNITION",
            economic={"precision": "DATE", "day": "2026-10-02"},
            event_reference=str(uuid4()),
            discharge="Exact evidenced original principal correction",
        )
        | changes,
    )


def view(api, f):
    return current(api, f["case"])


def test_RW01_full_cash(api):
    f = setup(api)
    cash(api, f, "50000")
    v = view(api, f)
    assert D(v["realized"]) == D("50000") and D(v["unrealized"]) == 0
    assert v["claimed"] is None and v["acknowledged"] is None and v["lifecycle"] == "OPEN"


def test_RW02_partial_cash(api):
    f = setup(api)
    cash(api, f, "30000")
    v = view(api, f)
    assert D(v["realized"]) == 30000 and D(v["unrealized"]) == 20000
    assert v["ratio"] == "60.00" and v["disputed"] is None


def test_RW03_credit_issue(api):
    f = setup(api)
    ready(api, f)
    instrument(api, f, "20000", kind="CREDIT")
    v = view(api, f)
    assert D(v["pending_credit"]) == 20000 and D(v["realized"]) == 0 and v["net_cash"] is None


def test_RW04_credit_applied(api):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "20000", kind="CREDIT")
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
            "20000",
            method="APPLIED_CREDIT",
            net_cash=None,
            application_reference="AP-actual",
        ),
    )
    v = view(api, f)
    assert D(v["realized"]) == 20000 and D(v["pending_credit"]) == 0 and v["net_cash"] is None


def test_RW05_credit_reversal_and_unused_cancellation(api):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "20000", kind="CREDIT")
    a = act(
        api,
        f,
        realization(
            api,
            f,
            p,
            r,
            i,
            v,
            "20000",
            method="APPLIED_CREDIT",
            net_cash=None,
            application_reference="AP-actual",
        ),
    )
    negative(api, f, a, "5000", reversal_type="ECONOMIC_RETURN")
    v = view(api, f)
    assert D(v["realized"]) == 15000 and D(v["unrealized"]) == 35000
    j, _ = instrument(api, f, "20000", kind="CREDIT")
    act(
        api,
        f,
        dict(
            kind="credit_state",
            instrument_id=j["id"],
            state="CANCELLED",
            amount="20000",
            economic=DAY,
            reconciliation="COMPLETE",
        ),
    )
    assert D(view(api, f)["realized"]) == 15000 and D(view(api, f)["pending_credit"]) == 0


def test_RW06_offset_later_invoice(api):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "20000", kind="CREDIT")
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
            application_reference="LATER-PAYABLE-1",
        ),
    )
    v = view(api, f)
    assert (
        D(v["realized"]) == 12000 and D(v["pending_credit"]) == 8000 and D(v["unrealized"]) == 38000
    )


def test_RW07_unpaid_replacement_liability(api):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "50000", kind="LIABILITY")
    proposal = realization(
        api,
        f,
        p,
        r,
        i,
        v,
        "50000",
        method="LIABILITY_REDUCTION",
        net_cash=None,
        unpaid_original=True,
        liability_before="120000",
        liability_after="70000",
    )
    act(api, f, proposal)
    assert D(view(api, f)["realized"]) == 50000 and view(api, f)["net_cash"] is None
    assert D(f["evaluation"]["potential"]) == 50000


def test_RW08_settlement_separate_from_performance(api):
    f = setup(api, "74199.90")
    p, r = ready(api, f)
    claim(api, f, "74199.90")
    response(api, f, p, state="PARTLY_DISPUTED", acknowledged="50000", disputed="24199.90")
    i, v = instrument(api, f, "30000")
    act(api, f, realization(api, f, p, r, i, v, "30000"))
    j, w = instrument(api, f, "20000", kind="CREDIT")
    assert D(view(api, f)["unrealized"]) == D("44199.90")
    act(
        api,
        f,
        realization(
            api,
            f,
            p,
            r,
            j,
            w,
            "20000",
            method="APPLIED_CREDIT",
            net_cash=None,
            application_reference="AP-actual",
        ),
    )
    v = view(api, f)
    assert D(v["realized"]) == 50000 and D(v["unrealized"]) == D("24199.90")
    assert D(v["acknowledged"]) == 50000 and D(v["disputed"]) == D("24199.90")


def test_RW09_acknowledgment_is_not_cash(api):
    f = setup(api)
    p, _ = ready(api, f)
    response(api, f, p)
    v = view(api, f)
    assert D(v["acknowledged"]) == 50000 and D(v["realized"]) == 0 and v["net_cash"] is None


def test_RW10_dispute_is_not_false_positive(api):
    f = setup(api)
    p, _ = ready(api, f)
    claim(api, f)
    response(api, f, p, state="DISPUTED", acknowledged=None, disputed="50000")
    v = view(api, f)
    assert D(v["disputed"]) == 50000 and v["acknowledged"] is None
    assert D(v["realized"]) == 0 and v["finding_decision"] == "confirmed"


def test_RW11_confirmation_withdrawal(api):
    f = setup(api)
    ready(api, f)
    claim(api, f)
    decision(api, f, "needs_review")
    v = view(api, f)
    assert v["validated"] is None and v["readiness"] == "BLOCKED" and D(v["claimed"]) == 50000


def test_RW12_dismissal_preserves_receipt(api):
    f = setup(api)
    cash(api, f)
    decision(api, f, "false_positive")
    v = view(api, f)
    assert D(v["realized"]) == 10000 and D(v["net_cash"]) == 10000
    assert v["category"] == "INVALIDATED_BASIS" and v["ratio"] is None
    assert post(api, "/cases", {"evaluation_id": f["evaluation"]["id"]}).status_code == 409


def test_RW13_stale_basis(api):
    f = setup(api)
    p, r, i, v, _ = cash(api, f)
    revise(api, f)
    state = view(api, f)
    assert (
        state["currentness"] == "STALE" and D(state["realized"]) == 10000 and state["ratio"] is None
    )
    assert approve(api, f, prepare(api, f, realization(api, f, p, r, i, v, "1"))).status_code == 409


def successor(api, f):
    revise(api, f)
    e = ok(evaluate(api, f["invoice"]))
    package = issued(api, e)
    c = ok(post(api, "/cases", {"evaluation_id": e["id"]}))
    d = decision(api, {"evaluation": e, "decision": None}, "confirmed")
    link = proof_post(
        api,
        f"/packages/{f['proof']['id']}/successor",
        {"successor_id": package["id"], "reason": "Exact authorized same-scope successor"},
    )
    assert link.status_code == 200, link.text
    return dict(f, evaluation=e, proof=package, decision=d, case=c), link.json()


def test_RW14_explicit_unused_successor(api):
    f = setup(api)
    ready(api, f)
    new, link = successor(api, f)
    act(
        api,
        f,
        dict(
            kind="retire",
            successor_case_id=new["case"]["id"],
            proof_successor_id=link["successor_relation_id"],
        ),
    )
    ready(api, new)
    assert D(view(api, new)["pursuit"]) == 45000 and view(api, f)["readiness"] == "BLOCKED"


def test_RW15_partial_commercial_closure(api):
    f = setup(api)
    cash(api, f, "30000")
    close(api, f, reason="PARTIAL_SETTLEMENT")
    v = view(api, f)
    assert D(v["unrealized"]) == 20000 and D(v["realized"]) == 30000 and v["lifecycle"] == "CLOSED"


def test_RW16_distinct_refunds(api):
    f = setup(api)
    p, r, _, _, _ = cash(api, f, "20000")
    i, v = instrument(api, f, "15000")
    act(api, f, realization(api, f, p, r, i, v, "15000"))
    v = view(api, f)
    assert D(v["realized"]) == 35000 and D(v["unrealized"]) == 15000 and D(v["net_cash"]) == 35000


def test_RW17_one_root_application_and_cash(api):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "20000", kind="CREDIT")
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
    s = view(api, f)
    assert D(s["realized"]) == 20000 and D(s["net_cash"]) == 8000 and D(s["pending_credit"]) == 0
    assert approve(api, f, prepare(api, f, realization(api, f, p, r, i, v, "1"))).status_code == 409


def note(api, f, text):
    return ok(
        post(
            api,
            f"/cases/{f['case']['id']}/notes",
            {
                "text": text,
                "reason": "Nonfinancial reviewed observation",
                "expected_head": view(api, f)["head_id"],
            },
        )
    )


def test_RW18_future_price_correction_not_money(api):
    f = setup(api)
    cash(api, f)
    note(api, f, "Future price correction, not realized savings")
    assert D(view(api, f)["realized"]) == 10000 and D(view(api, f)["potential"]) == 50000


def test_RW19_later_invoice_observation(api):
    f = setup(api)
    ready(api, f)
    note(api, f, "Reviewed later invoice correctly billed; no counterfactual authority")
    assert D(view(api, f)["realized"]) == 0 and D(view(api, f)["potential"]) == 50000


def test_RW20_forecast_deferred(api):
    f = setup(api)
    ready(api, f)
    assert (
        post(
            api,
            f"/cases/{f['case']['id']}/proposals",
            {
                "value": {"kind": "forecast", "amount": "10000"},
                "evidence": [],
                "expected_head": view(api, f)["head_id"],
                "reason": "Unsupported",
            },
        ).status_code
        == 422
    )
    assert D(view(api, f)["realized"]) == 0


def test_RW21_annualization_deferred(api):
    f = setup(api)
    note(api, f, "Scenario 5000 × 12 = 60000, unapproved monetary forecast")
    assert D(view(api, f)["realized"]) == 0 and "annualized" not in view(api, f)


def nonpositive(api, f, rate=None, state="approved"):
    revise(api, f, value=term(rate=rate or "10"), state=state)
    e = ok(evaluate(api, f["invoice"]))
    assert e["potential"] is None
    assert post(api, "/cases", {"evaluation_id": e["id"]}).status_code == 409
    return e


def test_RW22_undercharge_no_case(api):
    f = setup(api)
    e = nonpositive(api, f, rate="600")
    assert e["outcome"] == "UNDERCHARGE"


def test_RW23_no_overcharge_no_case(api):
    f = setup(api)
    e = nonpositive(api, f, rate="510")
    assert e["outcome"] == "NO_OVERCHARGE"


def test_RW24_blocked_assessment_no_case(api):
    f = setup(api)
    e = nonpositive(api, f, state="revoked")
    assert e["outcome"] == "NEEDS_REVIEW"


def test_RW25_incomplete_proof_no_ready(api):
    f = setup(api, complete=False)
    doc = api["session"].get(Document, UUID(f["cdoc"]))
    path = api["app"].state.storage.root / doc.storage_key
    original = path.read_bytes()
    path.unlink()
    f["proof"] = issued(api, f["evaluation"])
    path.write_bytes(original)
    assert f["proof"]["issued_completeness"] == "INCOMPLETE"
    p = party(api, f)
    proposed = prepare(
        api,
        f,
        dict(
            kind="readiness",
            proof_id=f["proof"]["id"],
            decision_id=f["decision"]["id"],
            party_id=p["id"],
            pursuit="50000",
            quantum="0.01",
            currency="USD",
            tax_basis="EXCLUSIVE",
            scope="SKU-A",
            reconciliation="COMPLETE",
        ),
    )
    assert approve(api, f, proposed).status_code == 409 and view(api, f)["pursuit"] is None


def test_RW26_complete_unconfirmed_not_validated(api):
    f = setup(api, confirm=False)
    assert f["proof"]["issued_completeness"] == "COMPLETE"
    assert view(api, f)["validated"] is None and view(api, f)["pursuit"] is None


def test_RW27_source_free_claim_is_not_authority(api):
    f = setup(api)
    ready(api, f)
    value = dict(
        kind="claim",
        state="RECORDED_ACTION",
        principal="50000",
        currency="USD",
        tax_basis="EXCLUSIVE",
        economic=DAY,
        scope="SKU-A",
        action_reference="UNSUPPORTED",
    )
    proposed = ok(
        post(
            api,
            f"/cases/{f['case']['id']}/proposals",
            {
                "value": value,
                "evidence": [],
                "reason": "Typed assertion only",
                "expected_head": view(api, f)["head_id"],
            },
        )
    )
    assert approve(api, f, proposed).status_code == 409 and view(api, f)["claimed"] is None


def test_RW28_foreign_currency_no_fx(api):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "10000", currency="EUR")
    assert (
        approve(
            api, f, prepare(api, f, realization(api, f, p, r, i, v, "10000", currency="EUR"))
        ).status_code
        == 409
    )
    assert D(view(api, f)["realized"]) == 0 and view(api, f)["ratio"] is None


def test_RW29_explicit_bundle_allocation_deferred(api):
    f = setup(api)
    p, r = ready(api, f)
    g = setup(api)
    i, v = instrument(
        api,
        f,
        "50000",
        kind="SETTLEMENT",
        related_cases=[f["case"]["id"], g["case"]["id"]],
        status="AGREED",
    )
    assert (
        approve(api, f, prepare(api, f, realization(api, f, p, r, i, v, "25000"))).status_code
        == 409
    )
    assert D(view(api, f)["realized"]) == 0


def test_RW30_ambiguous_bundle_no_cap_first(api):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(
        api,
        f,
        None,
        kind="SETTLEMENT",
        gross="60000",
        tax=None,
        other=None,
        reconciliation="UNRESOLVED",
        status="UNRESOLVED",
    )
    assert (
        approve(api, f, prepare(api, f, realization(api, f, p, r, i, v, "50000"))).status_code
        == 409
    )
    assert view(api, f)["unrealized"] is None and view(api, f)["ratio"] is None


def test_RW31_reversal_closed(api):
    f = setup(api)
    *_, a = cash(api, f, "30000")
    close(api, f)
    negative(api, f, a, "5000", reversal_type="ECONOMIC_RETURN", cash_return="5000")
    assert D(view(api, f)["realized"]) == 25000 and view(api, f)["lifecycle"] == "CLOSED"


def test_RW32_reopen_same_case_requires_fresh_ready(api):
    f = setup(api)
    p, r, i, v, _ = cash(api, f)
    close(api, f)
    close(api, f, state="OPEN")
    assert approve(api, f, prepare(api, f, realization(api, f, p, r, i, v, "1"))).status_code == 409
    assert (
        ok(post(api, "/cases", {"evaluation_id": f["evaluation"]["id"]}))["id"] == f["case"]["id"]
    )
    assert D(view(api, f)["realized"]) == 10000


def test_RW33_one_cent_exact(api):
    f = setup(api)
    cash(api, f, "0.01")
    assert D(view(api, f)["realized"]) == D("0.01") and D(view(api, f)["unrealized"]) == D(
        "49999.99"
    )


def test_RW34_semantic_retry(api):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "10000")
    proposed = prepare(api, f, realization(api, f, p, r, i, v, "10000"))
    key = uuid4()
    a = ok(approve(api, f, proposed, key=key))
    b = ok(approve(api, f, proposed))
    assert a["id"] == b["id"] and D(view(api, f)["realized"]) == 10000


def test_RW35_concurrent_same_proposal(api, recovery_engine):
    from tests.recovery_races import approve_race

    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "10000")
    proposed = prepare(api, f, realization(api, f, p, r, i, v, "10000"))
    results = approve_race(api, recovery_engine, [proposed, proposed])
    assert all("error" not in x for x in results) and results[0]["id"] == results[1]["id"]
    assert D(view(api, f)["realized"]) == 10000


def test_RW36_analyst_prepares_owner_approves(api):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "15000")
    set_role(api, "analyst")
    proposed = prepare(api, f, realization(api, f, p, r, i, v, "15000"))
    assert approve(api, f, proposed).status_code == 403
    set_role(api, "owner")
    act_id = ok(approve(api, f, proposed))["id"]
    assert act_id and D(view(api, f)["realized"]) == 15000


def test_RW37_tenant_history_and_attachment_hidden(api):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "10000")
    q = prepare(api, f, realization(api, f, p, r, i, v, "10000"))
    for suffix in [
        f"/cases/{f['case']['id']}",
        f"/cases/{f['case']['id']}/history",
        f"/proposals/{q['id']}/evidence",
    ]:
        response = api["client"].get(root(api, "b") + suffix, headers=headers(api, "b"))
        assert response.status_code == 404 and f["doc"] not in response.text


def test_RW38_source_loss_preserves_history(api):
    f = setup(api)
    cash(api, f)
    doc = api["session"].get(Document, UUID(f["doc"]))
    (api["app"].state.storage.root / doc.storage_key).unlink()
    v = view(api, f)
    assert D(v["realized"]) == 10000 and v["evidence"] == "UNAVAILABLE_OR_MISMATCH"
    assert v["category"] == "EVIDENCE_EXCEPTION" and v["ratio"] is None


def test_RW39_successor_with_realized_history_cannot_transfer(api):
    f = setup(api)
    cash(api, f)
    new, link = successor(api, f)
    q = prepare(
        api,
        f,
        dict(
            kind="retire",
            successor_case_id=new["case"]["id"],
            proof_successor_id=link["successor_relation_id"],
        ),
    )
    assert approve(api, f, q).status_code == 409
    assert D(view(api, f)["realized"]) == 10000 and D(view(api, new)["realized"]) == 0
    assert D(view(api, new)["potential"]) == 45000


def test_RW40_evidenced_extra_consideration(api):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "50000", gross="60000", other="10000")
    act(
        api,
        f,
        realization(api, f, p, r, i, v, "50000", gross="60000", other="10000", net_cash="60000"),
    )
    assert D(view(api, f)["realized"]) == 50000 and D(view(api, f)["net_cash"]) == 60000


def test_RW41_evidenced_vat_principal(api):
    f = setup(api, "90000")
    p, r = ready(api, f)
    i, v = instrument(
        api, f, "90000", kind="CREDIT", gross="108000", tax="18000", tax_basis="INCLUSIVE"
    )
    a = act(
        api,
        f,
        realization(
            api,
            f,
            p,
            r,
            i,
            v,
            "90000",
            method="APPLIED_CREDIT",
            gross="108000",
            tax="18000",
            tax_basis="INCLUSIVE",
            net_cash=None,
            application_reference="AP-VAT",
        ),
    )
    assert D(view(api, f)["realized"]) == 90000 and view(api, f)["ratio"] == "100.00"
    assert a["value"]["tax_recoverability"] == "NOT_ASSESSED"


def test_RW42_unknown_vat_blocks_ratio(api):
    f = setup(api, "90000")
    ready(api, f)
    instrument(
        api,
        f,
        None,
        kind="CREDIT",
        gross="108000",
        tax=None,
        other=None,
        tax_basis="UNKNOWN",
        reconciliation="UNRESOLVED",
    )
    v = view(api, f)
    assert (
        D(v["realized"]) == 0
        and v["unrealized"] is None
        and v["ratio"] is None
        and v["pending_credit"] is None
    )


def test_RW43_gross_and_net_are_distinct(api):
    f = setup(api)
    cash(api, f, "50000", fees="500", net_cash="49500")
    v = view(api, f)
    assert D(v["realized"]) == 50000 and D(v["net_cash"]) == 49500 and v["ratio"] == "100.00"


def test_RW44_unknown_withholding_supported_slice_only(api):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "49500", gross="50000", other=None, reconciliation="UNRESOLVED")
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
            "49500",
            gross="50000",
            other=None,
            withholding="500",
            reconciliation="UNRESOLVED",
        ),
    )
    v = view(api, f)
    assert (
        D(v["realized"]) == 49500
        and D(v["net_cash"]) == 49500
        and v["ratio"] is None
        and v["unrealized"] is None
    )


def associated_case(api, payer="parent-B", payee="buyer-A", relationship="AGENCY"):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "20000", payer=payer, payee=payee)
    q = prepare(api, f, realization(api, f, p, r, i, v, "20000", payer=payer, payee=payee))
    assert approve(api, f, q).status_code == 409
    p2 = party(
        api, f, previous_party_id=p["id"], payer=payer, payee=payee, relationship=relationship
    )
    r2 = act(api, f, r["value"] | {"party_id": p2["id"]})
    act(api, f, realization(api, f, p2, r2, i, v, "20000", payer=payer, payee=payee))
    return f


def test_RW45_parent_payer_requires_reviewed_mandate(api):
    f = associated_case(api)
    assert D(view(api, f)["realized"]) == 20000


def test_RW46_rename_continuity_and_acquisition(api):
    f = associated_case(api, payer="renamed-same-legal-id", relationship="CONTINUITY")
    assert D(view(api, f)["realized"]) == 20000
    p = prepare(
        api,
        f,
        dict(
            kind="party",
            supplier="acquirer-new-entity",
            customer="buyer-A",
            payer="acquirer-new-entity",
            payee="buyer-A",
            beneficiary="buyer-A",
            valid_from="2026-01-01",
            relationship="DIRECT",
            discharge="Asset purchase name alone",
            previous_party_id=view(api, f)["readiness_record"]["value"]["party_id"],
        ),
    )
    assert approve(api, f, p).status_code == 409


def test_RW47_processor_name_not_relationship(api):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "10000", payer="generic-processor")
    assert (
        approve(
            api,
            f,
            prepare(api, f, realization(api, f, p, r, i, v, "10000", payer="generic-processor")),
        ).status_code
        == 409
    )
    assert D(view(api, f)["realized"]) == 0 and view(api, f)["ratio"] is None


def test_RW48_workflow_no_financial_side_effect(api):
    f = setup(api)
    cash(api, f)
    before = view(api, f)
    set_role(api, "analyst")
    ok(
        post(
            api,
            f"/cases/{f['case']['id']}/workflow",
            dict(
                assignee_id=str(api["users"]["a"].id),
                priority="URGENT",
                next_action="Internal investigation",
                follow_up_date="2026-10-04",
                escalation="REQUESTED",
                reason="Operational only",
                expected_head=before["head_id"],
            ),
        )
    )
    after = view(api, f)
    assert all(
        after[k] == before[k]
        for k in ("potential", "validated", "pursuit", "realized", "finding_decision", "lifecycle")
    )
    assert after["workflow"]["priority"] == "URGENT"


def test_RW49_not_pursued_is_not_false_positive(api):
    f = setup(api)
    ready(api, f)
    close(api, f, reason="RELATIONSHIP")
    v = view(api, f)
    assert (
        D(v["unrealized"]) == 50000
        and v["finding_decision"] == "confirmed"
        and D(v["realized"]) == 0
    )


def cost(api, f, amount, currency="USD", paid=False):
    i = ok(
        post(
            api,
            "/instruments",
            dict(
                kind="COST",
                namespace="legal/cost",
                issuer="counsel",
                reference=str(uuid4()),
                currency=currency,
            ),
        )
    )
    value = dict(
        kind="cost",
        instrument_id=i["id"],
        state="INCURRED",
        event_reference=str(uuid4()),
        principal=amount,
        currency=currency,
        economic=DAY,
        scope="SKU-A",
        directly_attributable=True,
    )
    a = act(api, f, value)
    if paid:
        act(api, f, value | {"state": "PAID", "event_reference": str(uuid4())})
    return i, a


def test_RW50_cost_currencies_and_status_separate(api):
    f = setup(api)
    cash(api, f, "20000")
    cost(api, f, "2000", paid=True)
    cost(api, f, "1000")
    cost(api, f, "500", currency="EUR")
    v = view(api, f)
    assert D(v["realized"]) == 20000 and D(v["net_cash"]) == 20000
    assert (
        D(v["costs"]["USD"]["incurred"]) == 3000
        and D(v["costs"]["USD"]["paid"]) == 2000
        and D(v["costs"]["EUR"]["incurred"]) == 500
    )


def test_RW51_credit_economic_year_cutoffs(api):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(
        api, f, "20000", kind="CREDIT", economic={"precision": "DATE", "day": "2026-12-31"}
    )
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
            "20000",
            method="APPLIED_CREDIT",
            net_cash=None,
            application_reference="AP-JAN",
            economic={"precision": "DATE", "day": "2027-01-10"},
        ),
    )
    inspect(api, f)
    december = ok(post(api, "/report", report_body()))
    january = ok(
        post(
            api,
            "/report",
            report_body(
                start={"precision": "DATE", "day": "2027-01-01"},
                end={"precision": "DATE", "day": "2028-01-01"},
            ),
        )
    )
    assert D(december["realized_flow"]) == 0 and D(december["items"][0]["pending_credit"]) == 20000
    assert D(january["realized_flow"]) == 20000 and D(january["items"][0]["pending_credit"]) == 0


def test_RW52_corrected_economic_date_preserves_as_known(api):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "10000")
    before = datetime.now(UTC).isoformat()
    a = act(
        api,
        f,
        realization(
            api, f, p, r, i, v, "10000", economic={"precision": "DATE", "day": "2026-12-31"}
        ),
    )
    inspect(api, f)
    old_k = datetime.now(UTC).isoformat()
    old = ok(post(api, "/report", report_body(known_at=old_k)))
    negative(api, f, a, "10000")
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
            "10000",
            replaces_id=a["id"],
            economic={"precision": "DATE", "day": "2027-01-02"},
        ),
    )
    inspect(api, f)
    earlier = ok(post(api, "/report", report_body(known_at=before)))
    replay = ok(post(api, "/report", report_body(known_at=old_k)))
    restated = ok(post(api, "/report", report_body()))
    january = ok(
        post(
            api,
            "/report",
            report_body(
                start={"precision": "DATE", "day": "2027-01-01"},
                end={"precision": "DATE", "day": "2028-01-01"},
            ),
        )
    )
    assert D(earlier["realized_flow"]) == 0 and replay == old
    assert (
        D(old["realized_flow"]) == 10000
        and D(restated["realized_flow"]) == 0
        and D(january["realized_flow"]) == 10000
    )
    assert D(view(api, f)["realized"]) == 10000 and D(view(api, f)["net_cash"]) == 10000


def test_RW53_different_payee_requires_beneficial_discharge(api):
    f = associated_case(api, payer="supplier-A", payee="buyer-affiliate-B")
    assert D(view(api, f)["realized"]) == 20000


def test_RW54_independent_competing_payments(api, recovery_engine):
    from tests.recovery_races import approve_race

    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "30000")
    j, w = instrument(api, f, "30000")
    proposals = [
        prepare(api, f, realization(api, f, p, r, i, v, "30000")),
        prepare(api, f, realization(api, f, p, r, j, w, "30000")),
    ]
    results = approve_race(api, recovery_engine, proposals)
    assert sum("error" not in x for x in results) == 1
    assert D(view(api, f)["realized"]) == 30000 and D(view(api, f)["unrealized"]) == 20000


def test_RW55_source_change_during_capture_aborts(api, monkeypatch):
    from app.recovery import service

    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "10000")
    q = prepare(api, f, realization(api, f, p, r, i, v, "10000"))
    source = api["session"].get(Document, UUID(f["doc"]))
    path = api["app"].state.storage.root / source.storage_key
    verify = service.verified_sources
    calls = 0

    def changing(*args, **kwargs):
        nonlocal calls
        result = verify(*args, **kwargs)
        calls += 1
        if calls == 1:
            path.write_bytes(b"Concurrent externally corrupted bank bytes")
        return result

    monkeypatch.setattr(service, "verified_sources", changing)
    result = approve(api, f, q)
    assert result.status_code == 409 and D(view(api, f)["realized"]) == 0
    assert f["doc"] not in result.text and "bank bytes" not in result.text


def test_RW56_de_recognition_is_not_cash_return(api):
    f = setup(api)
    *_, a = cash(api, f)
    close(api, f)
    negative(api, f, a)
    assert D(view(api, f)["realized"]) == 7000 and D(view(api, f)["net_cash"]) == 10000
    g = setup(api)
    *_, b = cash(api, g)
    close(api, g)
    negative(api, g, b, reversal_type="ECONOMIC_RETURN", cash_return="3000")
    assert D(view(api, g)["realized"]) == 7000 and D(view(api, g)["net_cash"]) == 7000
