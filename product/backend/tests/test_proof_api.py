import hashlib
from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app.db.models import Document
from app.financial.models import FinancialAudit, FinancialEvaluation, FinancialRevision
from app.proof.canonical import canonical, fingerprint, snapshot_digest
from app.proof.models import ProofArtifact, ProofBinding, ProofEvent, ProofPackage, ProofRequest
from app.proof.schema import OperationalLimits
from tests.financial_fixtures import bill, term
from tests.test_documents import api as api
from tests.test_documents import headers
from tests.test_financial_api import body, evaluate, review, set_role, workflow
from tests.test_financial_api import root as financial_root

pytestmark = pytest.mark.integration


def root(api, org="a"):
    return f"/api/v1/organizations/{api['orgs'][org]}/proof"


def post(api, path, data, *, key=None, subject="a", org="a"):
    return api["client"].post(
        root(api, org) + path,
        json=data,
        headers={**headers(api, subject), "Idempotency-Key": str(key or uuid4())},
    )


def setup(api):
    contract, invoice, cdoc, idoc, approvals = workflow(api)
    response = evaluate(api, invoice)
    assert response.status_code == 200, response.text
    return contract, invoice, cdoc, idoc, approvals, response.json()


def generate(api, assessment, **changes):
    data = {"expected_fingerprint": assessment["fingerprint"], **changes}
    return post(api, f"/evaluations/{assessment['id']}/generate", data)


def issued(api, assessment):
    response = generate(api, assessment)
    assert response.status_code == 200, response.text
    package_id = response.json()["package_id"]
    response = api["client"].get(root(api) + f"/packages/{package_id}", headers=headers(api))
    assert response.status_code == 200, response.text
    return response.json()


def test_real_source_chain_exact_outputs_c01_c10_and_no_recalculation(api, monkeypatch):
    *_, assessment = setup(api)
    from app.financial import engine, service

    def forbidden(*args, **kwargs):
        raise AssertionError("Proof assembly must not invoke calculation or compilation")

    monkeypatch.setattr(engine, "evaluate", forbidden)
    monkeypatch.setattr(service, "run_engine", forbidden)
    package = issued(api, assessment)
    core = package["core"]
    assert package["issued_completeness"] == "COMPLETE"
    assert all(c["passed"] for c in core["completeness"]["requirements"].values())
    assert set(core["completeness"]["requirements"]) == {f"C{i:02}" for i in range(1, 11)}
    assert core["financial"]["potential"] == "200.000000"
    assert core["identity"]["finding_id"] == assessment["id"]
    assert core["evaluation_snapshot_digest"] == snapshot_digest(assessment["snapshot"])
    assert fingerprint(core) == package["fingerprint"]
    bindings = core["calculation"]["bindings"]
    assert any(b["source"]["run_id"] and b["source"]["field_id"] for b in bindings)
    assert any(b["source"]["manual"] and b["source"]["run_id"] is None for b in bindings)
    assert {b["typed_input"]["type"] for b in bindings} >= {
        "quantity",
        "unit_price",
        "money",
        "date",
        "boolean",
        "null",
    }
    assert api["session"].scalar(select(func.count()).select_from(ProofBinding)) == len(bindings)
    assert api["session"].scalar(select(func.count()).select_from(FinancialEvaluation)) == 1
    assert "storage_key" not in canonical(core).decode()


def test_retry_semantic_deduplication_request_conflict_and_one_issuance_audit(api):
    *_, assessment = setup(api)
    key = uuid4()
    path = f"/evaluations/{assessment['id']}/generate"
    data = {"expected_fingerprint": assessment["fingerprint"]}
    first = post(api, path, data, key=key)
    assert first.status_code == 200, first.text
    assert post(api, path, data, key=key).json() == first.json()
    assert generate(api, assessment).json()["package_id"] == first.json()["package_id"]
    conflict = post(api, path, {**data, "mode": "HISTORICAL"}, key=key)
    assert (
        conflict.status_code == 409 and conflict.json()["error"]["code"] == "proof_request_conflict"
    )
    assert api["session"].scalar(select(func.count()).select_from(ProofPackage)) == 1
    actions = api["session"].scalars(select(FinancialAudit.action)).all()
    assert actions.count("proof.issued") == 1 and "proof.operation.failed" in actions


