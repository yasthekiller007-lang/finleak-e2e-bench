"""Explicit Recovery Ledger commands over fenced Phase 4/5 authority.

No function invokes evaluation, proof generation, extraction or external actions.
"""

import hashlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select, text

from app.auth.dependencies import OrganizationAccess
from app.db.models import Document, OrganizationMembership
from app.domain.types import MembershipRole
from app.financial import service as financial
from app.financial.models import FinancialAudit
from app.proof import service as proof
from app.proof.budget import ProofError, verify_source
from app.proof.canonical import canonical, leaves
from app.proof.models import ProofFamily, ProofPackage, ProofSuccessor
from app.recovery.budget import Budget, admit, quota
from app.recovery.models import (
    RecoveryAlias,
    RecoveryCase,
    RecoveryEvidence,
    RecoveryInstrument,
    RecoveryProposal,
    RecoveryPublication,
    RecoveryRecord,
    RecoveryRequest,
)
from app.recovery.schema import Moment, Proposal
from app.recovery.values import (
    aligned,
    economic_day,
    exact,
    fail,
    subtract,
    total,
)


# Shared tenant query primitives never resolve an unscoped client identity.
def query(model, access):
    return select(model).where(model.organization_id == access.organization_id)


def get(session, access, model, identity):
    row = session.scalar(query(model, access).where(model.id == identity))
    if row is None:
        fail("recovery_not_found", "Recovery record not found", 404)
    if model in {RecoveryRecord, RecoveryCase, RecoveryProposal, RecoveryInstrument}:
        assert_origin(session, access, row)
    return row


def require_guards(session):
    tables = [
        RecoveryCase,
        RecoveryInstrument,
        RecoveryProposal,
        RecoveryEvidence,
        RecoveryRecord,
        RecoveryAlias,
        RecoveryRequest,
        RecoveryPublication,
    ]
    requirements = {}
    for model in tables:
        names = ["recovery_immutable", "recovery_authority"]
        if model not in {RecoveryEvidence, RecoveryAlias}:
            names.append("recovery_audit")
        requirements[model.__tablename__] = names
    requirements.update(
        documents=["recovery_source_guard", "financial_source_guard", "proof_source_guard"],
        financial_audit=["audit_origin", "immutable_history"],
    )
    for table, names in requirements.items():
        found = session.scalars(
            text(
                "SELECT t.tgname FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
                "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=current_schema() "
                "AND c.relname=:table AND t.tgenabled IN ('O','A')"
            ),
            {"table": table},
        ).all()
        if not set(names) <= set(found):
            fail("recovery_guard_integrity", "Recovery integrity guards are unavailable", 503)
    if session.scalar(text("SELECT current_setting('track_commit_timestamp')")) != "on":
        fail("recovery_known_at_unavailable", "Actual commit provenance is unavailable", 503)


def assert_origin(session, access, row):
    journal = session.scalar(query(FinancialAudit, access).where(FinancialAudit.id == row.audit_id))
    action = {
        RecoveryCase: "case.created",
        RecoveryInstrument: "instrument.created",
        RecoveryProposal: "proposal.prepared",
    }.get(type(row), getattr(row, "kind", ""))
    if (
        journal is None
        or journal.target_id != row.id
        or journal.actor_id != row.actor_id
        or journal.action != "recovery." + action
        or journal.detail.get("table") != row.__tablename__
    ):
        fail("recovery_audit_integrity", "Recovery history and trusted audit disagree", 503)


def digest(value):
    return hashlib.sha256(b"FLA-RECOVERY/1\n" + canonical(value)).hexdigest()


def head(session, access, case_id, kind=None):
    q = query(RecoveryRecord, access).where(RecoveryRecord.case_id == case_id)
    if kind:
        q = q.where(RecoveryRecord.kind == kind)
    return session.scalar(q.order_by(RecoveryRecord.number.desc()).limit(1))


def records(session, access, case_id, budget):
    rows = session.scalars(
        query(RecoveryRecord, access)
        .where(RecoveryRecord.case_id == case_id)
        .order_by(RecoveryRecord.number)
        .limit(budget.limits.projection_records + 1)
    ).all()
    budget.bound(len(rows), "projection_records")
    for row in rows:
        assert_origin(session, access, row)
    return rows


def cas(session, access, case_id, expected):
    current = head(session, access, case_id)
    if (current.id if current else None) != expected:
        fail("recovery_stale_input", "Recovery history changed; reload before acting")
    return current


def append(session, access, case, kind, value, reason, *, proposal=None, pins=None, **components):
    previous = head(session, access, case.id)
    row = RecoveryRecord(
        organization_id=access.organization_id,
        case_id=case.id,
        number=previous.number + 1 if previous else 1,
        previous_id=previous.id if previous else None,
        actor_id=access.user_id,
        audit_id=uuid4(),
        kind=kind,
        proposal_id=proposal.id if proposal else None,
        value=value,
        reason=reason,
        pins=pins or {},
        recorded_at=datetime.now(UTC),
        **components,
    )
    session.add(row)
    session.flush()
    session.refresh(row)
    return row


def identity_hash(value):
    return digest({k: value[k] for k in ("namespace", "issuer", "reference", "currency")})


def create_case(session, access, body):
    e = financial.get_evaluation(session, access, body.evaluation_id)
    decision = financial.latest_decision(session, access, e.id)
    if e.potential is None or (decision and decision.status == "false_positive"):
        fail("recovery_ineligible_finding")
    existing = session.scalar(query(RecoveryCase, access).where(RecoveryCase.evaluation_id == e.id))
    if existing:
        return existing
    row = RecoveryCase(
        organization_id=access.organization_id,
        evaluation_id=e.id,
        actor_id=access.user_id,
        audit_id=uuid4(),
    )
    session.add(row)
    session.flush()
    return row


