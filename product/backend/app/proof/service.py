"""Atomic, bounded proof operations over immutable Phase 4 assessments."""

import hashlib
import logging
import re
import time
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4, uuid5

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app.db.models import (
    Document,
    ExtractedField,
    ExtractionRun,
    Organization,
    OrganizationMembership,
)
from app.financial.models import FinancialAudit, FinancialRevision, FinancialRevisionEvidence
from app.financial.service import get_evaluation, is_stale, latest_decision, lock_authority
from app.proof.assemble import KINDS, assemble, integrity, observation_time
from app.proof.budget import Budget, ProofError, verify_source
from app.proof.canonical import DISCLOSURE, CanonicalError, canonical, digest, fingerprint, leaves
from app.proof.models import (
    ProofArtifact,
    ProofBinding,
    ProofEvent,
    ProofFamily,
    ProofPackage,
    ProofRequest,
    ProofSuccessor,
)

logger = logging.getLogger("financial_leakage")


def query(model, access):
    return select(model).where(model.organization_id == access.organization_id)


def get(session, access, model, identity):
    row = session.scalar(query(model, access).where(model.id == identity))
    if row is None:
        raise HTTPException(404, "Proof record not found")
    return row


def read_authority(session, access, *, exclusive=False):
    from app.auth.access import tenant_active, user_active

    user_active(session, access.user_id)
    # Readers fence current roles and overlays against financial/proof writers too.
    session.scalar(
        select(Organization)
        .where(Organization.id == access.organization_id)
        .with_for_update(read=not exclusive)
    )
    tenant_active(session, access.organization_id)
    membership = session.scalar(
        query(OrganizationMembership, access)
        .where(OrganizationMembership.user_id == access.user_id)
        .with_for_update(read=True)
        .execution_options(populate_existing=True)
    )
    if membership is None:
        raise HTTPException(404, "Organization not found")
    return membership.role


def database_budget(session, budget):
    budget.check()
    session.execute(
        text(
            "SELECT set_config('statement_timeout', :timeout, true), "
            "set_config('lock_timeout', :timeout, true)"
        ),
        {
            "timeout": str(
                max(
                    1,
                    int((budget.limits.work_seconds - (time.monotonic() - budget.started)) * 1000),
                )
            )
        },
    )


def admit(session, access, budget):
    database_budget(session, budget)
    # Transaction-scoped PostgreSQL slots work across processes and release on rollback.
    for slot in range(budget.limits.tenant_concurrency):
        key = int.from_bytes(
            hashlib.sha256(
                f"FLA-PROOF-OPERATION/1:{access.organization_id}:{slot}".encode()
            ).digest()[:8],
            "big",
            signed=True,
        )
        if session.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": key}):
            return
    raise ProofError("proof_busy", "Tenant proof capacity is busy; retry later", 429)


def quota(session, access, budget):
    # One actor can belong to multiple tenants: the rolling quota still belongs to the actor.
    key = int.from_bytes(
        hashlib.sha256(f"FLA-PROOF-ACTOR/1:{access.user_id}".encode()).digest()[:8],
        "big",
        signed=True,
    )
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
    since = datetime.now(UTC) - timedelta(minutes=1)
    count = session.scalar(
        select(func.count())
        .select_from(ProofRequest)
        .where(
            ProofRequest.actor_id == access.user_id,
            ProofRequest.counted.is_(True),
            ProofRequest.created_at >= since,
        )
    )
    budget.check()
    if count >= budget.limits.actor_operations_per_minute:
        raise ProofError(
            "proof_rate_limit", "Proof generation/export rate exceeded; retry later", 429
        )


def event_record(session, access, package, kind, detail, previous=None):
    number = (
        session.scalar(
            select(func.max(ProofEvent.number)).where(
                ProofEvent.organization_id == access.organization_id,
                ProofEvent.package_id == package.id,
            )
        )
        or 0
    ) + 1
    row = ProofEvent(
        organization_id=access.organization_id,
        package_id=package.id,
        number=number,
        actor_id=access.user_id,
        audit_id=uuid4(),
        kind=kind,
        detail=detail,
        previous_id=previous,
    )
    session.add(row)
    session.flush()
    return row


