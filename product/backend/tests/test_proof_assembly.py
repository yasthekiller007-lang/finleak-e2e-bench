from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace as Record
from uuid import UUID, uuid5

import pytest

from app.financial.engine import fingerprint as financial_fingerprint
from app.financial.service import inputs_snapshot
from app.proof.assemble import assemble
from app.proof.budget import Budget, ProofError
from app.proof.canonical import canonical, fingerprint, leaves, snapshot_digest
from app.proof.schema import OperationalLimits
from tests.financial_fixtures import ROUNDING, bill, packet, term
from tests.test_financial_api import body
from tests.test_financial_engine import run, vectors

NAMESPACE = UUID("00000000-0000-4000-8000-000000000001")
TIME = datetime(2026, 10, 3, tzinfo=UTC)


def identity(key):
    return uuid5(NAMESPACE, key)


def capture(terms, bill, governing_changes=None):
    org, actor, cdoc, idoc, cid, iid = [
        identity(k)
        for k in ("org", "actor", "contract", "invoice", "contract-source", "invoice-source")
    ]
    governing = packet(
        documents=({"document_id": cdoc, "role": "master"},), **(governing_changes or {})
    )
    # This calculation creates the fixture's historical Phase 4 truth BEFORE proof assembly.
    # The assembly itself receives records only and has no financial evaluator dependency.
    result = run(terms, bill, governing)
    revisions, evidence, audits = [], [], []
    data = [("term", value, cdoc, cid) for value in terms] + [
        ("packet", governing, cdoc, cid),
        ("billing_scope", bill, idoc, iid),
        (
            "association",
            {
                "contract_source_id": str(cid),
                "method": "manual",
                "identifier": None,
                "rationale": "Reviewed invoice obligation",
            },
            idoc,
            iid,
        ),
    ]
    for index, (kind, value, document_id, source_id) in enumerate(data):
        payload = body(kind, value, document_id)
        payload["knowledge_cutoff"] = TIME.isoformat()
        payload["has_approval_history"] = True
        sha = "a" * 64 if document_id == cdoc else "b" * 64
        detail = payload["evidence"][0] | {
            "sha256": sha,
            "document_type": "contract" if document_id == cdoc else "invoice",
            "available_at": TIME.isoformat(),
            "raw_value": payload["evidence"][0]["quote"],
            "normalized_candidate": None,
            "source_location": "Document-level reviewer citation",
            "run_id": None,
        }
        if kind == "packet":
            payload["document_hashes"] = [
                {"document_id": str(cdoc), "role": "master", "sha256": "a" * 64}
            ]
        revision = Record(
            id=identity(f"revision-{index}"),
            organization_id=org,
            source_id=source_id,
            kind=kind,
            key=payload["key"],
            number=1,
            state="approved",
            actor_id=actor,
            created_at=TIME,
            knowledge_cutoff=TIME,
            payload=payload,
            provenance=[detail],
        )
        revisions.append(revision)
        evidence.append(
            Record(
                id=identity(f"evidence-{index}"),
                organization_id=org,
                revision_id=revision.id,
                document_id=document_id,
                field_id=None,
                run_id=None,
                detail=deepcopy(detail),
            )
        )
        if kind == "billing_scope" and value.base_components:
            contract_citation = deepcopy(payload["evidence"][0])
            contract_citation.update(
                document_id=str(cdoc),
                quote="Reviewed contractual eligible base",
                supports=[
                    f"/base_components/{i}/contractual_gross"
                    for i in range(len(value.base_components))
                ],
            )
            payload["evidence"].append(contract_citation)
            contract_detail = (
                detail
                | contract_citation
                | {
                    "sha256": "a" * 64,
                    "document_type": "contract",
                    "raw_value": contract_citation["quote"],
                }
            )
            revision.provenance.append(contract_detail)
            evidence.append(
                Record(
                    id=identity(f"contract-base-evidence-{index}"),
                    organization_id=org,
                    revision_id=revision.id,
                    document_id=cdoc,
                    field_id=None,
                    run_id=None,
                    detail=deepcopy(contract_detail),
                )
            )
        audits.append(
            Record(
                id=identity(f"audit-{index}"),
                target_id=revision.id,
                actor_id=actor,
                action=f"review.{kind}.approved",
                detail={"role_at_action": "owner"},
            )
        )
    snapshot = {
        "schema": "financial-snapshot/1",
        "compiler": "reviewed-compiler/1",
        "rules": "core-bundle/1",
        "invoice_source_id": str(iid),
        "organization_id": str(org),
        "scope_key": bill.key,
        "inputs": deepcopy(inputs_snapshot(revisions)),
    }
    fp = financial_fingerprint(snapshot)
    snapshot.update(
        calculation_driving_revision_ids=[str(r.id) for r in revisions],
        calculation=result.trace,
        billing_scope=bill.model_dump(mode="json"),
        match_outcome="MATCHED",
        coverage="Only the approved named scope is assessed.",
    )
    evaluation = Record(
        id=identity("evaluation"),
        organization_id=org,
        invoice_source_id=iid,
        scope_key=bill.key,
        actor_id=actor,
        fingerprint=fp,
        outcome=result.outcome,
        reason_code=result.reason,
        explanation=result.explanation,
        currency=result.currency,
        created_at=TIME,
        snapshot=snapshot,
        **{
            k: Decimal(format(getattr(result, k), ".6f"))
            if getattr(result, k) is not None
            else None
            for k in ("expected", "actual", "discrepancy", "potential")
        },
    )
    audits.append(
        Record(
            id=identity("evaluation-audit"),
            target_id=evaluation.id,
            actor_id=actor,
            action="evaluation.created",
            detail={"role_at_action": "owner"},
        )
    )
    documents = [
        Record(
            id=doc, organization_id=org, sha256=sha, file_size=1, document_type=Record(value=kind)
        )
        for doc, sha, kind in [(cdoc, "a" * 64, "contract"), (idoc, "b" * 64, "invoice")]
    ]
    return [
        evaluation,
        revisions,
        evidence,
        documents,
        [],
        [],
        audits,
        {str(cdoc): "AVAILABLE_VERIFIED", str(idoc): "AVAILABLE_VERIFIED"},
        Budget(OperationalLimits()),
    ]