@pytest.mark.parametrize(
    "role,can_generate", [("owner", True), ("admin", True), ("analyst", True), ("viewer", False)]
)
def test_current_role_generation_read_and_export_matrix(api, role, can_generate):
    *_, assessment = setup(api)
    package = issued(api, assessment)
    set_role(api, role)
    assert generate(api, assessment).status_code == (200 if can_generate else 403)
    result = api["client"].get(root(api) + f"/packages/{package['id']}", headers=headers(api))
    assert result.status_code == 200
    export = post(api, f"/packages/{package['id']}/export", {})
    assert export.status_code == (200 if role in {"owner", "admin"} else 403)


@pytest.mark.parametrize("role", ["analyst", "viewer"])
@pytest.mark.parametrize("kind", ["review.finalized", "disclosure.approved"])
def test_final_human_authority_is_not_granted_to_analysts_or_viewers(api, role, kind):
    *_, assessment = setup(api)
    package = issued(api, assessment)
    set_role(api, role)
    data = (
        {"kind": kind, "text": "Attributed human judgment", "status": "REVIEWED"}
        if kind.startswith("review")
        else {"kind": kind, "text": "Approved disclosure", "previous_id": str(uuid4())}
    )
    assert post(api, f"/packages/{package['id']}/events", data).status_code == 403


def test_annotation_review_are_separate_audited_nonfinancial_revisions(api):
    *_, assessment = setup(api)
    package = issued(api, assessment)
    set_role(api, "analyst")
    path = f"/packages/{package['id']}/events"
    first = post(api, path, {"kind": "annotation.appended", "text": "Check supplier reference"})
    assert first.status_code == 200, first.text
    revision = post(
        api,
        path,
        {
            "kind": "annotation.appended",
            "text": "Reference checked",
            "previous_id": first.json()["event_id"],
        },
    )
    assert revision.status_code == 200
    assert (
        post(
            api,
            path,
            {
                "kind": "annotation.retracted",
                "text": "Retracted note",
                "previous_id": first.json()["event_id"],
            },
        ).status_code
        == 409
    )
    assert (
        post(
            api, path, {"kind": "annotation.appended", "text": "x", "potential": "999"}
        ).status_code
        == 422
    )
    assert (
        post(
            api,
            path,
            {"kind": "review.proposed", "text": "Evidence review proposal", "status": "REVIEWED"},
        ).status_code
        == 200
    )
    set_role(api, "owner")
    human = post(
        api,
        path,
        {"kind": "review.finalized", "text": "Proof evidence reviewed", "status": "REVIEWED"},
    )
    assert human.status_code == 200, human.text
    assert (
        post(
            api,
            path,
            {
                "kind": "review.finalized",
                "text": "Concurrent stale review",
                "status": "NEEDS_REVIEW",
            },
        ).status_code
        == 409
    )
    after = api["client"].get(root(api) + f"/packages/{package['id']}", headers=headers(api)).json()
    assert after["overlays"]["human_review"] == "REVIEWED"
    assert after["overlays"]["finding_decision"] == "detected"
    assert after["issued_completeness"] == "COMPLETE"
    assert after["core"] == package["core"] and after["envelope"] == package["envelope"]


def test_actual_bytes_mismatch_initial_issuance_and_all_download_paths_are_quarantined(api):
    _, _, cdoc, _, _, assessment = setup(api)
    doc = api["session"].get(Document, UUID(cdoc))
    (api["root"] / doc.storage_key).write_bytes(b"corrupt original")
    response = generate(api, assessment)
    assert (
        response.status_code == 409
        and response.json()["error"]["code"] == "proof_integrity_failure"
    )
    assert api["session"].scalar(select(func.count()).select_from(ProofPackage)) == 0
    generic = api["client"].get(
        f"/api/v1/organizations/{api['orgs']['a']}/documents/{cdoc}/content", headers=headers(api)
    )
    assert generic.status_code == 409 and b"corrupt original" not in generic.content