def assert_package(session, access, package):
    audit = session.scalar(
        query(FinancialAudit, access).where(
            FinancialAudit.id == package.audit_id,
            FinancialAudit.target_id == package.id,
            FinancialAudit.action == "proof.issued",
        )
    )
    if fingerprint(package.core) != package.fingerprint or audit is None:
        integrity("Proof content or trusted issuance journal disagrees")


def availability(session, access, package, storage, budget, *, verify=True):
    result = []
    budget.bound(len(package.core["sources"]), "documents")
    documents = {
        str(row.id): row
        for row in session.scalars(
            query(Document, access)
            .where(Document.id.in_([UUID(s["document_id"]) for s in package.core["sources"]]))
            .with_for_update(read=True)
        )
    }
    source_id = ProofEvent.detail["document_id"].astext
    observed = (
        {
            row.detail["document_id"]: row
            for row in session.scalars(
                query(ProofEvent, access)
                .where(ProofEvent.package_id == package.id, ProofEvent.kind == "integrity.observed")
                .distinct(source_id)
                .order_by(source_id, ProofEvent.number.desc())
            )
        }
        if verify
        else {}
    )
    for source in package.core["sources"]:
        budget.check()
        doc = documents.get(source["document_id"])
        if doc is None:
            status = "UNAVAILABLE"
        elif doc.sha256 != source["sha256"]:
            status = "MISMATCH"
        elif verify:
            status, _ = verify_source(storage, doc, budget)
        else:
            status = "UNCHECKED"
        result.append(
            {
                "document_id": source["document_id"],
                "status": status,
                "observed_at": observation_time(),
            }
        )
        if verify:
            previous = observed.get(source["document_id"])
            prior_status = (
                previous.detail["status"]
                if previous
                else ("AVAILABLE_VERIFIED" if source["verified_at_issuance"] else "UNAVAILABLE")
            )
            if status != prior_status:
                event_record(
                    session,
                    access,
                    package,
                    "integrity.observed",
                    {
                        "document_id": source["document_id"],
                        "sha256": source["sha256"],
                        "status": status,
                        "observed_at": observation_time(),
                        "quarantined": status == "MISMATCH",
                    },
                )
    return result


def overlays(session, access, package, *, availability_result=None):
    family = get(session, access, ProofFamily, package.family_id)
    evaluation = get_evaluation(session, access, family.evaluation_id)
    try:
        currentness = "STALE" if is_stale(session, access, evaluation) else "CURRENT"
    except HTTPException as exc:
        if exc.status_code != 422:
            raise
        currentness = "UNKNOWN"
    decision = latest_decision(session, access, evaluation.id)
    review = session.scalar(
        query(ProofEvent, access)
        .where(ProofEvent.package_id == package.id, ProofEvent.kind == "review.finalized")
        .order_by(ProofEvent.number.desc())
        .limit(1)
    )
    successor = session.scalar(
        query(ProofSuccessor, access).where(ProofSuccessor.predecessor_id == package.id)
    )
    predecessor = session.scalar(
        query(ProofSuccessor, access).where(ProofSuccessor.successor_id == package.id)
    )
    return {
        "as_of": observation_time(),
        "financial_currentness": currentness,
        "finding_decision": decision.status
        if decision
        else ("detected" if evaluation.outcome == "POTENTIAL_LEAKAGE" else None),
        "finding_decision_id": str(decision.id) if decision else None,
        "human_review": review.detail["status"] if review else "UNREVIEWED",
        "review_id": str(review.id) if review else None,
        "successor_id": str(successor.successor_id) if successor else None,
        "predecessor_id": str(predecessor.predecessor_id) if predecessor else None,
        "evidence_availability": availability_result
        if availability_result is not None
        else [
            {"document_id": s["document_id"], "status": "UNCHECKED"}
            for s in package.core["sources"]
        ],
    }


def summary(session, access, package, budget=None):
    if budget:
        database_budget(session, budget)
    result = {
        "id": str(package.id),
        "family_id": str(package.family_id),
        "number": package.number,
        "previous_id": str(package.previous_id) if package.previous_id else None,
        "revision_reason": package.revision_reason,
        "fingerprint": package.fingerprint,
        "issued_completeness": package.completeness,
        "financial": package.core["financial"],
        "identity": package.core["identity"],
        "created_at": package.created_at.isoformat(),
        "overlays": overlays(session, access, package),
    }
    if budget:
        budget.check()
    return result