def create_instrument(session, access, body):
    value = body.model_dump(mode="json")
    identity = identity_hash(value)
    existing = session.scalar(
        query(RecoveryInstrument, access).where(RecoveryInstrument.identity_hash == identity)
    )
    alias = session.scalar(query(RecoveryAlias, access).where(RecoveryAlias.alias_hash == identity))
    if alias:
        existing = get(session, access, RecoveryInstrument, alias.instrument_id)
    if existing:
        if existing.kind != body.kind:
            fail("recovery_identity_conflict")
        return existing
    row = RecoveryInstrument(
        organization_id=access.organization_id,
        actor_id=access.user_id,
        audit_id=uuid4(),
        identity_hash=identity,
        **value,
    )
    session.add(row)
    session.flush()
    return row


def text_bounds(value, budget):
    for _, item in leaves(value).items():
        if isinstance(item, str):
            budget.bound(len(item), "text_chars")


def prepare(session, access, case_id, body, budget):
    case = get(session, access, RecoveryCase, case_id)
    value = body.value.model_dump(mode="json")
    text_bounds(body.model_dump(mode="json"), budget)
    budget.bound(sum(len(e.supports) for e in body.evidence), "bindings")
    budget.bound(len({e.document_id for e in body.evidence}), "documents")
    semantic = digest(
        {
            "value": value,
            "evidence": [e.model_dump(mode="json") for e in body.evidence],
            "head": str(body.expected_head) if body.expected_head else None,
        }
    )
    existing = session.scalar(
        query(RecoveryProposal, access).where(
            RecoveryProposal.case_id == case.id, RecoveryProposal.semantic_hash == semantic
        )
    )
    if existing:
        return existing
    cas(session, access, case.id, body.expected_head)
    evidence_manifest = []
    for binding in body.evidence:
        doc = get(session, access, Document, binding.document_id)
        evidence_manifest.append(
            {
                "document_id": str(doc.id),
                "binding_hash": digest(binding.model_dump(mode="json")),
                "sha256": doc.sha256,
                "file_size": doc.file_size,
            }
        )
    proposal = RecoveryProposal(
        organization_id=access.organization_id,
        case_id=case.id,
        actor_id=access.user_id,
        audit_id=uuid4(),
        kind=body.value.kind,
        value=value,
        semantic_hash=semantic,
        authority={
            "head": str(body.expected_head) if body.expected_head else None,
            "evidence_manifest": evidence_manifest,
        },
        reason=body.reason,
    )
    session.add(proposal)
    session.flush()
    for binding in body.evidence:
        doc = get(session, access, Document, binding.document_id)
        row = RecoveryEvidence(
            organization_id=access.organization_id,
            proposal_id=proposal.id,
            document_id=doc.id,
            sha256=doc.sha256,
            file_size=doc.file_size,
            media_type=doc.mime_type,
            binding_hash=digest(binding.model_dump(mode="json")),
            detail=binding.model_dump(mode="json"),
        )
        session.add(row)
    session.flush()
    return proposal


def bindings(session, access, proposal_id):
    return session.scalars(
        query(RecoveryEvidence, access).where(RecoveryEvidence.proposal_id == proposal_id)
    ).all()


def verified_sources(session, access, proposal_ids, package, storage, budget):
    rows = []
    for identity in set(proposal_ids):
        if identity:
            rows.extend(bindings(session, access, identity))
    for row in rows:
        if digest(row.detail) != row.binding_hash:
            fail("recovery_integrity_conflict")
    budget.track(
        bindings=[
            (str(r.proposal_id), str(r.document_id), pointer)
            for r in rows
            for pointer in r.detail["supports"]
        ]
    )
    if package:
        budget.track(
            bindings=[
                (str(package.id), index)
                for index, _ in enumerate(package.core["calculation"]["bindings"])
            ]
        )
    pinned = {str(r.document_id): {"sha256": r.sha256, "file_size": r.file_size} for r in rows}
    if package:
        for source in package.core["sources"]:
            key = source["document_id"]
            if key in pinned and pinned[key]["sha256"] != source["sha256"]:
                fail("recovery_integrity_conflict")
            pinned[key] = {"sha256": source["sha256"], "file_size": source.get("size_bytes")}
    budget.track(sources=pinned)
    for identity, expected in pinned.items():
        budget.check()
        document = get(session, access, Document, UUID(identity))
        if document.sha256 != expected["sha256"] or (
            expected["file_size"] is not None and document.file_size != expected["file_size"]
        ):
            fail("recovery_integrity_conflict")
        status, _ = verify_source(storage, document, budget)
        if status != "AVAILABLE_VERIFIED":
            fail(
                "recovery_source_unavailable",
                "Required original is unavailable or its bytes disagree",
            )
    return pinned


def evidence_gate(session, access, proposal, budget):
    rows = bindings(session, access, proposal.id)
    budget.bound(len(rows), "bindings")
    if not rows:
        fail("recovery_evidence_incomplete")
    supported = set()
    for row in rows:
        if (
            not row.detail["quotation"]
            or not row.detail["raw_fields"]
            or not row.detail["reviewed_fields"]
        ):
            fail("recovery_evidence_incomplete")
        reviewed = row.detail["reviewed_fields"]
        for pointer in row.detail["supports"]:
            material = leaves({"value": proposal.value}).get(pointer)
            if material is not None and reviewed.get(pointer) != str(material):
                fail("recovery_evidence_mapping")
        supported.update(row.detail["supports"])
    # Every material reviewed value is explicitly tied to a source locator/quotation.
    required = {
        "/value" + pointer for pointer, value in leaves(proposal.value).items() if value is not None
    }
    if not required <= supported:
        fail("recovery_evidence_incomplete")