def test_issued_historical_completeness_survives_missing_and_changed_bytes_with_audit(api):
    _, _, cdoc, _, _, assessment = setup(api)
    package = issued(api, assessment)
    doc = api["session"].get(Document, UUID(cdoc))
    path = api["root"] / doc.storage_key
    original = path.read_bytes()
    path.unlink()
    response = api["client"].get(root(api) + f"/packages/{package['id']}", headers=headers(api))
    assert response.status_code == 200, response.text
    after = response.json()
    assert after["issued_completeness"] == "COMPLETE" and after["core"] == package["core"]
    assert {s["status"] for s in after["overlays"]["evidence_availability"]} == {
        "UNAVAILABLE",
        "AVAILABLE_VERIFIED",
    }
    assert generate(api, assessment).json()["package_id"] == package["id"]
    path.write_bytes(b"tampered")
    after = api["client"].get(root(api) + f"/packages/{package['id']}", headers=headers(api)).json()
    assert any(s["status"] == "MISMATCH" for s in after["overlays"]["evidence_availability"])
    download = api["client"].get(
        root(api) + f"/packages/{package['id']}/sources/{cdoc}/download", headers=headers(api)
    )
    assert download.status_code == 409 and b"tampered" not in download.content
    events = (
        api["session"]
        .scalars(select(ProofEvent).where(ProofEvent.kind == "integrity.observed"))
        .all()
    )
    assert [e.detail["status"] for e in events] == ["UNAVAILABLE", "MISMATCH"]
    path.write_bytes(original)
    assert (
        api["client"]
        .get(root(api) + f"/packages/{package['id']}/sources/{cdoc}/download", headers=headers(api))
        .content
        == original
    )


def test_repaired_identical_source_has_explicit_new_content_identity_same_evaluation(api):
    _, _, cdoc, _, _, assessment = setup(api)
    doc = api["session"].get(Document, UUID(cdoc))
    path = api["root"] / doc.storage_key
    original = path.read_bytes()
    path.unlink()
    package = issued(api, assessment)
    assert package["issued_completeness"] == "INCOMPLETE"
    path.write_bytes(original)
    assert generate(api, assessment).json()["package_id"] == package["id"]
    response = generate(
        api, assessment, previous_package_id=package["id"], revision_reason="REPAIRED_EVIDENCE"
    )
    assert response.status_code == 200, response.text
    repaired = (
        api["client"]
        .get(root(api) + f"/packages/{response.json()['package_id']}", headers=headers(api))
        .json()
    )
    assert repaired["number"] == 2 and repaired["issued_completeness"] == "COMPLETE"
    assert repaired["financial"] == package["financial"]
    assert repaired["identity"]["evaluation_id"] == assessment["id"]
    assert (
        generate(
            api, assessment, previous_package_id=package["id"], revision_reason="REPAIRED_EVIDENCE"
        ).status_code
        == 409
    )
    assert api["session"].scalar(select(func.count()).select_from(FinancialEvaluation)) == 1


def test_dismissal_and_material_approval_require_historical_mode_and_explicit_successor(api):
    contract, invoice, cdoc, _, approvals, assessment = setup(api)
    old = issued(api, assessment)
    dismiss = api["client"].post(
        financial_root(api) + f"/evaluations/{assessment['id']}/decision",
        headers=headers(api),
        json={
            "status": "false_positive",
            "reason": "Historical comparison reviewed",
            "expected_decision": None,
        },
    )
    assert dismiss.status_code == 201
    assert generate(api, assessment).status_code == 409
    assert generate(api, assessment, mode="HISTORICAL").json()["package_id"] == old["id"]
    change = review(api, contract, body("term", term(rate="11"), cdoc, previous=approvals[0]["id"]))
    assert change.status_code == 201, change.text
    fresh = evaluate(api, invoice).json()
    new = issued(api, fresh)
    after = api["client"].get(root(api) + f"/packages/{old['id']}", headers=headers(api)).json()
    assert after["overlays"]["financial_currentness"] == "STALE"
    assert after["overlays"]["finding_decision"] == "false_positive"
    assert after["overlays"]["successor_id"] is None
    relation = post(
        api,
        f"/packages/{old['id']}/successor",
        {"successor_id": new["id"], "reason": "Explicit same-scope reviewed successor"},
    )
    assert relation.status_code == 200, relation.text
    assert (
        post(
            api,
            f"/packages/{new['id']}/successor",
            {"successor_id": old["id"], "reason": "Forbidden cycle"},
        ).status_code
        == 409
    )
    after = api["client"].get(root(api) + f"/packages/{old['id']}", headers=headers(api)).json()
    assert after["core"] == old["core"] and after["overlays"]["successor_id"] == new["id"]