def detail(session, access, package, storage, budget):
    assert_package(session, access, package)
    states = availability(session, access, package, storage, budget)
    result = summary(session, access, package, budget)
    result.update(core=package.core, envelope=package.envelope)
    result["overlays"]["evidence_availability"] = states
    return result


def generate(session, access, evaluation_id, body, storage, budget, request_key):
    evaluation = get_evaluation(session, access, evaluation_id)
    if body.expected_fingerprint != evaluation.fingerprint:
        raise ProofError("proof_stale_input", "Requested evaluation fingerprint disagrees")
    stale = is_stale(session, access, evaluation)
    decision = latest_decision(session, access, evaluation.id)
    if body.mode == "CURRENT" and (stale or (decision and decision.status == "false_positive")):
        raise ProofError(
            "proof_historical_required", "Select explicit historical mode for this assessment"
        )
    family = session.scalar(
        query(ProofFamily, access).where(
            ProofFamily.evaluation_id == evaluation.id,
            ProofFamily.kind == KINDS[evaluation.outcome],
        )
    )
    previous = (
        session.scalar(
            query(ProofPackage, access)
            .where(ProofPackage.family_id == family.id)
            .order_by(ProofPackage.number.desc())
            .limit(1)
        )
        if family
        else None
    )
    if previous and body.revision_reason is None:
        assert_package(session, access, previous)
        # Current byte availability is an overlay, never an automatic content revision.
        return {"package_id": str(previous.id), "created": False, "mode": body.mode}, False
    if (previous.id if previous else None) != body.previous_package_id:
        raise ProofError(
            "proof_stale_revision", "Proof content predecessor changed; reload history"
        )
    quota(session, access, budget)
    ids = evaluation.snapshot.get("calculation_driving_revision_ids", [])
    budget.bound(len(ids), "revisions")
    pinned = [r for r in evaluation.snapshot.get("inputs", []) if r["id"] in ids]
    budget.bound(sum(len(e["supports"]) for r in pinned for e in r["provenance"]), "bindings")
    revisions = session.scalars(
        query(FinancialRevision, access)
        .where(FinancialRevision.id.in_([UUID(i) for i in ids]))
        .with_for_update(read=True)
    ).all()
    evidence = session.scalars(
        query(FinancialRevisionEvidence, access).where(
            FinancialRevisionEvidence.revision_id.in_([r.id for r in revisions])
        )
    ).all()
    doc_ids = {e["document_id"] for r in pinned for e in r["provenance"]} | {
        d["document_id"] for r in pinned for d in r["payload"].get("document_hashes", [])
    }
    budget.bound(len(doc_ids), "documents")
    documents = session.scalars(
        query(Document, access)
        .where(Document.id.in_([UUID(d) for d in sorted(doc_ids)]))
        .order_by(Document.id)
        .with_for_update(read=True)
    ).all()
    run_ids = {e.run_id for e in evidence if e.run_id}
    field_ids = {e.field_id for e in evidence if e.field_id}
    runs = session.scalars(query(ExtractionRun, access).where(ExtractionRun.id.in_(run_ids))).all()
    fields = session.scalars(
        query(ExtractedField, access).where(ExtractedField.id.in_(field_ids))
    ).all()
    audits = session.scalars(
        query(FinancialAudit, access).where(
            FinancialAudit.target_id.in_([evaluation.id, *[r.id for r in revisions]])
        )
    ).all()
    observed, times = {}, {}
    for document in documents:
        observed[str(document.id)], _ = verify_source(storage, document, budget)
        times[str(document.id)] = observation_time()
    core, bindings = assemble(
        evaluation, revisions, evidence, documents, runs, fields, audits, observed, budget
    )
    fp = fingerprint(core)
    if previous:
        assert_package(session, access, previous)
        if fp == previous.fingerprint:
            return {"package_id": str(previous.id), "created": False, "mode": body.mode}, False
        if body.revision_reason == "REPAIRED_EVIDENCE":
            old = deepcopy(previous.core)
            new = deepcopy(core)
            # Repair availability gaps only; financial/evidence meaning stays frozen.
            for content in (old, new):
                content.pop("completeness")
                for source in content["sources"]:
                    source.pop("verified_at_issuance")
            old_gaps = previous.core["completeness"]["gaps"]
            if (
                old != new
                or not old_gaps
                or any(g["code"] != "C07" for g in old_gaps)
                or core["completeness"]["state"] != "COMPLETE"
            ):
                raise ProofError(
                    "proof_invalid_repair",
                    "Repair must restore identical pinned bytes and resolve only availability gaps",
                )
        else:
            version_field = "schema" if body.revision_reason == "SCHEMA_EVOLUTION" else "assembly"
            if previous.core[version_field] == core[version_field]:
                raise ProofError(
                    "proof_version_unchanged",
                    "Schema/assembly revisions require an explicitly released new version",
                )
    if not family:
        family = ProofFamily(
            organization_id=access.organization_id,
            evaluation_id=evaluation.id,
            kind=KINDS[evaluation.outcome],
            actor_id=access.user_id,
        )
        session.add(family)
        session.flush()
    package_id, audit_id = uuid4(), uuid4()
    number = previous.number + 1 if previous else 1
    envelope = {
        "package_id": str(package_id),
        "family_id": str(family.id),
        "number": number,
        "previous_id": str(previous.id) if previous else None,
        "revision_reason": body.revision_reason,
        "actor_id": str(access.user_id),
        "issued_at": observation_time(),
        "source_observed_at": times,
        "request_key": str(request_key),
        "audit_id": str(audit_id),
        "manifest_fingerprint": fp,
        "operations": budget.limits.model_dump(),
    }
    budget.bound(len(canonical({"core": core, "envelope": envelope})), "canonical_bytes")
    if body.mode == "CURRENT" and is_stale(session, access, evaluation):
        raise ProofError("proof_stale_input", "Material inputs changed during proof assembly")
    budget.check()
    package = ProofPackage(
        id=package_id,
        organization_id=access.organization_id,
        family_id=family.id,
        number=number,
        previous_id=previous.id if previous else None,
        revision_reason=body.revision_reason,
        actor_id=access.user_id,
        audit_id=audit_id,
        fingerprint=fp,
        completeness=core["completeness"]["state"],
        core=core,
        envelope=envelope,
    )
    session.add(package)
    session.flush()
    for evidence_row, binding in bindings:
        session.add(
            ProofBinding(
                organization_id=access.organization_id,
                package_id=package.id,
                revision_id=evidence_row.revision_id,
                evidence_id=evidence_row.id,
                document_id=evidence_row.document_id,
                run_id=evidence_row.run_id,
                field_id=evidence_row.field_id,
                binding_id=binding["binding_id"],
                input_pointer=binding["input_pointer"],
            )
        )
    session.flush()
    budget.check()
    return {"package_id": str(package.id), "created": True, "mode": body.mode}, True