def finding_state(session, access, case):
    e = financial.get_evaluation(session, access, case.evaluation_id)
    decision = financial.latest_decision(session, access, e.id)
    stale = financial.is_stale(session, access, e)
    return e, decision, stale


def party_gate(session, access, case, party_id, value=None):
    party = get(session, access, RecoveryRecord, UUID(str(party_id)))
    if (
        party.kind != "party"
        or party.case_id != case.id
        or head(session, access, case.id, "party").id != party.id
    ):
        fail("recovery_party_unresolved")
    revoked = session.scalar(
        query(RecoveryRecord, access)
        .where(
            RecoveryRecord.case_id == case.id,
            RecoveryRecord.kind == "party_revoked",
            RecoveryRecord.value["party_id"].astext == str(party.id),
        )
        .limit(1)
    )
    if revoked:
        fail("recovery_party_revoked")
    e = financial.get_evaluation(session, access, case.evaluation_id)
    scope = e.snapshot["billing_scope"]
    if (
        party.value["supplier"] != scope["supplier_party"]
        or party.value["customer"] != scope["customer_party"]
    ):
        fail("recovery_party_unresolved")
    if value:
        for field in ("payer", "payee", "beneficiary"):
            if field in value and value[field] != party.value[field]:
                fail("recovery_party_unresolved")
        day = economic_day(value["economic"])
        if day < Moment(precision="DATE", day=party.value["valid_from"]).day or (
            party.value["valid_to"]
            and day >= Moment(precision="DATE", day=party.value["valid_to"]).day
        ):
            fail("recovery_party_date")
    return party


def authority(session, access, case, readiness, storage, budget, proposal_ids=()):
    e, decision, stale = finding_state(session, access, case)
    if stale or decision is None or decision.status != "confirmed":
        fail("recovery_finding_blocked")
    if decision.id != UUID(readiness["decision_id"]) or e.currency != readiness["currency"]:
        fail("recovery_stale_input")
    package = get(session, access, ProofPackage, UUID(readiness["proof_id"]))
    family = get(session, access, ProofFamily, package.family_id)
    if (
        family.evaluation_id != e.id
        or family.kind != "MONETARY_FINDING_PROOF"
        or package.completeness != "COMPLETE"
    ):
        fail("recovery_proof_incomplete")
    proof.assert_package(session, access, package)
    party = party_gate(session, access, case, readiness["party_id"])
    sources = verified_sources(
        session, access, [party.proposal_id, *proposal_ids], package, storage, budget
    )
    return {
        "decision_id": str(decision.id),
        "evaluation_fingerprint": e.fingerprint,
        "proof_id": str(package.id),
        "proof_fingerprint": package.fingerprint,
        "party_id": str(party.id),
        "sources": sources,
        "integrity": "VERIFIED",
        "profile": budget.limits.profile,
    }


def positive_gate(session, access, case, budget):
    lifecycle = head(session, access, case.id, "lifecycle")
    ready = head(session, access, case.id, "readiness")
    if lifecycle and lifecycle.value["state"] != "OPEN":
        fail("recovery_case_closed")
    if head(session, access, case.id, "retire"):
        fail("recovery_scope_retired")
    if ready is None or (lifecycle and lifecycle.number > ready.number):
        fail("recovery_not_ready")
    # No overlapping old/new scope can obtain another pursuit budget.
    evaluation = financial.get_evaluation(session, access, case.evaluation_id)
    members = set(evaluation.snapshot["billing_scope"]["members"])
    others = session.scalars(
        query(RecoveryCase, access)
        .where(RecoveryCase.id != case.id)
        .limit(budget.limits.projection_records + 1)
    ).all()
    budget.bound(len(others), "projection_records")
    for other in others:
        e = financial.get_evaluation(session, access, other.evaluation_id)
        if e.invoice_source_id == evaluation.invoice_source_id and members & set(
            e.snapshot["billing_scope"]["members"]
        ):
            if head(session, access, other.id, "readiness") and not head(
                session, access, other.id, "retire"
            ):
                fail("recovery_overlapping_authority")
    budget.check()
    return ready


def signed_balance(session, access, case_id=None, instrument_id=None, original_id=None):
    q = query(RecoveryRecord, access).with_only_columns(
        func.coalesce(func.sum(RecoveryRecord.amount), 0)
    )
    if case_id:
        q = q.where(RecoveryRecord.case_id == case_id)
    if instrument_id:
        q = q.where(RecoveryRecord.instrument_id == instrument_id)
    if original_id:
        q = q.where(RecoveryRecord.original_id == original_id, RecoveryRecord.kind == "reversal")
    return exact(session.scalar(q))


def quantum_gate(value, quantum):
    for key in ("amount", "principal", "gross", "tax", "fees", "withholding", "net_cash", "other"):
        if value.get(key) is not None:
            aligned(exact(value[key]), exact(quantum))


def semantic_realization(session, access, value):
    existing = session.scalar(
        query(RecoveryRecord, access)
        .where(
            RecoveryRecord.kind == "realization",
            RecoveryRecord.instrument_id == UUID(value["instrument_id"]),
            RecoveryRecord.value["event_reference"].astext == value["event_reference"],
        )
        .limit(1)
    )
    if existing:
        if existing.value != value:
            fail("recovery_economic_conflict")
        return existing


