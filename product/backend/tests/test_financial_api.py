from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app.db.models import OrganizationMembership
from app.financial.models import (
    FinancialAudit,
    FinancialEvaluation,
    ReviewedFinancialSource,
)
from tests.financial_fixtures import bill, packet, term
from tests.test_documents import api as api
from tests.test_documents import headers, upload

pytestmark = pytest.mark.integration


def leaves(value, prefix=""):
    if isinstance(value, dict):
        return [p for k, v in value.items() for p in leaves(v, f"{prefix}/{k}")]
    if isinstance(value, list):
        return [p for i, v in enumerate(value) for p in leaves(v, f"{prefix}/{i}")]
    return [prefix]


def body(kind, value, document_id, previous=None, state="approved", field_id=None):
    value = value.model_dump(mode="json") if hasattr(value, "model_dump") else value
    return {
        "kind": kind,
        "key": value.get("key", kind),
        "expected_revision": previous,
        "state": state,
        "reason": "Source meaning reviewed",
        "uncertainty_resolution": "All financial meanings grounded in the cited source",
        "knowledge_cutoff": datetime.now(UTC).isoformat(),
        "value": value,
        "evidence": [
            {
                "document_id": str(document_id),
                "location": "CSV row 2",
                "quote": "Synthetic reviewed source",
                "field_id": field_id,
                "manual": field_id is None,
                "supports": leaves(value),
            }
        ],
    }


def root(api, org="a"):
    return f"/api/v1/organizations/{api['orgs'][org]}/financial"


def set_role(api, role, subject="a"):
    membership = api["session"].scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == api["users"][subject].id
        )
    )
    membership.role = role
    api["session"].flush()