def event(session, access, package_id, body, budget):
    package = get(session, access, ProofPackage, package_id)
    assert_package(session, access, package)
    budget.bound(len(body.text), "annotation_characters")
    previous = get(session, access, ProofEvent, body.previous_id) if body.previous_id else None
    if previous and previous.package_id != package.id:
        raise ProofError("proof_event_scope", "Event predecessor belongs to another proof")
    role = session.scalar(
        query(OrganizationMembership, access).where(
            OrganizationMembership.user_id == access.user_id
        )
    ).role
    if body.kind.startswith("annotation.") and previous:
        if previous.kind != "annotation.appended" or (
            role == "analyst" and previous.actor_id != access.user_id
        ):
            raise ProofError(
                "proof_annotation_authority", "Annotation revisions need their author's authority"
            )
        if session.scalar(
            query(ProofEvent, access).where(
                ProofEvent.previous_id == previous.id, ProofEvent.kind.like("annotation.%")
            )
        ):
            raise ProofError("proof_stale_revision", "Annotation already has a later revision")
    if body.kind == "review.finalized":
        head = session.scalar(
            query(ProofEvent, access)
            .where(ProofEvent.package_id == package.id, ProofEvent.kind == "review.finalized")
            .order_by(ProofEvent.number.desc())
            .limit(1)
        )
        if (head.id if head else None) != body.previous_id:
            raise ProofError("proof_stale_revision", "Final review predecessor changed")
    if body.kind == "disclosure.proposed":
        if previous and (
            previous.kind != "disclosure.proposed"
            or session.scalar(
                query(ProofEvent, access).where(
                    ProofEvent.previous_id == previous.id, ProofEvent.kind == "disclosure.proposed"
                )
            )
        ):
            raise ProofError(
                "proof_stale_revision",
                "Disclosure proposal predecessor is invalid or has a later revision",
            )
        known = leaves(package.core)
        if (
            not body.paths
            or len(set(body.paths)) != len(body.paths)
            or any(p not in known for p in body.paths)
        ):
            raise ProofError(
                "proof_redaction_path", "Choose distinct existing scalar proof paths", 422
            )
        if any(known[p] is None or type(known[p]) is bool for p in body.paths):
            raise ProofError(
                "proof_redaction_path", "Null/boolean masking would misrepresent evidence", 422
            )
    if body.kind == "disclosure.approved":
        if not previous or previous.kind != "disclosure.proposed":
            raise ProofError(
                "proof_disclosure_proposal", "An attributed disclosure proposal is required"
            )
        if session.scalar(
            query(ProofEvent, access).where(
                ProofEvent.previous_id == previous.id, ProofEvent.kind == "disclosure.approved"
            )
        ):
            raise ProofError("proof_stale_revision", "Disclosure proposal already has an approval")
    result = event_record(
        session, access, package, body.kind, body.model_dump(mode="json"), body.previous_id
    )
    return {"event_id": str(result.id)}, False