def approve(session, access, proposal_id, body, storage, budget):
    proposal = get(session, access, RecoveryProposal, proposal_id)
    case = get(session, access, RecoveryCase, proposal.case_id)
    existing = session.scalar(
        query(RecoveryRecord, access).where(RecoveryRecord.proposal_id == proposal.id)
    )
    if existing:
        if body.decision != (
            "REJECT"
            if existing.kind == "rejected"
            else "WITHDRAW"
            if existing.kind == "withdrawn"
            else "APPROVE"
        ):
            fail("recovery_decision_conflict")
        return existing
    value = proposal.value
    if proposal.kind == "realization" and body.decision == "APPROVE":
        existing = semantic_realization(session, access, value)
        if existing:
            if existing.case_id != case.id:
                fail("recovery_shared_allocation_deferred")
            return existing
    cas(session, access, case.id, body.expected_head)
    if body.decision == "APPROVE" and proposal.authority["head"] != (
        str(body.expected_head) if body.expected_head else None
    ):
        fail("recovery_stale_input")
    if body.decision != "APPROVE":
        if body.decision == "WITHDRAW" and proposal.actor_id != access.user_id:
            fail("recovery_forbidden", status=403)
        return append(
            session,
            access,
            case,
            "rejected" if body.decision == "REJECT" else "withdrawn",
            {},
            body.reason,
            proposal=proposal,
        )
    # Re-validate strict schema so malformed database payload cannot acquire authority.
    parsed = Proposal.model_validate(
        {"value": value, "evidence": [], "expected_head": body.expected_head, "reason": body.reason}
    ).value
    evidence_gate(session, access, proposal, budget)
    components = {}
    pins = {"profile": budget.limits.profile}
    package = None
    required_proposals = [proposal.id]
    if parsed.kind == "party":
        previous_party = head(session, access, case.id, "party")
        if parsed.previous_party_id != (previous_party.id if previous_party else None):
            fail("recovery_stale_input")
        e = financial.get_evaluation(session, access, case.evaluation_id)
        scope = e.snapshot["billing_scope"]
        if parsed.supplier != scope["supplier_party"] or parsed.customer != scope["customer_party"]:
            fail("recovery_party_unresolved")
        if parsed.valid_to and parsed.valid_to <= parsed.valid_from:
            fail("recovery_party_date")
        if parsed.relationship == "DIRECT" and (
            parsed.payer != parsed.supplier
            or parsed.payee != parsed.customer
            or parsed.beneficiary != parsed.customer
        ):
            fail("recovery_party_unresolved")
    elif parsed.kind == "readiness":
        lifecycle = head(session, access, case.id, "lifecycle")
        if (lifecycle and lifecycle.value["state"] != "OPEN") or head(
            session, access, case.id, "retire"
        ):
            fail("recovery_case_closed")
        e, _, _ = finding_state(session, access, case)
        if parsed.scope != e.snapshot["billing_scope"]["scope"]:
            fail("recovery_scope_incompatible")
        balance = signed_balance(session, access, case_id=case.id)
        current_claim = head(session, access, case.id, "claim")
        if (
            parsed.pursuit > e.potential
            or parsed.pursuit < balance
            or (
                current_claim
                and current_claim.value["state"] == "RECORDED_ACTION"
                and parsed.pursuit < current_claim.principal
            )
        ):
            fail("recovery_pursuit_conflict")
        quantum_gate({"amount": parsed.pursuit}, parsed.quantum)
        # Check overlap before granting the first budget, not only at realization.
        others = session.scalars(
            query(RecoveryCase, access)
            .where(RecoveryCase.id != case.id)
            .limit(budget.limits.projection_records + 1)
        ).all()
        budget.bound(len(others), "projection_records")
        for other in others:
            oe = financial.get_evaluation(session, access, other.evaluation_id)
            if oe.invoice_source_id == e.invoice_source_id and set(
                oe.snapshot["billing_scope"]["members"]
            ) & set(e.snapshot["billing_scope"]["members"]):
                if head(session, access, other.id, "readiness") and not head(
                    session, access, other.id, "retire"
                ):
                    fail("recovery_overlapping_authority")
        pins = authority(session, access, case, value, storage, budget, required_proposals)
        components["principal"] = parsed.pursuit
    elif parsed.kind == "realization":
        ready = positive_gate(session, access, case, budget)
        if ready.id != parsed.readiness_id:
            fail("recovery_stale_input")
        party = party_gate(session, access, case, parsed.party_id, value)
        reviewed = get(session, access, RecoveryRecord, parsed.instrument_review_id)
        instrument = get(session, access, RecoveryInstrument, parsed.instrument_id)
        if (
            reviewed.case_id != case.id
            or reviewed.kind != "instrument"
            or reviewed.instrument_id != instrument.id
        ):
            fail("recovery_instrument_unreviewed")
        if (
            head(session, access, case.id, "instrument")
            and reviewed.value.get("origin") != "POST_FINDING_REMEDY"
        ):
            fail("recovery_preexisting_credit")
        if (
            reviewed.value["related_cases"] and reviewed.value["related_cases"] != [str(case.id)]
        ) or instrument.kind == "SETTLEMENT":
            fail("recovery_shared_allocation_deferred")
        if parsed.scope != ready.value["scope"] or parsed.scope != reviewed.value["scope"]:
            fail("recovery_scope_incompatible")
        current_review = session.scalar(
            query(RecoveryRecord, access)
            .where(
                RecoveryRecord.kind == "instrument", RecoveryRecord.instrument_id == instrument.id
            )
            .order_by(RecoveryRecord.created_at.desc(), RecoveryRecord.number.desc())
            .limit(1)
        )
        if current_review.id != reviewed.id:
            fail("recovery_stale_input")
        for key in ("payer", "payee", "beneficiary"):
            if value[key] != reviewed.value[key]:
                fail("recovery_party_unresolved")
        if parsed.currency != ready.value["currency"] or instrument.currency != parsed.currency:
            fail("recovery_currency_incompatible")
        if (
            parsed.tax_basis == "UNKNOWN"
            or parsed.principal is None
            or parsed.amount > parsed.principal
            or reviewed.principal is None
        ):
            fail("recovery_basis_unresolved")
        if parsed.principal > reviewed.principal:
            fail("recovery_budget_conflict")
        if parsed.tax_basis == "INCLUSIVE" and parsed.tax is None:
            fail("recovery_basis_unresolved")
        if parsed.quantum != exact(ready.value["quantum"]):
            fail("recovery_quantum")
        quantum_gate(value, parsed.quantum)
        if parsed.method == "CASH":
            if (
                instrument.kind not in {"CASH", "CREDIT"}
                or parsed.net_cash is None
                or reviewed.value["status"]
                != ("SETTLED" if instrument.kind == "CASH" else "ISSUED")
            ):
                fail("recovery_method_incomplete")
        elif parsed.method == "APPLIED_CREDIT":
            if (
                instrument.kind != "CREDIT"
                or reviewed.value["status"] != "ISSUED"
                or not parsed.application_reference
            ):
                fail("recovery_method_incomplete")
        elif (
            instrument.kind != "LIABILITY"
            or parsed.unpaid_original is not True
            or parsed.liability_before is None
            or parsed.liability_after is None
            or subtract(parsed.liability_before, parsed.liability_after) != parsed.amount
        ):
            fail("recovery_method_incomplete")
        if parsed.amount > subtract(
            exact(ready.value["pursuit"]), signed_balance(session, access, case_id=case.id)
        ) or parsed.amount > subtract(
            reviewed.principal, signed_balance(session, access, instrument_id=instrument.id)
        ):
            fail("recovery_budget_conflict")
        if (
            instrument.kind == "CREDIT"
            and parsed.replaces_id is None
            and parsed.amount > credit_balance(session, access, case, instrument.id, budget)
        ):
            fail("recovery_credit_budget")
        if parsed.method == "CASH" and parsed.replaces_id is None:
            cash_rows = session.scalars(
                query(RecoveryRecord, access).where(RecoveryRecord.instrument_id == instrument.id)
            ).all()
            actual_cash = total(
                [
                    row.net_cash
                    for row in cash_rows
                    if row.net_cash is not None and not row.value.get("replaces_id")
                ]
            )
            cash_budget = reviewed.net_cash if reviewed.net_cash is not None else reviewed.gross
            earlier_cash = [
                row
                for row in cash_rows
                if row.kind == "realization"
                and row.value["method"] == "CASH"
                and not row.value.get("replaces_id")
            ]
            if instrument.kind == "CASH" and earlier_cash:
                # Another principal allocation to the same settled bank receipt
                # must retain its raw bank fact, not mint a second cash flow.
                if (
                    parsed.net_cash != earlier_cash[0].net_cash
                    or value["economic"] != earlier_cash[0].economic
                ):
                    fail("recovery_economic_conflict")
            elif cash_budget is None or total([actual_cash, parsed.net_cash]) > cash_budget:
                fail("recovery_cash_budget")
        if parsed.replaces_id:
            original = get(session, access, RecoveryRecord, parsed.replaces_id)
            negatives = session.scalars(
                query(RecoveryRecord, access).where(
                    RecoveryRecord.kind == "reversal", RecoveryRecord.original_id == original.id
                )
            ).all()
            replacements = session.scalars(
                query(RecoveryRecord, access).where(
                    RecoveryRecord.kind == "realization",
                    RecoveryRecord.value["replaces_id"].astext == str(original.id),
                )
            ).all()
            released = total(
                [-r.amount for r in negatives if r.value["reversal_type"] == "DE_RECOGNITION"]
            )
            if (
                original.kind != "realization"
                or original.case_id != case.id
                or original.instrument_id != instrument.id
                or (parsed.method == "CASH" and parsed.net_cash != original.net_cash)
                or parsed.amount > subtract(released, total([r.amount for r in replacements]))
            ):
                fail("recovery_replacement_budget")
            components["original_id"] = original.id
        required_proposals.extend(
            [
                r.proposal_id
                for r in records(session, access, case.id, budget)
                if r.kind in {"realization", "reversal"}
            ]
        )
        required_proposals.extend([ready.proposal_id, reviewed.proposal_id, party.proposal_id])
        pins = authority(session, access, case, ready.value, storage, budget, required_proposals)
        pins["readiness_id"] = str(ready.id)
        pins["instrument_kind"] = instrument.kind
        components.update(
            amount=parsed.amount, instrument_id=instrument.id, currency=parsed.currency
        )
    elif parsed.kind == "reversal":
        original = get(session, access, RecoveryRecord, parsed.original_id)
        if original.kind != "realization" or original.case_id != case.id:
            fail("recovery_original_invalid")
        if parsed.amount > total(
            [original.amount, signed_balance(session, access, original_id=original.id)]
        ):
            fail("recovery_reversal_budget")
        aligned(parsed.amount, exact(original.value["quantum"]))
        if parsed.restored_credit is not None:
            # An attribution correction alone cannot restore AP credit availability.
            if (
                parsed.reversal_type != "ECONOMIC_RETURN"
                or original.value["method"] != "APPLIED_CREDIT"
                or parsed.restored_credit > parsed.amount
            ):
                fail("recovery_credit_restoration")
        components.update(
            amount=-parsed.amount,
            original_id=original.id,
            instrument_id=original.instrument_id,
            currency=original.currency,
        )
        if parsed.reversal_type == "DE_RECOGNITION" and parsed.cash_return is not None:
            fail("recovery_correction_not_cash")
        if (
            parsed.reversal_type == "ECONOMIC_RETURN"
            and original.value["method"] == "CASH"
            and parsed.cash_return is None
        ):
            fail("recovery_return_evidence")
        if parsed.cash_return is not None:
            components["net_cash"] = -parsed.cash_return
        required_proposals.append(original.proposal_id)
    elif parsed.kind == "instrument":
        instrument = get(session, access, RecoveryInstrument, parsed.instrument_id)
        pins["instrument_kind"] = instrument.kind
        for identity in parsed.related_cases:
            get(session, access, RecoveryCase, identity)
        if parsed.principal is not None and parsed.tax_basis == "UNKNOWN":
            fail("recovery_basis_unresolved")
        existing_review = session.scalar(
            query(RecoveryRecord, access)
            .where(
                RecoveryRecord.instrument_id == instrument.id, RecoveryRecord.kind == "instrument"
            )
            .order_by(RecoveryRecord.created_at.desc(), RecoveryRecord.number.desc())
            .limit(1)
        )
        if parsed.previous_review_id != (existing_review.id if existing_review else None):
            fail("recovery_stale_input")
        if existing_review and (
            existing_review.case_id != case.id
            or (
                parsed.principal is None
                and signed_balance(session, access, instrument_id=instrument.id) != 0
            )
            or (
                parsed.principal is not None
                and parsed.principal < signed_balance(session, access, instrument_id=instrument.id)
            )
        ):
            fail("recovery_instrument_revision_conflict")
        if existing_review and instrument.kind == "CREDIT":
            physical_used = subtract(
                existing_review.principal,
                credit_balance(session, access, case, instrument.id, budget),
            )
            if (parsed.principal is None and physical_used != 0) or (
                parsed.principal is not None and parsed.principal < physical_used
            ):
                fail("recovery_instrument_revision_conflict")
        components.update(instrument_id=instrument.id, currency=instrument.currency)
    elif parsed.kind == "alias":
        instrument = get(session, access, RecoveryInstrument, parsed.instrument_id)
        alias_hash = identity_hash(parsed.identity.model_dump(mode="json"))
        if (
            parsed.identity.currency != instrument.currency
            or parsed.identity.kind != instrument.kind
        ):
            fail("recovery_identity_conflict")
        collision = session.scalar(
            query(RecoveryInstrument, access).where(RecoveryInstrument.identity_hash == alias_hash)
        )
        alias = session.scalar(
            query(RecoveryAlias, access).where(RecoveryAlias.alias_hash == alias_hash)
        )
        if (collision and collision.id != instrument.id) or (
            alias and alias.instrument_id != instrument.id
        ):
            fail("recovery_identity_conflict")
        components["instrument_id"] = instrument.id
    elif parsed.kind == "party_revoked":
        party_gate(session, access, case, parsed.party_id)
    elif parsed.kind == "credit_state":
        instrument = get(session, access, RecoveryInstrument, parsed.instrument_id)
        if instrument.kind != "CREDIT":
            fail("recovery_method_incomplete")
        available = credit_balance(session, access, case, instrument.id, budget)
        if parsed.state in {"CANCELLED", "EXPIRED"} and parsed.amount > available:
            fail("recovery_credit_budget")
        if parsed.state == "RESTORED":
            original = get(session, access, RecoveryRecord, parsed.original_id)
            if (
                original.kind != "reversal"
                or original.instrument_id != instrument.id
                or original.case_id != case.id
                or original.value.get("restored_credit") is None
                or parsed.amount > exact(original.value["restored_credit"])
            ):
                fail("recovery_credit_restoration")
            already = session.scalar(
                query(RecoveryRecord, access)
                .where(
                    RecoveryRecord.kind == "credit_state", RecoveryRecord.original_id == original.id
                )
                .limit(1)
            )
            if already:
                fail("recovery_credit_restoration")
            components["original_id"] = original.id
        if parsed.state == "RECONCILED" and parsed.amount != available:
            fail("recovery_credit_reconciliation")
        components.update(
            instrument_id=instrument.id, principal=parsed.amount, currency=instrument.currency
        )
    elif parsed.kind in {"claim", "vendor"}:
        if parsed.kind == "claim" and parsed.state == "RECORDED_ACTION":
            ready = positive_gate(session, access, case, budget)
            if (
                parsed.principal is None
                or parsed.tax_basis != "EXCLUSIVE"
                or parsed.currency != ready.value["currency"]
                or parsed.principal > exact(ready.value["pursuit"])
            ):
                fail("recovery_claim_basis")
            quantum_gate({"principal": parsed.principal}, exact(ready.value["quantum"]))
            pins = authority(
                session,
                access,
                case,
                ready.value,
                storage,
                budget,
                [proposal.id, ready.proposal_id],
            )
        elif parsed.kind == "vendor":
            party = party_gate(session, access, case, parsed.party_id, value)
            required_proposals.append(party.proposal_id)

        components.update(principal=getattr(parsed, "principal", None), currency=parsed.currency)
    elif parsed.kind == "cost":
        instrument = get(session, access, RecoveryInstrument, parsed.instrument_id)
        if instrument.kind != "COST" or instrument.currency != parsed.currency:
            fail("recovery_cost_basis")
        prior = session.scalars(
            query(RecoveryRecord, access).where(
                RecoveryRecord.instrument_id == instrument.id, RecoveryRecord.kind == "cost"
            )
        ).all()
        if any(r.case_id != case.id for r in prior):
            fail("recovery_shared_cost_deferred")
        same = next(
            (r for r in prior if r.value["event_reference"] == parsed.event_reference), None
        )
        if same:
            if same.value == value:
                return same
            fail("recovery_economic_conflict")
        incurred = total([r.principal for r in prior if r.value["state"] == "INCURRED"])
        paid = total([r.principal for r in prior if r.value["state"] == "PAID"])
        for correction in prior:
            if correction.value["state"] == "REVERSED":
                original_cost = get(session, access, RecoveryRecord, correction.original_id)
                if original_cost.value["state"] == "INCURRED":
                    incurred = subtract(incurred, correction.principal)
                elif original_cost.value["state"] == "PAID":
                    paid = subtract(paid, correction.principal)
        if (
            parsed.scope
            != financial.get_evaluation(session, access, case.evaluation_id).snapshot[
                "billing_scope"
            ]["scope"]
        ):
            fail("recovery_scope_incompatible")
        if parsed.state == "INCURRED" and incurred > 0:
            fail("recovery_cost_duplicate")
        if parsed.state == "PAID" and total([paid, parsed.principal]) > incurred:
            fail("recovery_cost_budget")
        if parsed.state == "REVERSED":
            original = get(session, access, RecoveryRecord, parsed.original_id)
            reversals = [r.principal for r in prior if r.original_id == original.id]
            if (
                original.case_id != case.id
                or original.kind != "cost"
                or original.instrument_id != instrument.id
                or original.currency != parsed.currency
                or original.value["state"] == "REVERSED"
                or parsed.principal > subtract(original.principal, total(reversals))
            ):
                fail("recovery_cost_budget")
            components["original_id"] = original.id
        components.update(
            instrument_id=instrument.id, principal=parsed.principal, currency=parsed.currency
        )
    elif parsed.kind == "retire":
        successor = get(session, access, RecoveryCase, parsed.successor_case_id)
        link = get(session, access, ProofSuccessor, parsed.proof_successor_id)
        predecessor_proof = get(session, access, ProofPackage, link.predecessor_id)
        successor_proof = get(session, access, ProofPackage, link.successor_id)
        pf = get(session, access, ProofFamily, predecessor_proof.family_id)
        sf = get(session, access, ProofFamily, successor_proof.family_id)
        any_realized = session.scalar(
            query(RecoveryRecord, access)
            .where(RecoveryRecord.case_id == case.id, RecoveryRecord.kind == "realization")
            .limit(1)
        )
        if (
            any_realized
            or pf.evaluation_id != case.evaluation_id
            or sf.evaluation_id != successor.evaluation_id
        ):
            fail("recovery_successor_reconciliation_deferred")
    if value.get("economic"):
        economic_day(value["economic"])
        components["economic"] = value["economic"]
    if parsed.kind == "reversal" and parsed.reversal_type == "DE_RECOGNITION":
        components["economic"] = original.economic
    for field in ("principal", "gross", "tax", "fees", "withholding", "net_cash", "other"):
        if field not in components and value.get(field) is not None:
            components[field] = exact(value[field])
    sources = verified_sources(session, access, required_proposals, package, storage, budget)
    pins.setdefault("sources", sources)
    pins.setdefault("integrity", "VERIFIED")
    # Recheck actual byte captures after all gates. Shared fence holds every DB revision.
    verified_sources(session, access, required_proposals, package, storage, budget)
    if parsed.kind in {"readiness", "realization"}:
        current = authority(
            session,
            access,
            case,
            value if parsed.kind == "readiness" else ready.value,
            storage,
            budget,
            required_proposals,
        )
        for key in (
            "decision_id",
            "evaluation_fingerprint",
            "proof_id",
            "proof_fingerprint",
            "party_id",
        ):
            if current[key] != pins[key]:
                fail("recovery_stale_input")
    row = append(
        session,
        access,
        case,
        proposal.kind,
        value,
        body.reason,
        proposal=proposal,
        pins=pins,
        **components,
    )
    if parsed.kind == "alias":
        if not alias:
            session.add(
                RecoveryAlias(
                    organization_id=access.organization_id,
                    instrument_id=instrument.id,
                    record_id=row.id,
                    alias_hash=alias_hash,
                )
            )
            session.flush()
    return row