def test_export_actual_checksum_private_download_current_membership_and_recursive_redaction(api):
    contract, invoice, cdoc, _, approvals, _ = setup(api)
    data = body("term", term(), cdoc, previous=approvals[0]["id"])
    data["evidence"][0]["quote"] = "Synthetic private bank account SECRET-IBAN-123"
    assert review(api, contract, data).status_code == 201
    assessment = evaluate(api, invoice).json()
    package = issued(api, assessment)
    core_before = deepcopy(package["core"])
    leaf = next(
        path
        for path, value in __import__("app.proof.canonical", fromlist=["leaves"])
        .leaves(core_before)
        .items()
        if value == data["evidence"][0]["quote"]
    )
    set_role(api, "analyst")
    proposal = post(
        api,
        f"/packages/{package['id']}/events",
        {"kind": "disclosure.proposed", "text": "Hide unnecessary bank detail", "paths": [leaf]},
    )
    assert proposal.status_code == 200, proposal.text
    set_role(api, "owner")
    approval = post(
        api,
        f"/packages/{package['id']}/events",
        {
            "kind": "disclosure.approved",
            "text": "Disclosure reviewed",
            "previous_id": proposal.json()["event_id"],
        },
    )
    assert approval.status_code == 200, approval.text
    exported = post(
        api, f"/packages/{package['id']}/export", {"disclosure_id": approval.json()["event_id"]}
    )
    assert exported.status_code == 200, exported.text
    artifact = exported.json()
    response = api["client"].get(
        root(api) + f"/artifacts/{artifact['artifact_id']}/download", headers=headers(api)
    )
    assert response.status_code == 200
    assert b"SECRET-IBAN-123" not in response.content
    for source in core_before["sources"]:
        assert source["sha256"] not in response.text
    assert core_before["evaluation_snapshot_digest"] not in response.text
    assert (
        hashlib.sha256(response.content).hexdigest()
        == artifact["content_hash"]
        == response.headers["X-Artifact-SHA256"]
    )
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["disclosure"]["verification"] == "LIMITED_VERIFICATION"
    assert (
        response.json()["disclosure"]["content"]["completeness"]["disclosed_verification"]
        == "LIMITED_VERIFICATION"
    )
    assert "state" not in response.json()["disclosure"]["content"]["completeness"]
    assert response.json()["disclosure"]["parent_manifest_fingerprint"] == package["fingerprint"]
    assert "core" not in response.json() and "envelope" not in response.json()
    assert api["session"].get(ProofPackage, UUID(package["id"])).core == core_before
    set_role(api, "analyst")
    assert (
        api["client"]
        .get(root(api) + f"/artifacts/{artifact['artifact_id']}/download", headers=headers(api))
        .status_code
        == 403
    )
    other = api["client"].get(
        root(api, "b") + f"/artifacts/{artifact['artifact_id']}/download", headers=headers(api, "b")
    )
    assert other.status_code in {403, 404} and artifact["content_hash"] not in other.text