def redaction_filter(package, proposal):
    known = leaves(package.core)
    hidden = [known[p] for p in proposal.detail["paths"]]
    # Original hashes/binding digests can act as disclosure oracles for withheld evidence.
    # Keep only the required parent manifest reference in the separate view metadata.
    original_digests = [
        value
        for value in known.values()
        if isinstance(value, str) and re.fullmatch(r"[a-fA-F0-9]{64}", value)
    ]
    derived_digests = [
        hashlib.sha256(raw).hexdigest()
        for value in hidden
        for raw in (str(value).encode("utf-8"), canonical(value))
    ]
    hidden = [*hidden, *original_digests, *derived_digests]
    secret_strings = [str(value).casefold() for value in hidden]

    def sensitive(value):
        folded = value.casefold()
        return bool(folded) and any(
            secret in folded or folded in secret for secret in secret_strings
        )

    def mask(value):
        if any(value == secret for secret in hidden):
            return {"redacted": True}
        if isinstance(value, str) and sensitive(value):
            return {"redacted": True}
        if isinstance(value, list):
            return [mask(item) for item in value]
        if isinstance(value, dict):
            result = {}
            for index, key in enumerate(sorted(value)):
                opaque = f"redacted-field-{index}" if sensitive(key) else key
                result[opaque] = mask(value[key])
            return result
        return value

    def verify(value):
        encoded = canonical(value).decode("utf-8").casefold()
        if any(secret in encoded for secret in secret_strings):
            raise ProofError("proof_redaction_leak", "Disclosure would expose a hidden value")

    return mask, verify


def disclosure(session, access, package, approval):
    if approval.package_id != package.id or approval.kind != "disclosure.approved":
        raise ProofError(
            "proof_disclosure_scope", "Disclosure approval does not belong to this proof"
        )
    proposal = get(session, access, ProofEvent, approval.previous_id)
    mask, verify = redaction_filter(package, proposal)
    content = mask(deepcopy(package.core))
    content["completeness"] = mask(
        {
            "internal_issued_state": package.completeness,
            "disclosed_verification": "LIMITED_VERIFICATION",
        }
    )
    view = {
        "schema": DISCLOSURE,
        "parent_manifest_fingerprint": package.fingerprint,
        "proposal_id": str(proposal.id),
        "approval_id": str(approval.id),
        "parent_package_id": str(package.id),
        "parent_content_revision": package.number,
        "parent_schema": package.core["schema"],
        "approval": mask(
            {
                "actor_id": str(approval.actor_id),
                "approved_at": approval.created_at.isoformat(),
                "reason": "Attributed reason retained in private approval history; "
                "free text omitted from disclosure for confidentiality.",
            }
        ),
        "withheld_descriptors": [
            {
                "category": "selected fields and original evidence digests",
                "verification": "LIMITED_VERIFICATION",
            }
        ],
        "verification": "LIMITED_VERIFICATION",
        "redacted_field_count": len(proposal.detail["paths"]),
        "limitation": "This separate disclosure hides evidence; "
        "verify the canonical internal proof for omitted assertions.",
        "content": content,
    }
    # Recursive masking includes duplicated raw/provenance/typed strings and dynamic keys.
    # No annotations, review reasons, source filenames or unredacted sibling core accompany it.
    verify(view)
    return view, digest("FLA-PROOF-DISCLOSURE/1", view)


