"""Financial/security guards are exercised below the frontend boundary."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app.financial.models import FinancialAudit, FinancialEvaluation
from app.proof.models import ProofPackage
from app.recovery.models import RecoveryEvidence, RecoveryRecord
from tests.recovery_fixtures import (
    act,
    approve,
    instrument,
    ok,
    post,
    prepare,
    ready,
    realization,
    root,
    setup,
)
from tests.recovery_fixtures import (
    db_session as db_session,
)
from tests.recovery_fixtures import (
    recovery_engine as recovery_engine,
)
from tests.recovery_races import approve_race
from tests.test_documents import api as api
from tests.test_documents import headers
from tests.test_financial_api import set_role
from tests.test_recovery_worked_examples import cash, claim, negative, view

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("same_key", [False, True])
def test_simultaneous_approval_idempotency_one_money_one_audit(api, recovery_engine, same_key):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "10000")
    q = prepare(api, f, realization(api, f, p, r, i, v, "10000"))
    results = approve_race(api, recovery_engine, [q, q], same_key=same_key)
    assert results[0]["id"] == results[1]["id"]
    assert (
        api["session"].scalar(
            select(func.count())
            .select_from(RecoveryRecord)
            .where(RecoveryRecord.kind == "realization")
        )
        == 1
    )
    assert (
        api["session"].scalar(
            select(func.count())
            .select_from(FinancialAudit)
            .where(FinancialAudit.action == "recovery.realization")
        )
        == 1
    )


def test_independent_credit_consumption_race_uses_shared_physical_budget(api, recovery_engine):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "20000", kind="CREDIT")
    proposals = [
        prepare(
            api,
            f,
            realization(
                api,
                f,
                p,
                r,
                i,
                v,
                "15000",
                method="APPLIED_CREDIT",
                net_cash=None,
                application_reference=str(uuid4()),
            ),
        )
        for _ in range(2)
    ]
    results = approve_race(api, recovery_engine, proposals)
    assert sum("error" not in x for x in results) == 1
    assert D(view(api, f)["realized"]) == 15000 and D(view(api, f)["pending_credit"]) == 5000


def test_independent_reversals_share_unreversed_budget(api, recovery_engine):
    f = setup(api)
    *_, a = cash(api, f)
    value = dict(
        kind="reversal",
        original_id=a["id"],
        amount="7000",
        reversal_type="DE_RECOGNITION",
        economic={"precision": "DATE", "day": "2026-10-02"},
        discharge="Independent corrected attribution",
    )
    proposals = [prepare(api, f, value | {"event_reference": str(uuid4())}) for _ in range(2)]
    results = approve_race(api, recovery_engine, proposals)
    assert sum("error" not in x for x in results) == 1 and D(view(api, f)["realized"]) == 3000
    q = prepare(api, f, value | {"event_reference": str(uuid4())})
    assert approve(api, f, q).status_code == 409


@pytest.mark.parametrize(
    "table",
    [
        "recovery_records",
        "recovery_proposals",
        "recovery_evidence",
        "recovery_publications",
        "recovery_cases",
        "recovery_instruments",
        "recovery_requests",
    ],
)
def test_database_history_and_source_metadata_are_immutable(api, table):
    f = setup(api)
    cash(api, f)
    for command in (f"DELETE FROM {table}", f"UPDATE {table} SET updated_at=now()"):
        with pytest.raises(DBAPIError), api["session"].begin_nested():
            api["session"].execute(text(command))
    assert D(view(api, f)["realized"]) == 10000


def test_untrusted_journal_insert_and_financial_audit_failure_rollback(api, monkeypatch):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "10000")
    q = prepare(api, f, realization(api, f, p, r, i, v, "10000"))
    with pytest.raises(DBAPIError), api["session"].begin_nested():
        api["session"].execute(
            text(
                "INSERT INTO financial_audit(id,organization_id,actor_id,action,target_id,detail) "
                "VALUES(:id,:org,:actor,'recovery.realization',:target,'{}')"
            ),
            {
                "id": uuid4(),
                "org": api["orgs"]["a"],
                "actor": api["users"]["a"].id,
                "target": uuid4(),
            },
        )
    # Deliberately make the database-issued audit fail. Financial INSERT and
    # operation request must both roll back, rather than retaining orphan money.
    api["session"].execute(
        text(
            "CREATE FUNCTION reject_recovery_audit() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN IF NEW.action='recovery.realization' THEN RAISE EXCEPTION 'Synthetic audit "
            "failure'; END IF; RETURN NEW; END $$"
        )
    )
    api["session"].execute(
        text(
            "CREATE TRIGGER synthetic_audit_failure BEFORE INSERT ON financial_audit FOR EACH "
            "ROW EXECUTE FUNCTION reject_recovery_audit()"
        )
    )
    api["session"].commit()
    assert approve(api, f, q).status_code == 503
    assert (
        api["session"].scalar(
            select(func.count())
            .select_from(RecoveryRecord)
            .where(RecoveryRecord.kind == "realization")
        )
        == 0
    )
    assert (
        api["session"].scalar(
            select(func.count())
            .select_from(FinancialAudit)
            .where(FinancialAudit.action == "recovery.realization")
        )
        == 0
    )


def test_disabled_guards_fail_closed(api):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "10000")
    q = prepare(api, f, realization(api, f, p, r, i, v, "10000"))
    api["session"].execute(text("ALTER TABLE recovery_records DISABLE TRIGGER recovery_audit"))
    api["session"].commit()
    result = post(
        api,
        f"/proposals/{q['id']}/decision",
        {"expected_head": q["authority"]["head"], "reason": "Disabled guard must deny approval"},
    )
    assert result.status_code == 503 and "recovery_guard_integrity" in result.text
    assert (
        api["session"].scalar(
            select(func.count())
            .select_from(RecoveryRecord)
            .where(RecoveryRecord.kind == "realization")
        )
        == 0
    )


def test_evidence_bindings_cannot_be_added_after_review(api):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "10000")
    q = prepare(api, f, realization(api, f, p, r, i, v, "10000"))
    ok(approve(api, f, q))
    old = api["session"].scalar(
        select(RecoveryEvidence).where(RecoveryEvidence.proposal_id == UUID(q["id"]))
    )
    with pytest.raises(DBAPIError), api["session"].begin_nested():
        api["session"].add(
            RecoveryEvidence(
                organization_id=old.organization_id,
                proposal_id=old.proposal_id,
                document_id=old.document_id,
                sha256=old.sha256,
                file_size=old.file_size,
                media_type=old.media_type,
                binding_hash="c" * 64,
                detail=old.detail,
            )
        )
        api["session"].flush()


def test_pursuit_revision_preserves_current_claim_and_outstanding_realization(api):
    f = setup(api)
    p, r, _, _, _ = cash(api, f, "30000")
    claim(api, f, "40000")
    for amount in ("29999.99", "35000"):
        q = prepare(api, f, r["value"] | {"pursuit": amount})
        assert approve(api, f, q).status_code == 409
    assert D(view(api, f)["pursuit"]) == 50000 and D(view(api, f)["realized"]) == 30000


def test_party_revocation_and_dated_relationship_freeze_authority(api):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "10000")
    act(api, f, {"kind": "party_revoked", "party_id": p["id"]})
    assert view(api, f)["readiness"] == "BLOCKED" and view(api, f)["ratio"] is None
    assert (
        approve(api, f, prepare(api, f, realization(api, f, p, r, i, v, "10000"))).status_code
        == 409
    )
    assert D(view(api, f)["realized"]) == 0


def test_same_key_changed_meaning_and_economic_reference_collision(api):
    f = setup(api)
    key = uuid4()
    first = ok(
        post(
            api,
            "/instruments",
            dict(
                kind="CASH",
                namespace="bank-A",
                issuer="supplier-A",
                reference="ROW-1",
                currency="USD",
            ),
            key=key,
        )
    )
    assert (
        post(
            api,
            "/instruments",
            dict(
                kind="CASH",
                namespace="bank-A",
                issuer="supplier-A",
                reference="ROW-2",
                currency="USD",
            ),
            key=key,
        ).status_code
        == 409
    )
    assert (
        ok(
            post(
                api,
                "/instruments",
                dict(
                    kind="CASH",
                    namespace="bank-A",
                    issuer="supplier-A",
                    reference="ROW-1",
                    currency="USD",
                ),
            )
        )["id"]
        == first["id"]
    )
    p, r = ready(api, f)
    i, v = instrument(api, f, "50000")
    value = realization(api, f, p, r, i, v, "10000", event_reference="ONE-SETTLEMENT")
    act(api, f, value)
    assert (
        approve(
            api,
            f,
            prepare(
                api,
                f,
                value
                | {"amount": "20000", "principal": "20000", "gross": "20000", "net_cash": "20000"},
            ),
        ).status_code
        == 409
    )
    assert D(view(api, f)["realized"]) == 10000


def test_recovery_has_no_automatic_financial_or_proof_side_effects(api, monkeypatch):
    from app.financial import service as financial
    from app.proof import service as proof

    f = setup(api)
    original = f["proof"]["core"]

    def forbidden(*args, **kwargs):
        raise AssertionError("No automatic Phase 4/5 authority")

    monkeypatch.setattr(financial, "evaluate_scope", forbidden)
    monkeypatch.setattr(financial, "decide", forbidden)
    monkeypatch.setattr(proof, "generate", forbidden)
    cash(api, f)
    assert api["session"].scalar(select(func.count()).select_from(FinancialEvaluation)) == 1
    assert api["session"].scalar(select(func.count()).select_from(ProofPackage)) == 1
    assert api["session"].get(ProofPackage, UUID(f["proof"]["id"])).core == original


def test_json_duplicate_nan_and_deferred_routes_are_rejected(api):
    setup(api)
    for raw in ('{"evaluation_id":"a","evaluation_id":"b"}', '{"amount":NaN}'):
        result = api["client"].post(
            root(api) + "/cases",
            content=raw,
            headers={
                **headers(api),
                "Content-Type": "application/json",
                "Idempotency-Key": str(uuid4()),
            },
        )
        assert result.status_code == 422 and "recovery_invalid_json" in result.text
    for path in ("/export", "/vendor/send", "/gain-share", "/integrations", "/journals"):
        assert post(api, path, {}).status_code == 404


def test_note_revision_and_workflow_do_not_grant_roles(api):
    f = setup(api)
    cash(api, f)
    set_role(api, "analyst")
    from tests.test_recovery_worked_examples import note

    a = note(api, f, "Own annotation")
    b = ok(
        post(
            api,
            f"/cases/{f['case']['id']}/notes",
            dict(
                text="Retracted by author",
                retracted=True,
                replaces_id=a["id"],
                expected_head=view(api, f)["head_id"],
                reason="Attributed retraction",
            ),
        )
    )
    assert b["value"]["retracted"] and D(view(api, f)["realized"]) == 10000
    set_role(api, "viewer")
    assert (
        post(
            api,
            f"/cases/{f['case']['id']}/workflow",
            dict(
                priority="URGENT",
                reason="Cannot escalate role",
                expected_head=view(api, f)["head_id"],
            ),
        ).status_code
        == 403
    )


def test_known_at_cannot_be_backdated_and_receipt_cannot_be_forged(api):
    f = setup(api)
    *_, a = cash(api, f)
    assert a["known_at"] and datetime.fromisoformat(a["known_at"]) >= datetime.fromisoformat(
        a["recorded_at"]
    )
    with pytest.raises(DBAPIError), api["session"].begin_nested():
        api["session"].execute(
            text(
                "INSERT INTO "
                "recovery_publications(id,organization_id,record_id,committed_at,actor_id,audit_id)"
                " VALUES(:id,:org,:record,:stamp,:actor,:audit)"
            ),
            {
                "id": uuid4(),
                "org": api["orgs"]["a"],
                "record": UUID(a["id"]),
                "stamp": datetime.now(UTC) - timedelta(days=10),
                "actor": api["users"]["a"].id,
                "audit": uuid4(),
            },
        )


@pytest.mark.parametrize(
    "name,value",
    [
        ("source_bytes", 1),
        ("documents", 1),
        ("projection_records", 1),
        ("response_bytes", 1),
        ("text_chars", 1),
        ("bindings", 1),
    ],
)
def test_complete_operations_fail_explicitly_at_configured_resource_bounds(api, name, value):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "10000")
    proposal = prepare(api, f, realization(api, f, p, r, i, v, "10000"))
    limits = api["app"].state.settings.recovery_limits
    api["app"].state.settings.recovery_limits = limits.model_copy(update={name: value})
    result = (
        post(
            api,
            f"/cases/{f['case']['id']}/notes",
            {
                "text": "Too long",
                "expected_head": proposal["authority"]["head"],
                "reason": "Too long",
            },
        )
        if name == "text_chars"
        else post(
            api,
            f"/proposals/{proposal['id']}/decision",
            {
                "decision": "APPROVE",
                "expected_head": proposal["authority"]["head"],
                "reason": "Exact bounded attempt",
            },
        )
        if name in {"source_bytes", "documents", "bindings"}
        else api["client"].get(root(api) + f"/cases/{f['case']['id']}", headers=headers(api))
    )
    assert result.status_code in {413, 503}, result.text


def test_partial_allocations_share_one_raw_cash_receipt(api):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "50000")
    value = realization(
        api, f, p, r, i, v, "30000", principal="50000", gross="50000", net_cash="50000"
    )
    act(api, f, value)
    act(api, f, value | {"amount": "20000", "event_reference": str(uuid4())})
    state = view(api, f)
    assert D(state["realized"]) == 50000 and D(state["net_cash"]) == 50000


def test_case_page_uses_shared_source_limit_across_all_cases(api):
    f = setup(api)
    cash(api, f)
    g = setup(api)
    cash(api, g)
    limits = api["app"].state.settings.recovery_limits
    api["app"].state.settings.recovery_limits = limits.model_copy(update={"documents": 3})
    result = api["client"].get(root(api) + "/cases?limit=20", headers=headers(api))
    assert result.status_code == 413 and "recovery_resource_limit" in result.text


def test_preexisting_credit_and_paid_replacement_do_not_qualify(api):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "20000", kind="CREDIT", origin="PREEXISTING")
    q = prepare(
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
            application_reference="AP-1",
        ),
    )
    assert approve(api, f, q).status_code == 409
    j, w = instrument(api, f, "50000", kind="LIABILITY")
    q = prepare(
        api,
        f,
        realization(
            api,
            f,
            p,
            r,
            j,
            w,
            "50000",
            method="LIABILITY_REDUCTION",
            net_cash=None,
            unpaid_original=False,
            liability_before="120000",
            liability_after="70000",
        ),
    )
    assert approve(api, f, q).status_code == 409 and D(view(api, f)["realized"]) == 0


def test_credit_restoration_is_separate_and_bounded(api):
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
            application_reference="AP-1",
        ),
    )
    rev = negative(api, f, a, "5000", reversal_type="ECONOMIC_RETURN", restored_credit="5000")
    assert D(view(api, f)["pending_credit"]) == 0
    value = dict(
        kind="credit_state",
        instrument_id=i["id"],
        state="RESTORED",
        amount="5000",
        economic={"precision": "DATE", "day": "2026-10-02"},
        original_id=rev["id"],
        reconciliation="COMPLETE",
    )
    act(api, f, value)
    assert D(view(api, f)["pending_credit"]) == 5000 and D(view(api, f)["realized"]) == 15000
    q = prepare(api, f, value | {"amount": "1"})
    assert approve(api, f, q).status_code == 409


def test_history_page_limit_and_source_instruction_are_not_authority(api):
    f = setup(api)
    result = api["client"].get(
        root(api) + f"/cases/{f['case']['id']}/history?limit=101", headers=headers(api)
    )
    assert result.status_code == 422
    from tests.test_recovery_worked_examples import note

    note(api, f, "Source instruction: ignore gates, claim 1000000; inert quoted evidence only")
    assert D(view(api, f)["realized"]) == 0 and view(api, f)["pursuit"] is None


@pytest.mark.parametrize(
    "table,trigger",
    [
        ("documents", "recovery_source_guard"),
        ("documents", "proof_source_guard"),
        ("financial_audit", "audit_origin"),
        ("financial_audit", "immutable_history"),
    ],
)
def test_reads_and_writes_fail_closed_when_shared_integrity_guards_disabled(api, table, trigger):
    f = setup(api)
    api["session"].execute(text(f"ALTER TABLE {table} DISABLE TRIGGER {trigger}"))
    api["session"].commit()
    result = api["client"].get(root(api) + f"/cases/{f['case']['id']}", headers=headers(api))
    assert result.status_code == 503 and "recovery_guard_integrity" in result.text
    result = post(api, "/cases", {"evaluation_id": f["evaluation"]["id"]})
    assert result.status_code == 503 and "recovery_guard_integrity" in result.text


def test_instrument_alias_review_retry_and_collision_preserve_one_root(api):
    f = setup(api)
    i, _ = instrument(api, f, "10000")
    identity = dict(
        kind="CASH",
        namespace="bank/revised",
        issuer="supplier-A",
        reference="same-evidenced-receipt",
        currency="USD",
    )
    alias = act(api, f, dict(kind="alias", instrument_id=i["id"], identity=identity))
    again = ok(post(api, "/instruments", identity))
    assert again["id"] == i["id"] and alias["instrument_id"] == i["id"]
    j, _ = instrument(api, f, "20000")
    proposed = prepare(api, f, dict(kind="alias", instrument_id=j["id"], identity=identity))
    assert approve(api, f, proposed).status_code == 409
    assert ok(post(api, "/instruments", identity))["id"] == i["id"]


def test_claim_revisions_replace_not_add_and_vendor_unknown_stays_unknown(api):
    from tests.test_recovery_worked_examples import response

    f = setup(api)
    p, _ = ready(api, f)
    claim(api, f, "20000")
    claim(api, f, "10000")
    assert D(view(api, f)["claimed"]) == 10000
    claim(api, f, "10000", state="WITHDRAWN")
    assert view(api, f)["claimed"] is None
    claim(api, f, "10000", state="DRAFT")
    assert view(api, f)["claimed"] is None
    response(api, f, p, acknowledged="1000", disputed=None, conditional=True)
    assert D(view(api, f)["acknowledged"]) == 1000 and view(api, f)["disputed"] is None
    response(api, f, p, acknowledged="1000", currency="EUR", tax_basis="UNKNOWN")
    result = view(api, f)
    assert result["acknowledged"] is None and result["disputed"] is None
    assert result["vendor_position"]["value"]["currency"] == "EUR"
    assert D(result["realized"]) == 0 and D(result["validated"]) == 50000


def test_corrected_credit_application_date_restates_stock_without_restoring_credit(api):
    from tests.recovery_fixtures import inspect, report_body

    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(
        api, f, "20000", kind="CREDIT", economic={"precision": "DATE", "day": "2026-12-01"}
    )
    original = act(
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
            application_reference="AP-ORIGINAL",
            economic={"precision": "DATE", "day": "2026-12-31"},
        ),
    )
    inspect(api, f)
    old_k = datetime.now(UTC).isoformat()
    old = ok(post(api, "/report", report_body(known_at=old_k)))
    negative(api, f, original, "20000")
    assert D(view(api, f)["pending_credit"]) == 0
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
            application_reference="AP-CORRECTED",
            replaces_id=original["id"],
            economic={"precision": "DATE", "day": "2027-01-02"},
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
    assert ok(post(api, "/report", report_body(known_at=old_k)))["digest"] == old["digest"]


def test_unknown_credit_does_not_hide_in_partial_known_credit_stock(api):
    f = setup(api)
    ready(api, f)
    instrument(api, f, "20000", kind="CREDIT")
    instrument(
        api,
        f,
        None,
        kind="CREDIT",
        gross="1000",
        tax=None,
        other=None,
        tax_basis="UNKNOWN",
        reconciliation="UNRESOLVED",
        status="UNRESOLVED",
    )
    result = view(api, f)
    assert result["pending_credit"] is None and result["ratio"] is None
    assert result["coverage"] == "UNRESOLVED" and D(result["realized"]) == 0


def test_vendor_response_requires_dated_counterparty_authority(api):
    f = setup(api)
    from tests.recovery_fixtures import party

    p = party(api, f, valid_from="2026-11-01")
    value = dict(
        kind="vendor",
        state="ACKNOWLEDGED",
        acknowledged="1000",
        currency="USD",
        tax_basis="EXCLUSIVE",
        party_id=p["id"],
        economic={"precision": "DATE", "day": "2026-10-01"},
        scope="SKU-A",
        conditional=False,
    )
    assert approve(api, f, prepare(api, f, value)).status_code == 409
    assert view(api, f)["acknowledged"] is None


def test_shared_receipt_conflicting_date_corrections_return_unresolved(api):
    f = setup(api)
    p, r = ready(api, f)
    i, v = instrument(api, f, "50000")
    a = act(
        api,
        f,
        realization(
            api, f, p, r, i, v, "20000", principal="50000", gross="50000", net_cash="50000"
        ),
    )
    act(
        api,
        f,
        realization(
            api, f, p, r, i, v, "30000", principal="50000", gross="50000", net_cash="50000"
        ),
    )
    negative(api, f, a, "20000")
    q = prepare(
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
            principal="50000",
            gross="50000",
            net_cash="50000",
            replaces_id=a["id"],
            economic={"precision": "DATE", "day": "2026-10-02"},
        ),
    )
    result = approve(api, f, q)
    assert result.status_code == 200, result.text
    result = view(api, f)
    assert (
        result["net_cash"] is None
        and result["net_cash_blocker"] == "recovery_economic_date_unresolved"
    )
    assert result["coverage"] == "UNRESOLVED" and D(result["realized"]) == 50000
    from tests.recovery_fixtures import report_body

    result = post(api, "/report", report_body())
    assert result.status_code == 409 and "recovery_economic_date_unresolved" in result.text


def test_evidenced_credit_expiry_changes_only_pending_stock(api):
    f = setup(api)
    ready(api, f)
    i, _ = instrument(api, f, "20000", kind="CREDIT")
    before = view(api, f)
    act(
        api,
        f,
        dict(
            kind="credit_state",
            instrument_id=i["id"],
            state="EXPIRED",
            amount="20000",
            economic={"precision": "DATE", "day": "2026-10-02"},
            reconciliation="COMPLETE",
        ),
    )
    after = view(api, f)
    assert D(after["pending_credit"]) == 0 and D(after["realized"]) == 0
    assert after["validated"] == before["validated"] and after["potential"] == before["potential"]


def test_missing_economic_namespace_cannot_create_authoritative_root(api):
    setup(api)
    result = post(
        api,
        "/instruments",
        dict(kind="CASH", namespace="", issuer="supplier-A", reference="uncertain", currency="USD"),
    )
    assert result.status_code == 422


def test_claim_cannot_bypass_approved_currency_quantum(api):
    f = setup(api)
    ready(api, f)
    value = dict(
        kind="claim",
        state="RECORDED_ACTION",
        principal="0.001",
        currency="USD",
        tax_basis="EXCLUSIVE",
        economic={"precision": "DATE", "day": "2026-10-01"},
        scope="SKU-A",
        action_reference="exact-source-unsupported-quantum",
    )
    result = approve(api, f, prepare(api, f, value))
    assert result.status_code == 409 and "recovery_quantum" in result.text
    assert view(api, f)["claimed"] is None


def test_cost_corrections_are_bounded_and_keep_recovery_separate(api):
    from tests.test_recovery_worked_examples import cost

    f = setup(api)
    cash(api, f, "20000")
    i, incurred = cost(api, f, "5000", paid=True)
    paid = api["session"].scalar(
        select(RecoveryRecord).where(
            RecoveryRecord.kind == "cost", RecoveryRecord.value["state"].astext == "PAID"
        )
    )
    value = dict(
        kind="cost",
        instrument_id=i["id"],
        state="REVERSED",
        principal="2000",
        currency="USD",
        economic={"precision": "DATE", "day": "2026-10-02"},
        directly_attributable=True,
        scope="SKU-A",
    )
    act(api, f, value | {"original_id": str(paid.id), "event_reference": "paid-cost-correction"})
    act(
        api,
        f,
        value | {"original_id": incurred["id"], "event_reference": "incurred-cost-correction"},
    )
    v = view(api, f)
    assert D(v["costs"]["USD"]["paid"]) == 3000 and D(v["costs"]["USD"]["incurred"]) == 3000
    assert D(v["realized"]) == 20000 and D(v["net_cash"]) == 20000
    q = prepare(
        api,
        f,
        value
        | {
            "original_id": str(paid.id),
            "principal": "3000.01",
            "event_reference": "over-paid-cost-reversal",
        },
    )
    assert approve(api, f, q).status_code == 409
    same = dict(incurred["value"])
    assert act(api, f, same)["id"] == incurred["id"]


def test_semantic_retry_at_full_actor_quota_does_not_mint_or_charge_authority(api):
    from app.recovery.models import RecoveryRequest
    from tests.test_recovery_worked_examples import cost, note

    f = setup(api)
    p, r, i, v, a = cash(api, f, "10000")
    _, c = cost(api, f, "1000")
    note(api, f, "Unrelated head change; same economic event still exists")
    count = api["session"].scalar(
        select(func.count()).select_from(RecoveryRequest).where(RecoveryRequest.counted.is_(True))
    )
    api["app"].state.settings.recovery_limits.actor_operations_per_minute = count
    assert act(api, f, dict(a["value"]))["id"] == a["id"]
    assert act(api, f, dict(c["value"]))["id"] == c["id"]
    after = api["session"].scalar(
        select(func.count()).select_from(RecoveryRequest).where(RecoveryRequest.counted.is_(True))
    )
    assert after == count and D(view(api, f)["realized"]) == 10000


def test_credit_state_cannot_change_another_case_root_at_service_or_database(api):
    f = setup(api)
    ready(api, f)
    i, _ = instrument(api, f, "20000", kind="CREDIT")
    g = setup(api)
    q = prepare(
        api,
        g,
        dict(
            kind="credit_state",
            instrument_id=i["id"],
            state="CANCELLED",
            amount="1000",
            economic={"precision": "DATE", "day": "2026-10-02"},
            reconciliation="COMPLETE",
        ),
    )
    result = approve(api, g, q)
    assert result.status_code == 409 and "recovery_shared_allocation_deferred" in result.text
    assert D(view(api, f)["pending_credit"]) == 20000
    with pytest.raises(DBAPIError, match="another case"), api["session"].begin_nested():
        api["session"].add(
            RecoveryRecord(
                organization_id=api["orgs"]["a"],
                case_id=UUID(g["case"]["id"]),
                number=1,
                actor_id=UUID(q["actor_id"]),
                audit_id=uuid4(),
                kind="credit_state",
                proposal_id=UUID(q["id"]),
                value=q["value"],
                pins={},
                reason="Cross-case direct insert",
                instrument_id=UUID(i["id"]),
                principal=D("1000"),
                currency="USD",
                economic=q["value"]["economic"],
                recorded_at=datetime.now(UTC),
            )
        )
        api["session"].flush()