@pytest.mark.parametrize(
    "outcome,value", [("NO_OVERCHARGE", "1000"), ("UNDERCHARGE", "900"), ("NEEDS_REVIEW", None)]
)
def test_nonpositive_and_blocked_evidence_never_gain_finding_identity_or_unknown_zero(
    api, outcome, value
):
    _, invoice, _, idoc, approvals, _ = setup(api)
    data = (
        bill(billed_rate="10" if value == "1000" else "9", billed_gross=value, posted_amount=value)
        if value
        else bill(quantity=None)
    )
    assert (
        review(
            api, invoice, body("billing_scope", data, idoc, previous=approvals[2]["id"])
        ).status_code
        == 201
    )
    assessment = evaluate(api, invoice).json()
    assert assessment["outcome"] == outcome
    package = issued(api, assessment)
    assert package["identity"]["finding_id"] is None
    assert package["financial"]["potential"] is None
    if outcome == "NEEDS_REVIEW":
        assert all(
            package["financial"][key] is None
            for key in ("expected", "actual", "discrepancy", "potential")
        )
        assert package["identity"]["kind"] == "BLOCKED_ASSESSMENT_EVIDENCE"
    elif outcome == "NO_OVERCHARGE":
        assert package["financial"]["discrepancy"] == "0.000000"
    else:
        assert package["financial"]["discrepancy"] == "-100.000000"


@pytest.mark.parametrize(
    "name,value",
    [
        ("revisions", 1),
        ("documents", 1),
        ("bindings", 1),
        ("canonical_bytes", 100),
        ("source_bytes", 1),
    ],
)
def test_operational_bounds_fail_explicitly_without_partial_proof(api, name, value):
    *_, assessment = setup(api)
    api["app"].state.settings.proof_limits = OperationalLimits(**{name: value})
    result = generate(api, assessment)
    assert result.status_code == 413, result.text
    assert result.json()["error"]["code"] == "proof_resource_limit"
    assert api["session"].scalar(select(func.count()).select_from(ProofPackage)) == 0
    assert api["session"].scalar(select(func.count()).select_from(ProofRequest)) == 1
    assert api["session"].scalar(select(func.count()).select_from(FinancialEvaluation)) == 1


def test_json_annotation_history_and_rate_bounds(api):
    *_, assessment = setup(api)
    package = issued(api, assessment)
    path = f"/packages/{package['id']}/events"
    assert post(api, path, {"kind": "annotation.appended", "text": "a" * 4001}).status_code == 422
    assert post(api, path, {"kind": "annotation.appended", "text": "a\x00b"}).status_code == 422
    raw = api["client"].post(
        root(api) + path,
        headers={
            **headers(api),
            "Idempotency-Key": str(uuid4()),
            "Content-Type": "application/json",
        },
        content=b'{"kind":"annotation.appended","text":"a","text":"b"}',
    )
    assert raw.status_code == 422 and raw.json()["error"]["code"] == "proof_invalid_json"
    oversized = api["client"].post(
        root(api) + path,
        headers={**headers(api), "Idempotency-Key": str(uuid4())},
        content=b"x" * (1024 * 1024 + 1),
    )
    assert oversized.status_code == 413
    assert (
        api["client"]
        .get(root(api) + f"/packages/{package['id']}/history?limit=101", headers=headers(api))
        .status_code
        == 422
    )
    api["app"].state.settings.proof_limits = OperationalLimits(actor_operations_per_minute=1)
    assert post(api, f"/packages/{package['id']}/export", {}).status_code == 429


@pytest.mark.parametrize(
    "table",
    [
        "proof_packages",
        "proof_bindings",
        "proof_events",
        "proof_artifacts",
        "proof_requests",
        "proof_families",
    ],
)
def test_database_immutability_and_journal_origin(api, table):
    *_, assessment = setup(api)
    package = issued(api, assessment)
    assert (
        post(
            api,
            f"/packages/{package['id']}/events",
            {"kind": "annotation.appended", "text": "Immutable annotation"},
        ).status_code
        == 200
    )
    assert post(api, f"/packages/{package['id']}/export", {}).status_code == 200
    with pytest.raises(DBAPIError), api["session"].begin_nested():
        api["session"].execute(text(f"DELETE FROM {table}"))
    with pytest.raises(DBAPIError), api["session"].begin_nested():
        api["session"].execute(text(f"UPDATE {table} SET updated_at=now()"))
    with pytest.raises(DBAPIError), api["session"].begin_nested():
        api["session"].execute(
            text(
                "INSERT INTO financial_audit(id,organization_id,actor_id,action,target_id,detail) "
                "VALUES(:id,:org,:actor,'proof.issued',:target,'{}')"
            ),
            {
                "id": uuid4(),
                "org": api["orgs"]["a"],
                "actor": api["users"]["a"].id,
                "target": UUID(package["id"]),
            },
        )