def create(api, kind, content):
    response = upload(api, kind=kind, content=content, filename=kind + ".csv")
    assert response.status_code == 201, response.text
    doc = response.json()["id"]
    response = api["client"].post(
        root(api) + "/sources", headers=headers(api), json={"document_id": doc, "kind": kind}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"], doc


def review(api, source_id, data, subject="a", key=None):
    return api["client"].post(
        root(api) + f"/sources/{source_id}/reviews",
        headers={**headers(api, subject), "Idempotency-Key": str(key or uuid4())},
        json=data,
    )


def workflow(api):
    set_role(api, "owner")
    contract, cdoc = create(api, "contract", b"reference,price\nC-1,10\n")
    invoice, idoc = create(
        api,
        "invoice",
        (
            b"field,value\nInvoice number,I-1\nSupplier,supplier-A\nCustomer,buyer-A\n"
            b"Invoice date,2026-06-15\nCurrency,USD\nTotal,1200\n"
            b"Line 1 description,Approved billed line\nLine 1 sku,SKU-A\n"
            b"Line 1 quantity,100\nLine 1 unit price,12\nLine 1 unit,unit\nLine 1 total,1200\n"
        ),
    )
    # Phase 3 remains candidate history. Review retains its exact extracted lineage.
    processed = api["client"].post(
        f"/api/v1/organizations/{api['orgs']['a']}/documents/{idoc}/process",
        headers={**headers(api), "Idempotency-Key": str(uuid4())},
    )
    assert processed.status_code == 200, processed.text
    fields = processed.json()["run"]["fields"]
    assert fields, "The workflow must preserve actual Phase 3 extraction lineage"
    field_id = next(f["id"] for f in fields if f["path"] == "lines.1.quantity")
    values = [
        (contract, body("term", term(), cdoc)),
        (
            contract,
            body(
                "packet", packet(documents=({"document_id": UUID(cdoc), "role": "master"},)), cdoc
            ),
        ),
        (invoice, body("billing_scope", bill(), idoc, field_id=field_id)),
        (
            invoice,
            body(
                "association",
                {
                    "contract_source_id": contract,
                    "method": "manual",
                    "identifier": None,
                    "rationale": "Invoice obligation reviewed",
                },
                idoc,
            ),
        ),
    ]
    approvals = []
    for source_id, data in values:
        response = review(api, source_id, data)
        assert response.status_code == 201, response.text
        approvals.append(response.json())
    return contract, invoice, cdoc, idoc, approvals


def evaluate(api, invoice, *, revisions=None, scope="line-1", subject="a"):
    if revisions is None:
        detail = api["client"].get(root(api) + f"/sources/{invoice}", headers=headers(api))
        assert detail.status_code == 200, detail.text
        revisions = detail.json()["revision_ids"]
    return api["client"].post(
        root(api) + f"/sources/{invoice}/evaluate",
        headers=headers(api, subject),
        json={"scope_key": scope, "expected_revisions": revisions},
    )


def test_real_extraction_review_evaluate_retry_audit_and_dismissal(api):
    contract, invoice, cdoc, idoc, approvals = workflow(api)
    response = evaluate(api, invoice)
    assert response.status_code == 200, response.text
    finding = response.json()
    assert finding["potential"] == "200.000000" and finding["status"] == "detected"
    assert finding["snapshot"]["calculation"]["precision"] == 80
    assert evaluate(api, invoice).json()["id"] == finding["id"]
    assert api["session"].scalar(select(func.count()).select_from(FinancialEvaluation)) == 1
    decision = api["client"].post(
        root(api) + f"/evaluations/{finding['id']}/decision",
        headers=headers(api),
        json={
            "status": "false_positive",
            "reason": "Reviewed duplicate commercial claim",
            "expected_decision": None,
        },
    )
    assert decision.status_code == 201, decision.text
    assert evaluate(api, invoice).json()["status"] == "false_positive"
    actions = api["session"].scalars(select(FinancialAudit.action)).all()
    assert actions.count("evaluation.created") == 1 and "finding.false_positive" in actions
    assert len([a for a in actions if a.startswith("review.")]) == 4
    repeated = api["client"].post(
        root(api) + "/sources", headers=headers(api), json={"document_id": idoc, "kind": "invoice"}
    )
    assert repeated.json()["id"] == invoice
    assert api["session"].scalar(select(func.count()).select_from(ReviewedFinancialSource)) == 2


def test_correction_revocation_stale_history_and_new_evaluation(api):
    contract, invoice, cdoc, idoc, approvals = workflow(api)
    original = evaluate(api, invoice).json()
    corrected = review(api, contract, body("term", term(rate="11"), cdoc, approvals[0]["id"]))
    assert corrected.status_code == 201, corrected.text
    stale = (
        api["client"].get(root(api) + f"/evaluations/{original['id']}", headers=headers(api)).json()
    )
    assert stale["stale"] and stale["potential"] == original["potential"]
    current = evaluate(api, invoice).json()
    assert current["id"] != original["id"] and current["potential"] == "100.000000"
    revoked = review(
        api, contract, body("term", term(rate="11"), cdoc, corrected.json()["id"], "revoked")
    )
    assert revoked.status_code == 201, revoked.text
    blocked = evaluate(api, invoice).json()
    assert blocked["potential"] is None
    assert api["session"].get(FinancialEvaluation, UUID(original["id"])).potential == 200


def test_stale_revision_and_request_key_conflicts(api):
    contract, invoice, cdoc, idoc, approvals = workflow(api)
    data = body("term", term(rate="11"), cdoc, approvals[0]["id"])
    key = uuid4()
    first = review(api, contract, data, key=key)
    assert first.status_code == 201, first.text
    assert review(api, contract, data, key=key).json()["id"] == first.json()["id"]
    assert review(api, contract, data).status_code == 409
    data["reason"] = "Different request"
    assert review(api, contract, data, key=key).status_code == 409
    assert evaluate(api, invoice, revisions=[r["id"] for r in approvals]).status_code == 409


@pytest.mark.parametrize("role", ["owner", "admin", "analyst", "viewer"])
def test_role_authority_is_enforced_in_backend(api, role):
    contract, invoice, cdoc, idoc, approvals = workflow(api)
    set_role(api, role)
    approved = review(api, contract, body("term", term(rate="11"), cdoc, approvals[0]["id"]))
    assert approved.status_code == (201 if role in {"owner", "admin"} else 403)
    result = evaluate(api, invoice)
    assert result.status_code == (200 if role in {"owner", "admin"} else 403)
    prepared = review(
        api,
        invoice,
        body("billing_scope", bill(key="proposed", members=("proposed",)), idoc, state="prepared"),
    )
    assert prepared.status_code == (403 if role == "viewer" else 201)


@pytest.mark.parametrize("suffix", ["/sources", "/evaluations", "/summary", "/audit"])
def test_missing_auth_and_cross_tenant_reads(api, suffix):
    assert api["client"].get(root(api) + suffix).status_code == 401
    assert api["client"].get(root(api, "b") + suffix, headers=headers(api)).status_code == 404


def test_cross_tenant_ids_evidence_and_associations_fail(api):
    contract, invoice, cdoc, idoc, approvals = workflow(api)
    set_role(api, "owner", "b")
    for path in [f"/sources/{contract}", f"/sources/{invoice}/history"]:
        assert (
            api["client"].get(root(api, "b") + path, headers=headers(api, "b")).status_code == 404
        )
    foreign = upload(api, org="b", subject="b", content=b"other,data\nB,12\n").json()["id"]
    assert (
        review(
            api, contract, body("term", term(rate="11"), foreign, approvals[0]["id"])
        ).status_code
        == 404
    )
    assert (
        api["client"]
        .post(
            root(api, "b") + f"/sources/{invoice}/evaluate",
            headers=headers(api, "b"),
            json={"scope_key": "line-1", "expected_revisions": []},
        )
        .status_code
        == 404
    )


def test_historical_outputs_and_audit_are_immutable_at_database(api):
    contract, invoice, cdoc, idoc, approvals = workflow(api)
    result = evaluate(api, invoice).json()
    for table, update in [
        ("financial_evaluations", "potential=1"),
        ("financial_revisions", "state='revoked'"),
        ("financial_audit", "action='tampered'"),
    ]:
        with pytest.raises(DBAPIError, match="immutable"), api["session"].begin_nested():
            api["session"].execute(
                text(f"UPDATE {table} SET {update} WHERE organization_id=:org"),
                {"org": api["orgs"]["a"]},
            )
    assert api["session"].get(FinancialEvaluation, UUID(result["id"])).potential == 200


def test_F20_unique_supplier_or_candidates_do_not_create_a_match(api):
    contract, invoice, cdoc, idoc, approvals = workflow(api)
    association = approvals[3]
    revoked = review(
        api,
        invoice,
        body("association", association["payload"]["value"], idoc, association["id"], "revoked"),
    )
    assert revoked.status_code == 201, revoked.text
    candidate, candidate_doc = create(api, "contract", b"reference,price\nC-2,12\n")
    assert review(api, candidate, body("term", term(rate="12"), candidate_doc)).status_code == 201
    result = evaluate(api, invoice).json()
    assert result["reason_code"] == "AMBIGUOUS_MATCH" and result["potential"] is None
    assert result["snapshot"]["match_outcome"] == "AMBIGUOUS"


def test_known_missing_packet_prevents_false_positive(api):
    contract, invoice, cdoc, idoc, approvals = workflow(api)
    data = packet(
        documents=({"document_id": UUID(cdoc), "role": "master"},), known_missing=("schedule",)
    )
    assert review(api, contract, body("packet", data, cdoc, approvals[1]["id"])).status_code == 201
    result = evaluate(api, invoice).json()
    assert result["reason_code"] == "PACKET_INCOMPLETE" and result["potential"] is None


def test_rerun_and_review_retry_preserve_stable_business_identity(api):
    contract, invoice, cdoc, idoc, approvals = workflow(api)
    original = evaluate(api, invoice).json()
    reprocessed = api["client"].post(
        f"/api/v1/organizations/{api['orgs']['a']}/documents/{idoc}/reprocess",
        headers={**headers(api), "Idempotency-Key": str(uuid4())},
    )
    assert reprocessed.status_code == 200, reprocessed.text
    assert evaluate(api, invoice).json()["id"] == original["id"]
    assert api["session"].scalar(select(func.count()).select_from(ReviewedFinancialSource)) == 2
    data = body("billing_scope", bill(), idoc, approvals[2]["id"])
    key = uuid4()
    first = review(api, invoice, data, key=key)
    assert first.status_code == 201, first.text
    assert review(api, invoice, data, key=key).json()["id"] == first.json()["id"]
    assert evaluate(api, invoice).json()["id"] != original["id"]


def test_prepared_correction_blocks_current_authority_until_reviewed(api):
    contract, invoice, cdoc, idoc, approvals = workflow(api)
    original = evaluate(api, invoice).json()
    proposed = review(
        api, contract, body("term", term(rate="11"), cdoc, approvals[0]["id"], "prepared")
    )
    assert proposed.status_code == 201, proposed.text
    result = evaluate(api, invoice).json()
    assert result["potential"] is None
    historic = (
        api["client"].get(root(api) + f"/evaluations/{original['id']}", headers=headers(api)).json()
    )
    assert historic["stale"] and historic["potential"] == original["potential"]


def test_audit_cannot_be_forged_and_referenced_source_cannot_be_changed(api):
    contract, invoice, cdoc, idoc, approvals = workflow(api)
    with pytest.raises(DBAPIError, match="authoritative record"), api["session"].begin_nested():
        api["session"].execute(
            text(
                "INSERT INTO financial_audit "
                "(id,organization_id,actor_id,action,target_id,detail) "
                "VALUES (:id,:org,:actor,'forged',:target,'{}'::jsonb)"
            ),
            {
                "id": uuid4(),
                "org": api["orgs"]["a"],
                "actor": api["users"]["a"].id,
                "target": uuid4(),
            },
        )
    with pytest.raises(DBAPIError, match="immutable"), api["session"].begin_nested():
        api["session"].execute(
            text("UPDATE documents SET sha256=:sha WHERE id=:id"),
            {"sha": "d" * 64, "id": UUID(idoc)},
        )


def test_summary_keeps_blocked_unknown_and_does_not_net_undercharges(api):
    contract, invoice, cdoc, idoc, approvals = workflow(api)
    evaluate(api, invoice)
    first = api["client"].get(root(api) + "/summary", headers=headers(api)).json()
    assert first["potential_by_currency"] == {"USD": "200.000000"}
    assert (
        review(
            api,
            invoice,
            body(
                "billing_scope",
                bill(
                    key="other",
                    members=("other",),
                    quantity="100",
                    billed_rate="9",
                    billed_gross="900",
                    posted_amount="900",
                ),
                idoc,
            ),
        ).status_code
        == 201
    )
    # Authority set changes conservatively stale the prior view, then both disjoint scopes reassess.
    evaluate(api, invoice)
    under = evaluate(api, invoice, scope="other").json()
    assert under["outcome"] == "UNDERCHARGE"
    summary = api["client"].get(root(api) + "/summary", headers=headers(api)).json()
    assert summary["potential_by_currency"] == {"USD": "200.000000"}
    assert summary["counts"]["assessed"] == 1


@pytest.mark.parametrize("role", ["analyst", "viewer"])
@pytest.mark.parametrize("index", [0, 1, 2, 3])
def test_every_approval_and_revocation_family_requires_owner_or_admin(api, role, index):
    contract, invoice, cdoc, idoc, approvals = workflow(api)
    set_role(api, role)
    record = approvals[index]
    sid = contract if index in (0, 1) else invoice
    doc = cdoc if index in (0, 1) else idoc
    for state in ("approved", "revoked"):
        response = review(
            api, sid, body(record["kind"], record["payload"]["value"], doc, record["id"], state)
        )
        assert response.status_code == 403


def test_discount_base_requires_governing_source_and_combined_bundle_is_one_finding(api):
    from app.financial.schema import BaseComponent
    from tests.test_financial_engine import discount

    contract, invoice, cdoc, idoc, approvals = workflow(api)
    data = body("term", discount("10"), cdoc)
    assert review(api, contract, data).status_code == 201
    combined = evaluate(api, invoice).json()
    assert combined["potential"] == "300.000000"
    assert set(combined["snapshot"]["calculation"]["rules"]) == {
        "unit_price",
        "percentage_discount",
    }
    # Use a separate approved scope for the standalone discount. Revoking the
    # first scope's price must block that scope rather than silently discard it.
    assert (
        review(
            api, contract, body("term", discount("10", key="discount-B", scope="SKU-B"), cdoc)
        ).status_code
        == 201
    )
    assert (
        review(
            api,
            contract,
            body(
                "packet",
                packet(
                    documents=({"document_id": UUID(cdoc), "role": "master"},),
                    scopes=("SKU-A", "SKU-B"),
                ),
                cdoc,
                approvals[1]["id"],
            ),
        ).status_code
        == 201
    )
    billing = bill(
        scope="SKU-B",
        quantity=None,
        billed_rate=None,
        base_complete=True,
        base_components=(BaseComponent(key="line-1", contractual_gross="1000", eligible=True),),
    )
    invoice_data = body("billing_scope", billing, idoc, approvals[2]["id"])
    first = review(api, invoice, invoice_data)
    assert first.status_code == 201, first.text
    assert evaluate(api, invoice).json()["reason_code"] == "DISCOUNT_BASE_UNRESOLVED"
    paths = [
        p for p in invoice_data["evidence"][0]["supports"] if p.startswith("/base_components/")
    ]
    invoice_data["evidence"].append(
        {**invoice_data["evidence"][0], "document_id": cdoc, "supports": paths}
    )
    invoice_data["expected_revision"] = first.json()["id"]
    result = review(api, invoice, invoice_data)
    assert result.status_code == 201, result.text
    assert evaluate(api, invoice).json()["potential"] == "300.000000"


@pytest.mark.parametrize("method", ["exact_reference", "approved_po"])
def test_strong_reference_matching_requires_approved_consistent_identifiers(api, method):
    contract, invoice, cdoc, idoc, approvals = workflow(api)
    field = "contract_reference" if method == "exact_reference" else "po_reference"
    refs = {"contract_reference": None, "po_reference": None, field: "ID-1"}
    assert review(api, contract, body("reference", refs, cdoc)).status_code == 201
    billing = bill(
        **{"contract_references" if method == "exact_reference" else "po_references": ("ID-1",)}
    )
    reviewed = review(api, invoice, body("billing_scope", billing, idoc, approvals[2]["id"]))
    assert reviewed.status_code == 201
    association = {
        "contract_source_id": contract,
        "method": method,
        "identifier": "ID-1",
        "rationale": "Explicit approved identity relationship",
    }
    assert (
        review(api, invoice, body("association", association, idoc, approvals[3]["id"])).status_code
        == 201
    )
    assert evaluate(api, invoice).json()["potential"] == "200.000000"
    conflict = billing.model_copy(
        update={
            "contract_references" if method == "exact_reference" else "po_references": ("ID-2",)
        }
    )
    assert (
        review(
            api, invoice, body("billing_scope", conflict, idoc, reviewed.json()["id"])
        ).status_code
        == 201
    )
    assert evaluate(api, invoice).json()["reason_code"] == "CONFLICTING_IDENTIFIERS"


@pytest.mark.parametrize("role", ["analyst", "viewer"])
def test_finding_validation_and_dismissal_are_protected(api, role):
    contract, invoice, cdoc, idoc, approvals = workflow(api)
    result = evaluate(api, invoice).json()
    set_role(api, role)
    for status in ("confirmed", "false_positive", "needs_review"):
        response = api["client"].post(
            root(api) + f"/evaluations/{result['id']}/decision",
            headers=headers(api),
            json={"status": status, "reason": "Reviewed", "expected_decision": None},
        )
        assert response.status_code == 403


def test_period_allocations_reconcile_both_quantity_and_amount_to_parent(api):
    from datetime import date

    contract, invoice, cdoc, idoc, approvals = workflow(api)
    old = term(rate="18.4", effective_to=date(2026, 7, 1))
    assert review(api, contract, body("term", old, cdoc, approvals[0]["id"])).status_code == 201
    new = term(key="amendment", rate="19.1", effective_from=date(2026, 7, 1), supersedes=("price",))
    assert review(api, contract, body("term", new, cdoc)).status_code == 201
    parent = bill(
        key="parent",
        members=("parent",),
        quantity="1000",
        billed_rate="19.2",
        billed_gross="19200",
        posted_amount="19200",
        service_to=date(2026, 7, 15),
    )
    assert review(api, invoice, body("billing_scope", parent, idoc)).status_code == 201
    first = bill(
        key="before",
        members=("before",),
        quantity="400",
        billed_rate="19.2",
        billed_gross="7680",
        posted_amount="7680",
        service_to=date(2026, 7, 1),
        allocation_parent="parent",
    )
    assert review(api, invoice, body("billing_scope", first, idoc)).status_code == 201
    assert evaluate(api, invoice, scope="before").json()["reason_code"] == "ALLOCATION_REQUIRED"
    second = bill(
        key="after",
        members=("after",),
        quantity="600",
        billed_rate="19.2",
        billed_gross="11520",
        posted_amount="11520",
        service_from=date(2026, 7, 1),
        service_to=date(2026, 7, 15),
        allocation_parent="parent",
    )
    assert review(api, invoice, body("billing_scope", second, idoc)).status_code == 201
    a = evaluate(api, invoice, scope="before").json()
    b = evaluate(api, invoice, scope="after").json()
    assert a["potential"] == "320.000000" and b["potential"] == "60.000000"
    assert evaluate(api, invoice, scope="parent").json()["reason_code"] == "OVERLAPPING_SCOPE"


def test_disjoint_review_and_filename_metadata_do_not_reopen_a_dismissed_finding(api):
    contract, invoice, cdoc, idoc, approvals = workflow(api)
    original = evaluate(api, invoice).json()
    decision = api["client"].post(
        root(api) + f"/evaluations/{original['id']}/decision",
        headers=headers(api),
        json={
            "status": "false_positive",
            "reason": "Reviewed conclusion",
            "expected_decision": None,
        },
    )
    assert decision.status_code == 201
    assert (
        review(
            api, invoice, body("billing_scope", bill(key="disjoint", members=("disjoint",)), idoc)
        ).status_code
        == 201
    )
    api["session"].execute(
        text("UPDATE documents SET original_filename='reviewed.csv' WHERE id=:id"),
        {"id": UUID(idoc)},
    )
    result = evaluate(api, invoice).json()
    assert (
        result["id"] == original["id"]
        and result["status"] == "false_positive"
        and not result["stale"]
    )
    audit = api["session"].scalar(
        select(FinancialAudit).where(FinancialAudit.action == "evaluation.created")
    )
    assert audit.detail["role_at_action"] == "owner"


def test_owner_can_withdraw_unapproved_proposal_without_creating_false_authority(api):
    contract, invoice, cdoc, idoc, approvals = workflow(api)
    original = evaluate(api, invoice).json()
    api["client"].post(
        root(api) + f"/evaluations/{original['id']}/decision",
        headers=headers(api),
        json={
            "status": "false_positive",
            "reason": "Reviewed conclusion",
            "expected_decision": None,
        },
    )
    proposed = review(
        api, contract, body("term", term(key="new-proposal", rate="11"), cdoc, state="prepared")
    )
    assert proposed.status_code == 201, proposed.text
    assert evaluate(api, invoice).json()["potential"] is None
    withdrawn = review(
        api,
        contract,
        body("term", term(key="new-proposal", rate="11"), cdoc, proposed.json()["id"], "revoked"),
    )
    assert withdrawn.status_code == 201, withdrawn.text
    assert not withdrawn.json()["payload"]["has_approval_history"]
    result = evaluate(api, invoice).json()
    assert result["id"] == original["id"] and result["status"] == "false_positive"


def test_composite_evidence_foreign_keys_reject_cross_tenant_sources(api):
    from sqlalchemy.exc import IntegrityError

    from app.financial.models import FinancialRevisionEvidence

    contract, invoice, cdoc, idoc, approvals = workflow(api)
    foreign = upload(api, org="b", subject="b", content=b"foreign,invoice\nB,12\n").json()["id"]
    with pytest.raises(IntegrityError), api["session"].begin_nested():
        api["session"].add(
            FinancialRevisionEvidence(
                organization_id=api["orgs"]["a"],
                revision_id=UUID(approvals[2]["id"]),
                document_id=UUID(foreign),
                run_id=None,
                field_id=None,
                detail={},
            )
        )
        api["session"].flush()