def export(session, access, package_id, body, storage, budget):
    package = get(session, access, ProofPackage, package_id)
    assert_package(session, access, package)
    quota(session, access, budget)
    states = availability(session, access, package, storage, budget)
    context = overlays(session, access, package, availability_result=states)
    context["as_of"] = observation_time()
    context["actor_id"] = str(access.user_id)
    context["format_version"] = "proof-json/1"
    context["confidentiality"] = (
        "Private tenant evidence; downloaded files leave application access controls."
    )
    if body.disclosure_id:
        approval = get(session, access, ProofEvent, body.disclosure_id)
        view, view_hash = disclosure(session, access, package, approval)
        content = {"disclosure": view, "disclosure_hash": view_hash, "export_context": context}
        # Dynamic source IDs/metadata can be hidden too; omit availability IDs from disclosures.
        content["export_context"]["evidence_availability"] = [s["status"] for s in states]
        proposal = get(session, access, ProofEvent, approval.previous_id)
        mask, verify = redaction_filter(package, proposal)
        content["export_context"] = mask(content["export_context"])
        verify(content)
    else:
        content = {"core": package.core, "envelope": package.envelope, "export_context": context}
    raw = canonical(content)
    budget.bound(len(raw), "canonical_bytes")
    row = ProofArtifact(
        organization_id=access.organization_id,
        package_id=package.id,
        actor_id=access.user_id,
        audit_id=uuid4(),
        disclosure_id=body.disclosure_id,
        content=raw,
        content_hash=hashlib.sha256(raw).hexdigest(),
    )
    session.add(row)
    session.flush()
    budget.check()
    return {
        "artifact_id": str(row.id),
        "content_hash": row.content_hash,
        "package_id": str(package.id),
    }, True


def successor(session, access, package_id, body, budget):
    predecessor = get(session, access, ProofPackage, package_id)
    next_package = get(session, access, ProofPackage, body.successor_id)
    for package in (predecessor, next_package):
        assert_package(session, access, package)
    if predecessor.family_id == next_package.family_id:
        raise ProofError(
            "proof_successor_scope",
            "Content revisions already have a predecessor; successors need distinct evaluations",
        )
    same = session.scalar(
        text("SELECT proof_scope(CAST(:a AS jsonb)) = proof_scope(CAST(:b AS jsonb))"),
        {"a": canonical(predecessor.core).decode(), "b": canonical(next_package.core).decode()},
    )
    if (
        not same
        or predecessor.core["billing"]["scope"] is None
        or next_package.core["billing"]["scope"] is None
        or not (predecessor.core["billing"]["scope"] or {}).get("currency")
        or not (next_package.core["billing"]["scope"] or {}).get("currency")
    ):
        raise ProofError(
            "proof_successor_scope",
            "Successor must have the same known invoice scope, currency and period",
        )
    existing = session.scalar(
        query(ProofSuccessor, access).where(ProofSuccessor.predecessor_id == predecessor.id)
    )
    if existing:
        if existing.successor_id == next_package.id:
            return {"successor_relation_id": str(existing.id)}, False
        raise ProofError("proof_successor_conflict", "An explicit successor already exists")
    if session.scalar(
        query(ProofSuccessor, access).where(ProofSuccessor.successor_id == next_package.id)
    ):
        raise ProofError(
            "proof_successor_conflict", "Successor already has an explicit predecessor"
        )
    cursor, visited = next_package.id, set()
    while cursor not in visited:
        budget.check()
        if cursor == predecessor.id:
            raise ProofError("proof_successor_cycle", "Successor relationships cannot form a cycle")
        visited.add(cursor)
        link = session.scalar(
            query(ProofSuccessor, access).where(ProofSuccessor.predecessor_id == cursor)
        )
        if not link:
            break
        cursor = link.successor_id
    row = ProofSuccessor(
        organization_id=access.organization_id,
        predecessor_id=predecessor.id,
        successor_id=next_package.id,
        actor_id=access.user_id,
        audit_id=uuid4(),
        reason=body.reason,
    )
    session.add(row)
    session.flush()
    return {"successor_relation_id": str(row.id)}, False