def test_cross_tenant_package_source_history_and_generation_are_hidden(api):
    *_, assessment = setup(api)
    package = issued(api, assessment)
    set_role(api, "owner", subject="b")
    for path in [
        f"/packages/{package['id']}",
        f"/packages/{package['id']}/history",
        f"/evaluations/{assessment['id']}/packages",
    ]:
        response = api["client"].get(root(api, "b") + path, headers=headers(api, "b"))
        assert response.status_code == 404
        assert "200.000000" not in response.text and package["fingerprint"] not in response.text
    assert (
        post(
            api,
            f"/evaluations/{assessment['id']}/generate",
            {"expected_fingerprint": assessment["fingerprint"]},
            subject="b",
            org="b",
        ).status_code
        == 404
    )


def test_direct_artifact_forgery_and_proof_source_mutation_are_rejected(api):
    *_, assessment = setup(api)
    package = issued(api, assessment)
    forged = {"core": deepcopy(package["core"]), "envelope": package["envelope"]}
    forged["core"]["financial"]["potential"] = "999999.000000"
    raw = canonical(forged)
    with pytest.raises(DBAPIError), api["session"].begin_nested():
        api["session"].add(
            ProofArtifact(
                organization_id=api["orgs"]["a"],
                package_id=UUID(package["id"]),
                actor_id=api["users"]["a"].id,
                audit_id=uuid4(),
                content=raw,
                content_hash=hashlib.sha256(raw).hexdigest(),
            )
        )
        api["session"].flush()
    document_id = UUID(package["core"]["sources"][0]["document_id"])
    for statement in (
        "DELETE FROM documents WHERE id=:id",
        "UPDATE documents SET sha256=:sha WHERE id=:id",
    ):
        with pytest.raises(DBAPIError), api["session"].begin_nested():
            api["session"].execute(text(statement), {"id": document_id, "sha": "e" * 64})
    assert (
        api["session"].scalar(
            text(
                "SELECT count(*) FROM pg_trigger WHERE "
                "tgrelid='documents'::regclass AND tgname='proof_source_guard'"
            )
        )
        == 1
    )


def test_disclosure_hiding_current_actor_never_reintroduces_actor_in_export(api):
    *_, assessment = setup(api)
    package = issued(api, assessment)
    from app.proof.canonical import leaves

    actor = str(api["users"]["a"].id)
    path = next(path for path, value in leaves(package["core"]).items() if value == actor)
    proposal = post(
        api,
        f"/packages/{package['id']}/events",
        {"kind": "disclosure.proposed", "text": "Hide reviewer identity", "paths": [path]},
    )
    approval = post(
        api,
        f"/packages/{package['id']}/events",
        {
            "kind": "disclosure.approved",
            "text": "Approved separate limited disclosure",
            "previous_id": proposal.json()["event_id"],
        },
    )
    exported = post(
        api, f"/packages/{package['id']}/export", {"disclosure_id": approval.json()["event_id"]}
    )
    assert exported.status_code == 200, exported.text
    downloaded = api["client"].get(
        root(api) + f"/artifacts/{exported.json()['artifact_id']}/download", headers=headers(api)
    )
    assert downloaded.status_code == 200 and actor not in downloaded.text


def test_disclosure_and_final_review_reject_stale_predecessors(api):
    *_, assessment = setup(api)
    package = issued(api, assessment)
    path = f"/packages/{package['id']}/events"
    first = post(api, path, {"kind": "review.finalized", "text": "Reviewed", "status": "REVIEWED"})
    assert first.status_code == 200
    assert (
        post(
            api, path, {"kind": "review.finalized", "text": "Stale", "status": "NEEDS_REVIEW"}
        ).status_code
        == 409
    )
    assert (
        post(
            api,
            path,
            {
                "kind": "review.finalized",
                "text": "Updated review",
                "status": "NEEDS_REVIEW",
                "previous_id": first.json()["event_id"],
            },
        ).status_code
        == 200
    )