@pytest.mark.parametrize("name,terms,bill,outcome,delta", vectors())
def test_every_approved_financial_vector_is_explained_without_changing_money(
    name, terms, bill, outcome, delta
):
    args = capture(terms, bill)
    before = deepcopy(args[0].snapshot)
    core, normalized = assemble(*args)
    assert core["financial"]["reason_code"] == outcome, name
    assert core["completeness"]["state"] == "COMPLETE", (name, core["completeness"])
    assert core["financial"]["discrepancy"] == (
        format(Decimal(delta), ".6f") if delta is not None else None
    )
    assert core["financial"]["potential"] == (
        format(Decimal(delta), ".6f") if delta is not None and Decimal(delta) > 0 else None
    )
    assert (core["identity"]["finding_id"] is not None) == (
        delta is not None and Decimal(delta) > 0
    )
    assert core["evaluation_snapshot_digest"] == snapshot_digest(before)
    assert args[0].snapshot == before
    assert normalized
    if name == "F02":
        assert core["evaluation_snapshot_digest"] == (
            "c12ad2e313abc46a27b78343f2008e38d37b903dbc17a7028d7b4275707b7e90"
        )
        assert fingerprint(core) == (
            "09f90ad814103a836e95372170e9457ae0d1049669976708c4dbe6e59ac2d1bc"
        )
    if name == "F02":
        assert core["financial"]["expected"] == "803104.800000"
        assert core["financial"]["actual"] == "877304.700000"
        assert core["financial"]["potential"] == "74199.900000"
        values = [b["typed_input"]["value"] for b in core["calculation"]["bindings"]]
        assert {"18.40", "20.10", "43647"} <= set(v for v in values if isinstance(v, str))


@pytest.fixture
def sample():
    _, terms, bill, _, _ = vectors()[1]
    return capture(terms, bill)