def credit_balance(session, access, case, instrument_id, budget):
    rows = session.scalars(
        query(RecoveryRecord, access)
        .where(RecoveryRecord.instrument_id == instrument_id)
        .order_by(RecoveryRecord.created_at)
        .limit(budget.limits.projection_records + 1)
    ).all()
    budget.bound(len(rows), "projection_records")
    if any(r.case_id != case.id and r.kind != "alias" for r in rows):
        fail("recovery_shared_allocation_deferred")
    issued = next((r.principal for r in reversed(rows) if r.kind == "instrument"), None)
    if issued is None:
        fail("recovery_credit_unresolved")
    changes = [issued]
    for row in rows:
        if row.kind == "realization" and not row.value.get("replaces_id"):
            changes.append(-row.amount)
        elif row.kind == "credit_state":
            if row.value["state"] in {"CANCELLED", "EXPIRED"}:
                changes.append(-row.principal)
            elif row.value["state"] == "RESTORED":
                changes.append(row.principal)
    return total(changes)


def operational(session, access, command, case_id, body):
    case = get(session, access, RecoveryCase, case_id)
    cas(session, access, case.id, body.expected_head)
    value = body.model_dump(mode="json", exclude={"expected_head", "reason"})
    if command == "lifecycle":
        if body.state == "CLOSED" and body.closure_reason is None:
            fail("recovery_closure_reason")
        prior = head(session, access, case.id, "lifecycle")
        if prior and prior.value["state"] == body.state:
            fail("recovery_lifecycle_conflict")
    elif command == "workflow" and body.assignee_id:
        if not session.scalar(
            query(OrganizationMembership, access).where(
                OrganizationMembership.user_id == body.assignee_id
            )
        ):
            fail("recovery_assignee_unavailable")
    elif command == "note" and body.replaces_id:
        original = get(session, access, RecoveryRecord, body.replaces_id)
        if (
            original.kind != "note"
            or original.case_id != case.id
            or (access.role not in {"owner", "admin"} and original.actor_id != access.user_id)
        ):
            fail("recovery_note_forbidden", status=403)
    return append(session, access, case, command, value, body.reason)