def execute(session, access, command, target, body, key, storage, limits):
    budget = Budget(limits)
    # Admission before the tenant lock bounds the number of workers waiting for that lock.
    # Recheck the current role under the common Phase 4 organization/membership lock order.
    if access.role.value == "viewer":
        raise HTTPException(403, "Your role cannot change proof records")
    admit(session, access, budget)
    final = command in {"export", "successor", "review.finalized", "disclosure.approved"}
    lock_authority(session, access, final=final)
    budget.check()
    logger.info(
        "proof_operation_started",
        extra={
            "organization_id": str(access.organization_id),
            "evaluation_or_package_id": str(target),
            "operation": command,
            "operation_profile": limits.version,
        },
    )
    request_hash = digest(
        "FLA-PROOF-REQUEST/1",
        {
            "actor": str(access.user_id),
            "command": command,
            "target": str(target),
            "body": body.model_dump(mode="json"),
        },
    )
    prior = session.scalar(query(ProofRequest, access).where(ProofRequest.request_key == str(key)))
    if prior and prior.request_hash == request_hash:
        return prior.result
    if prior:
        # A conflict also has a trusted append-only audit origin, without overwriting the key.
        conflict_key = uuid5(key, request_hash)
        error = {
            "error": {
                "code": "proof_request_conflict",
                "message": "Idempotency key was already used for another request",
                "status": 409,
            }
        }
        if not session.scalar(
            query(ProofRequest, access).where(ProofRequest.request_key == str(conflict_key))
        ):
            session.add(
                ProofRequest(
                    organization_id=access.organization_id,
                    actor_id=access.user_id,
                    audit_id=uuid4(),
                    request_key=str(conflict_key),
                    request_hash=request_hash,
                    command=command,
                    counted=False,
                    result=error,
                )
            )
            session.flush()
        return error
    counted = False
    try:
        with session.begin_nested():
            if command == "generate":
                result, counted = generate(session, access, target, body, storage, budget, key)
            elif command == "export":
                result, counted = export(session, access, target, body, storage, budget)
            elif command == "successor":
                result, counted = successor(session, access, target, body, budget)
            else:
                result, counted = event(session, access, target, body, budget)
            budget.check()
    except ProofError as exc:
        result = {"error": {"code": exc.code, "message": exc.message, "status": exc.status}}
        # Rejections never leave an issued proof/artifact after their savepoint is rolled back.
        counted = command in {"generate", "export"} and exc.code != "proof_rate_limit"
    except DBAPIError:
        result = {
            "error": {
                "code": "proof_transaction_retry",
                "message": "Proof transaction could not complete safely; "
                "retry with a new request key",
                "status": 503,
            }
        }
    except (CanonicalError, KeyError, ValueError, TypeError, RecursionError):
        result = {
            "error": {
                "code": "proof_snapshot_integrity",
                "message": "Historical proof inputs are invalid",
                "status": 409,
            }
        }
    session.add(
        ProofRequest(
            organization_id=access.organization_id,
            actor_id=access.user_id,
            audit_id=uuid4(),
            request_key=str(key),
            request_hash=request_hash,
            command=command,
            counted=counted,
            result=result,
        )
    )
    session.flush()
    logger.info(
        "proof_operation_failed" if "error" in result else "proof_operation_completed",
        extra={
            "organization_id": str(access.organization_id),
            "evaluation_or_package_id": str(target),
            "operation": command,
            "reason_code": result.get("error", {}).get("code"),
            "duration_ms": round((time.monotonic() - budget.started) * 1000),
            "source_bytes": budget.bytes_read,
            "operation_profile": limits.version,
        },
    )
    return result