@pytest.mark.parametrize(
    "gap",
    [
        "revision",
        "support",
        "review_audit",
        "evaluation_audit",
        "source",
        "lineage",
        "trace",
        "version",
        "packet_hash",
    ],
)
def test_missing_material_records_yield_named_incomplete_gaps(sample, gap):
    if gap == "revision":
        sample[1].pop(0)
    elif gap == "support":
        sample[0].snapshot["inputs"][0]["provenance"][0]["supports"].remove("/rate")
        sample[1][0].provenance[0]["supports"].remove("/rate")
        sample[2][0].detail["supports"].remove("/rate")
    elif gap == "review_audit":
        sample[6].pop(0)
    elif gap == "evaluation_audit":
        sample[6].pop()
    elif gap == "source":
        sample[7][str(sample[3][0].id)] = "UNAVAILABLE"
    elif gap == "lineage":
        sample[2].pop(0)
    elif gap == "trace":
        sample[0].snapshot["calculation"] = None
    elif gap == "version":
        sample[0].snapshot["compiler"] = "unknown-compiler/9"
    else:
        sample[0].snapshot["inputs"][1]["payload"]["document_hashes"] = []
        sample[1][1].payload["document_hashes"] = []
    if gap in {"support", "packet_hash"}:
        # Model an honestly incomplete historical snapshot, not later tampering.
        sample[0].fingerprint = financial_fingerprint(
            {
                key: sample[0].snapshot[key]
                for key in (
                    "schema",
                    "compiler",
                    "rules",
                    "invoice_source_id",
                    "organization_id",
                    "scope_key",
                    "inputs",
                )
            }
        )
    core, _ = assemble(*sample)
    assert core["completeness"]["state"] == "INCOMPLETE"
    assert core["completeness"]["gaps"]
    assert core["financial"]["potential"] == "74199.900000"


@pytest.mark.parametrize(
    "conflict",
    [
        "tenant",
        "scope",
        "revision",
        "evidence",
        "hash",
        "authority",
        "duplicate_evidence",
        "float",
        "exponent",
    ],
)
def test_contradictory_frozen_identity_and_bindings_fail_safely(sample, conflict):
    if conflict in {"tenant", "scope"}:
        sample[0].snapshot["organization_id" if conflict == "tenant" else "scope_key"] = "different"
    elif conflict == "revision":
        sample[1][0].payload = sample[1][0].payload | {"reason": "Changed historical text"}
    elif conflict == "evidence":
        sample[2][0].document_id = identity("different-document")
    elif conflict == "hash":
        sample[7][str(sample[3][0].id)] = "MISMATCH"
    elif conflict == "authority":
        sample[6][0].detail["role_at_action"] = "analyst"
    elif conflict == "duplicate_evidence":
        sample[2].append(deepcopy(sample[2][0]))
    else:
        value = 18.4 if conflict == "float" else "1.84e1"
        sample[0].snapshot["inputs"][0]["payload"]["value"]["rate"] = value
        sample[1][0].payload["value"]["rate"] = value
    with pytest.raises(ProofError):
        assemble(*sample)


def test_stable_binding_identity_set_order_and_scale_preservation(sample):
    core, _ = assemble(*sample)
    sample[1].reverse()
    sample[2].reverse()
    reordered, _ = assemble(*sample)
    assert fingerprint(core) == fingerprint(reordered)
    assert [b["binding_id"] for b in core["calculation"]["bindings"]] == [
        b["binding_id"] for b in reordered["calculation"]["bindings"]
    ]
    assert b'"18.40"' in canonical(core)
    assert any("/rate" in leaves(r["revision"]["payload"]["value"]) for r in core["authority"])


def test_known_missing_governing_material_is_complete_blocked_explanation():
    core, _ = assemble(*capture((term(),), bill(), {"known_missing": ("Price schedule",)}))
    assert core["financial"]["outcome"] == "NEEDS_REVIEW"
    assert core["financial"]["potential"] is None
    assert core["completeness"]["state"] == "COMPLETE"
    assert "Price schedule" in canonical(core).decode()


def test_invariant_rounding_alternatives_and_one_cent_remain_exact():
    profile = ROUNDING.model_copy(update={"modes": ("ROUND_HALF_UP", "ROUND_HALF_EVEN")})
    core, _ = assemble(*capture((term(rounding=profile),), bill()))
    assert core["calculation"]["recorded_trace"]["invariant"] is True
    assert len(core["calculation"]["recorded_trace"]["alternatives"]) == 2
    core, _ = assemble(
        *capture(
            (term(),),
            bill(quantity="1", billed_rate="10.01", posted_amount="10.01", billed_gross="10.01"),
        )
    )
    assert core["financial"]["potential"] == "0.010000"