def serialize(row):
    result = {"id": str(row.id), "created_at": row.created_at.isoformat()}
    for key in (
        "evaluation_id",
        "case_id",
        "instrument_id",
        "previous_id",
        "original_id",
        "proposal_id",
        "actor_id",
        "audit_id",
    ):
        if hasattr(row, key):
            result[key] = str(getattr(row, key)) if getattr(row, key) else None
    for key in (
        "kind",
        "number",
        "currency",
        "namespace",
        "issuer",
        "reference",
        "reason",
        "value",
        "pins",
        "authority",
    ):
        if hasattr(row, key):
            result[key] = getattr(row, key)
    for key in ("amount", "principal", "gross", "tax", "fees", "withholding", "net_cash", "other"):
        if hasattr(row, key):
            result[key] = str(getattr(row, key)) if getattr(row, key) is not None else None
    if hasattr(row, "recorded_at"):
        result["recorded_at"] = row.recorded_at.isoformat()
        result["known_at"] = None
        result["economic"] = row.economic
    return result


def execute(session, access, command, target, body, key, storage, limits, budget=None):
    budget = budget or Budget(limits)
    admit(session, access, budget)
    final = command in {"approve", "lifecycle"} and not (
        command == "approve" and body.decision == "WITHDRAW"
    )
    financial.lock_authority(session, access, final=final)
    require_guards(session)
    membership = session.scalar(
        query(OrganizationMembership, access)
        .where(OrganizationMembership.user_id == access.user_id)
        .execution_options(populate_existing=True)
    )
    access = OrganizationAccess(
        access.organization_id, access.user_id, MembershipRole(membership.role)
    )
    request_hash = digest(
        {
            "command": command,
            "target": str(target) if target else None,
            "body": body.model_dump(mode="json"),
        }
    )
    old = session.scalar(
        query(RecoveryRequest, access).where(
            RecoveryRequest.actor_id == access.user_id, RecoveryRequest.request_key == key
        )
    )
    if old:
        if old.request_hash != request_hash:
            fail("recovery_request_conflict")
        return old.result
    counted = final and (command != "approve" or body.decision == "APPROVE")
    if command == "approve":
        approved = session.scalar(
            query(RecoveryRecord, access).where(RecoveryRecord.proposal_id == target)
        )
        proposed = get(session, access, RecoveryProposal, target)
        if approved is None and body.decision == "APPROVE":
            if proposed.kind == "realization":
                approved = semantic_realization(session, access, proposed.value)
            elif proposed.kind == "cost":
                prior = session.scalar(
                    query(RecoveryRecord, access)
                    .where(
                        RecoveryRecord.kind == "cost",
                        RecoveryRecord.instrument_id == UUID(proposed.value["instrument_id"]),
                        RecoveryRecord.value["event_reference"].astext
                        == proposed.value["event_reference"],
                    )
                    .limit(1)
                )
                if prior and prior.value == proposed.value:
                    approved = prior
        if approved:
            counted = False
    if counted:
        quota(session, access, budget)
    try:
        with session.begin_nested():
            if command == "create_case":
                row = create_case(session, access, body)
            elif command == "create_instrument":
                row = create_instrument(session, access, body)
            elif command == "prepare":
                row = prepare(session, access, target, body, budget)
            elif command == "approve":
                row = approve(session, access, target, body, storage, budget)
            elif command == "inspect":
                from app.recovery.reporting import current_observation

                case = get(session, access, RecoveryCase, target)
                cas(session, access, case.id, body.expected_head)
                _, value = current_observation(
                    session,
                    access,
                    case,
                    records(session, access, case.id, budget),
                    storage,
                    budget,
                )
                row = append(session, access, case, "observation", value, body.reason)
            else:
                text_bounds(body.model_dump(mode="json"), budget)
                row = operational(session, access, command, target, body)
            result = serialize(row)
            budget.bound(len(canonical(result)), "response_bytes")
            budget.check()
    except ProofError as exc:
        result = {"error": {"code": exc.code, "message": exc.message, "status": exc.status}}
    record = RecoveryRequest(
        organization_id=access.organization_id,
        actor_id=access.user_id,
        audit_id=uuid4(),
        request_key=key,
        request_hash=request_hash,
        command=command,
        counted=counted,
        result=result,
    )
    session.add(record)
    session.flush()
    return result