def test_only_pinned_extraction_identity_survives_rerun_and_filename_change(api):
    _, _, _, idoc, _, assessment = setup(api)
    package = issued(api, assessment)
    assert (
        api["client"]
        .post(
            f"/api/v1/organizations/{api['orgs']['a']}/documents/{idoc}/process",
            headers={**headers(api), "Idempotency-Key": str(uuid4())},
        )
        .status_code
        == 200
    )
    doc = api["session"].get(Document, UUID(idoc))
    doc.original_filename = "renamed-source.csv"
    api["session"].flush()
    after = api["client"].get(root(api) + f"/packages/{package['id']}", headers=headers(api)).json()
    assert after["core"] == package["core"]
    assert generate(api, assessment).json()["package_id"] == package["id"]
    assert api["session"].scalar(select(func.count()).select_from(FinancialRevision)) == 4


@pytest.mark.parametrize("collection", ["packages", "history", "artifacts"])
def test_history_reads_use_shared_capacity_and_work_budget(api, monkeypatch, collection):
    from app.proof import service
    from app.proof.budget import ProofError

    *_, assessment = setup(api)
    package = issued(api, assessment)

    def busy(session, access, budget):
        raise ProofError("proof_busy", "Tenant proof capacity is busy; retry later", 429)

    monkeypatch.setattr(service, "admit", busy)
    path = (
        f"/evaluations/{assessment['id']}/packages"
        if collection == "packages"
        else f"/packages/{package['id']}/{collection}"
    )
    response = api["client"].get(root(api) + path, headers=headers(api))
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "proof_busy"
    assert response.headers["retry-after"] == "60"


def test_disjoint_f32_proofs_preserve_320_and_60_without_an_aggregate_finding(api):
    from datetime import date

    contract, invoice, cdoc, idoc, approvals = workflow(api)
    old = term(rate="18.40", effective_to=date(2026, 7, 1))
    assert review(api, contract, body("term", old, cdoc, approvals[0]["id"])).status_code == 201
    amendment = term(
        key="amendment", rate="19.10", effective_from=date(2026, 7, 1), supersedes=("price",)
    )
    assert review(api, contract, body("term", amendment, cdoc)).status_code == 201
    scopes = [
        bill(
            key="parent",
            members=("parent",),
            quantity="1000",
            billed_rate="19.20",
            billed_gross="19200",
            posted_amount="19200",
            service_to=date(2026, 7, 15),
        ),
        bill(
            key="before",
            members=("before",),
            quantity="400",
            billed_rate="19.20",
            billed_gross="7680",
            posted_amount="7680",
            service_to=date(2026, 7, 1),
            allocation_parent="parent",
        ),
        bill(
            key="after",
            members=("after",),
            quantity="600",
            billed_rate="19.20",
            billed_gross="11520",
            posted_amount="11520",
            service_from=date(2026, 7, 1),
            service_to=date(2026, 7, 15),
            allocation_parent="parent",
        ),
    ]
    for value in scopes:
        assert review(api, invoice, body("billing_scope", value, idoc)).status_code == 201
    packages = [
        issued(api, evaluate(api, invoice, scope=scope).json()) for scope in ("before", "after")
    ]
    assert [p["financial"]["potential"] for p in packages] == ["320.000000", "60.000000"]
    assert [p["issued_completeness"] for p in packages] == ["COMPLETE", "COMPLETE"]
    assert api["session"].scalar(select(func.count()).select_from(ProofPackage)) == 2
    assert api["session"].scalar(select(func.count()).select_from(FinancialEvaluation)) == 2
    assert (
        post(
            api,
            f"/packages/{packages[0]['id']}/successor",
            {"successor_id": packages[1]["id"], "reason": "Cannot replace another period"},
        ).status_code
        == 409
    )
