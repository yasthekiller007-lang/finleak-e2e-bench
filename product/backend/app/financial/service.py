"""Tenant-serialized authority and immutable evaluations on PostgreSQL."""

import logging
from datetime import UTC, datetime
from time import perf_counter
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import OrganizationAccess
from app.db.models import (
    Document,
    ExtractedField,
    ExtractionRun,
    Organization,
    OrganizationMembership,
)
from app.financial.engine import (
    COMPILER_VERSION,
    RULE_VERSION,
    SNAPSHOT_VERSION,
    blocked,
    canonical,
    evaluate,
    fingerprint,
)
from app.financial.models import (
    FinancialEvaluation,
    FinancialFindingDecision,
    FinancialRevision,
    FinancialRevisionEvidence,
    ReviewedFinancialSource,
)
from app.financial.schema import (
    Association,
    BillingScope,
    CreateSource,
    Evaluate,
    FindingDecision,
    Packet,
    Reference,
    Review,
    Term,
)

logger = logging.getLogger("financial_leakage")


def fail(code: str, message: str, status=409):
    raise HTTPException(status, {"code": code, "message": message})


def lock_authority(session: Session, access: OrganizationAccess, *, final=False):
    from app.auth.access import tenant_active, user_active

    user_active(session, access.user_id)
    # Consistent lock order for every writer: organization, membership, then source.
    session.scalar(
        select(Organization).where(Organization.id == access.organization_id).with_for_update()
    )
    tenant_active(session, access.organization_id)
    membership = session.scalar(
        select(OrganizationMembership)
        .where(
            OrganizationMembership.organization_id == access.organization_id,
            OrganizationMembership.user_id == access.user_id,
        )
        .with_for_update(read=True)
        .execution_options(populate_existing=True)
    )
    if membership is None:
        fail("NOT_FOUND", "Organization not found", 404)
    if membership.role == "viewer" or (final and membership.role not in {"owner", "admin"}):
        fail(
            "FORBIDDEN",
            "Your role cannot grant financial authority"
            if final
            else "Your role cannot change financial records",
            403,
        )


def source(session, access, source_id):
    row = session.scalar(
        select(ReviewedFinancialSource).where(
            ReviewedFinancialSource.organization_id == access.organization_id,
            ReviewedFinancialSource.id == source_id,
        )
    )
    if row is None:
        fail("NOT_FOUND", "Reviewed financial source not found", 404)
    return row


def sources_query(access):
    return select(ReviewedFinancialSource).where(
        ReviewedFinancialSource.organization_id == access.organization_id
    )


def create_source(session: Session, access: OrganizationAccess, body: CreateSource):
    lock_authority(session, access)
    doc = session.scalar(
        select(Document).where(
            Document.organization_id == access.organization_id, Document.id == body.document_id
        )
    )
    if doc is None:
        fail("NOT_FOUND", "Document not found", 404)
    if doc.document_type.value != body.kind:
        fail(
            "SOURCE_KIND", "Review the document classification before creating its financial source"
        )
    existing = session.scalar(
        sources_query(access).where(
            ReviewedFinancialSource.document_id == body.document_id,
            ReviewedFinancialSource.kind == body.kind,
        )
    )
    if existing:
        return existing
    row = ReviewedFinancialSource(
        organization_id=access.organization_id,
        document_id=body.document_id,
        kind=body.kind,
        created_by=access.user_id,
    )
    session.add(row)
    session.flush()
    return row


def revisions(session, access, source_ids, *, authoritative=True):
    rows = session.scalars(
        select(FinancialRevision)
        .where(
            FinancialRevision.organization_id == access.organization_id,
            FinancialRevision.source_id.in_(source_ids),
        )
        .order_by(FinancialRevision.number.desc(), FinancialRevision.id)
    ).all()
    if len(rows) > 10000:
        fail("REVIEW_LIMIT", "Review history exceeds this V1 request limit", 422)
    heads = {}
    for row in rows:
        if authoritative and row.state == "prepared":
            continue
        heads.setdefault((row.source_id, row.kind, row.key), row)
    return list(heads.values())


def provenance(session, access, evidence):
    result = []
    for entry in evidence:
        doc = session.scalar(
            select(Document).where(
                Document.organization_id == access.organization_id, Document.id == entry.document_id
            )
        )
        if doc is None:
            fail("NOT_FOUND", "Evidence document not found", 404)
        item = entry.model_dump(mode="json") | {
            "sha256": doc.sha256,
            "document_type": doc.document_type.value,
            "available_at": doc.uploaded_at.isoformat(),
        }
        if entry.field_id:
            field = session.scalar(
                select(ExtractedField).where(
                    ExtractedField.organization_id == access.organization_id,
                    ExtractedField.document_id == doc.id,
                    ExtractedField.id == entry.field_id,
                )
            )
            if field is None:
                fail("NOT_FOUND", "Extracted evidence field not found", 404)
            run = session.scalar(
                select(ExtractionRun).where(
                    ExtractionRun.organization_id == access.organization_id,
                    ExtractionRun.document_id == doc.id,
                    ExtractionRun.id == field.extraction_run_id,
                )
            )
            if run is None or run.document_sha256 != doc.sha256:
                fail("STALE_EVIDENCE", "Extraction source hash no longer matches the document")
            item.update(
                {
                    "raw_value": field.raw_value,
                    "normalized_candidate": field.normalized_value,
                    "field_path": field.path,
                    "confidence": field.confidence,
                    "uncertainty": field.reason,
                    "source_location": field.source,
                    "run_id": str(run.id),
                    "run_version": run.version_number,
                    "parser_version": run.parser_version,
                    "extractor_version": run.extractor_version,
                    "schema_version": run.schema_version,
                    "extraction_available_at": field.created_at.isoformat(),
                }
            )
        else:
            item.update(
                {
                    "raw_value": entry.quote,
                    "normalized_candidate": None,
                    "source_location": entry.location,
                    "run_id": None,
                }
            )
        result.append(item)
    return sorted(result, key=canonical)


def review(session: Session, access: OrganizationAccess, source_id: UUID, body: Review, key: UUID):
    lock_authority(session, access, final=body.state != "prepared")
    owner = source(session, access, source_id)
    digest = fingerprint(
        {
            "source": str(source_id),
            "actor": str(access.user_id),
            "review": body.model_dump(mode="json"),
        }
    )
    previous_request = session.scalar(
        select(FinancialRevision).where(
            FinancialRevision.organization_id == access.organization_id,
            FinancialRevision.request_key == str(key),
        )
    )
    if previous_request:
        if previous_request.request_hash != digest:
            fail("IDEMPOTENCY_CONFLICT", "This request key was already used for a different review")
        return previous_request
    valid = {
        "contract": {"term", "reference", "packet"},
        "invoice": {"billing_scope", "reference", "association"},
    }
    if body.kind not in valid[owner.kind]:
        fail("SEMANTIC_TYPE", "This review does not belong to this financial source", 422)
    heads = revisions(session, access, [source_id], authoritative=False)
    previous = next((r for r in heads if r.kind == body.kind and r.key == body.key), None)
    if (previous.id if previous else None) != body.expected_revision:
        fail("STALE_INPUT", "Review revision changed. Reload before submitting a decision")
    if body.state == "revoked" and (
        previous is None or previous.state not in {"approved", "prepared"}
    ):
        fail("APPROVAL_REQUIRED", "Withdraw a current prepared review or revoke a current approval")
    if body.knowledge_cutoff.tzinfo is None or body.knowledge_cutoff > datetime.now(UTC):
        fail("KNOWLEDGE_CUTOFF", "Use an explicit timezone and an available evidence cutoff", 422)
    payload = body.model_dump(mode="json")
    if body.state == "revoked" and payload["value"] != previous.payload["value"]:
        fail(
            "REVOCATION_VALUE",
            "Withdrawal/revocation must retain the historical reviewed value",
            422,
        )
    payload["has_approval_history"] = body.state == "approved" or bool(
        previous
        and (previous.state == "approved" or previous.payload.get("has_approval_history", False))
    )
    grounded = provenance(session, access, body.evidence)
    for entry in grounded:
        if any(
            datetime.fromisoformat(entry[k]) > body.knowledge_cutoff
            for k in ("available_at", "extraction_available_at")
            if k in entry
        ):
            fail("KNOWLEDGE_CUTOFF", "Evidence was not available at the reviewed cutoff", 422)
    # Every supplied value leaf must have an explicit reviewed evidence mapping.
    supported = {p for e in body.evidence for p in e.supports}

    def leaves(value, prefix=""):
        if isinstance(value, dict):
            return {p for k, v in value.items() for p in leaves(v, f"{prefix}/{k}")}
        if isinstance(value, list):
            return {p for i, v in enumerate(value) for p in leaves(v, f"{prefix}/{i}")}
        return {prefix}

    if not leaves(payload["value"]) <= supported:
        fail(
            "EVIDENCE_MAPPING", "Map each reviewed value to the source supporting its meaning", 422
        )
    contract_id = None
    if isinstance(body.value, Packet):
        master = next(d.document_id for d in body.value.documents if d.role == "master")
        if master != owner.document_id:
            fail("PACKET_MASTER", "Packet master must be this stable contract source", 422)
        hashes = []
        for entry in body.value.documents:
            doc = session.scalar(
                select(Document).where(
                    Document.organization_id == access.organization_id,
                    Document.id == entry.document_id,
                )
            )
            if doc is None:
                fail("NOT_FOUND", "Packet document not found", 404)
            hashes.append({**entry.model_dump(mode="json"), "sha256": doc.sha256})
        payload["document_hashes"] = sorted(hashes, key=canonical)
    if isinstance(body.value, Association):
        contract = source(session, access, body.value.contract_source_id)
        if contract.kind != "contract":
            fail("ASSOCIATION_TYPE", "Association requires one reviewed contract source", 422)
        contract_id = contract.id
    row = FinancialRevision(
        organization_id=access.organization_id,
        source_id=source_id,
        contract_source_id=contract_id,
        kind=body.kind,
        key=body.key,
        number=previous.number + 1 if previous else 1,
        previous_id=previous.id if previous else None,
        state=body.state,
        actor_id=access.user_id,
        request_key=str(key),
        request_hash=digest,
        knowledge_cutoff=body.knowledge_cutoff,
        payload=payload,
        provenance=grounded,
    )
    session.add(row)
    session.flush()  # PostgreSQL inserts the audit event in the same transaction.
    for item in grounded:
        session.add(
            FinancialRevisionEvidence(
                organization_id=access.organization_id,
                revision_id=row.id,
                document_id=UUID(item["document_id"]),
                run_id=UUID(item["run_id"]) if item["run_id"] else None,
                field_id=UUID(item["field_id"]) if item["field_id"] else None,
                detail=item,
            )
        )
    session.flush()
    return row


def pinned_inputs(session, access, invoice):
    rows = revisions(session, access, [invoice.id], authoritative=False)
    association = next((r for r in rows if r.kind == "association" and r.state == "approved"), None)
    if association:
        source(session, access, association.contract_source_id)
        rows += revisions(session, access, [association.contract_source_id], authoritative=False)
    else:
        # These records can establish candidates/ambiguity only, never financial authority.
        candidates = session.scalars(
            sources_query(access).where(ReviewedFinancialSource.kind == "contract").limit(1001)
        ).all()
        if len(candidates) > 1000:
            fail("REVIEW_LIMIT", "Candidate review exceeds the bounded V1 request limit", 422)
        rows += revisions(session, access, [c.id for c in candidates], authoritative=False)
    return sorted(rows, key=lambda r: str(r.id))


def inputs_snapshot(rows):
    return [
        {
            "id": str(r.id),
            "source_id": str(r.source_id),
            "kind": r.kind,
            "key": r.key,
            "number": r.number,
            "state": r.state,
            "actor_id": str(r.actor_id),
            "created_at": r.created_at.isoformat(),
            "knowledge_cutoff": r.knowledge_cutoff.isoformat(),
            "payload": r.payload,
            "provenance": r.provenance,
        }
        for r in rows
    ]


def active_value(rows, kind, key=None):
    return next(
        (
            r
            for r in rows
            if r.kind == kind and (key is None or r.key == key) and r.state == "approved"
        ),
        None,
    )


def candidate_ids(rows, bill):
    return {
        r.source_id
        for r in rows
        if r.kind == "term"
        and r.state == "approved"
        and r.payload["value"].get("supplier_party") == bill.supplier_party
        and r.payload["value"].get("customer_party") == bill.customer_party
        and r.payload["value"].get("scope") == bill.scope
        and bill.supplier_party
        and bill.customer_party
    }


def run_engine(rows, scope_key, invoice):
    bill_row = active_value(rows, "billing_scope", scope_key)
    if bill_row is None:
        return blocked("UNAPPROVED_FACT"), None
    bill = BillingScope.model_validate(bill_row.payload["value"])
    all_bills = [
        BillingScope.model_validate(r.payload["value"])
        for r in rows
        if r.kind == "billing_scope" and r.state == "approved"
    ]
    if bill.allocation_parent:
        parent = next((b for b in all_bills if b.key == bill.allocation_parent), None)
        children = [b for b in all_bills if b.allocation_parent == bill.allocation_parent]
        if (
            parent is None
            or parent.quantity is None
            or parent.posted_amount is None
            or parent.service_from is None
            or parent.service_to is None
            or len(children) < 2
            or any(
                c.quantity is None
                or c.posted_amount is None
                or c.service_from is None
                or c.service_to is None
                or c.currency != parent.currency
                or c.unit != parent.unit
                or c.supplier_party != parent.supplier_party
                or c.customer_party != parent.customer_party
                for c in children
            )
        ):
            return blocked("ALLOCATION_REQUIRED"), bill
        from decimal import Decimal, localcontext

        with localcontext() as context:
            context.prec = 80
            if (
                sum((c.quantity for c in children), Decimal("0")) != parent.quantity
                or sum((c.posted_amount for c in children), Decimal("0")) != parent.posted_amount
            ):
                return blocked("ALLOCATION_REQUIRED"), bill
        ordered = sorted(children, key=lambda c: c.service_from)
        if (
            ordered[0].service_from != parent.service_from
            or ordered[-1].service_to != parent.service_to
            or any(
                left.service_to != right.service_from
                for left, right in zip(ordered, ordered[1:], strict=False)
            )
        ):
            return blocked("ALLOCATION_REQUIRED"), bill
        if parent.credits or any(c.credits for c in children):
            return blocked("CREDIT_ALLOCATION_UNRESOLVED"), bill
    if any(b.allocation_parent == bill.key for b in all_bills):
        return blocked("OVERLAPPING_SCOPE"), bill
    for other in all_bills:
        if other.key == bill.key or other.key == bill.allocation_parent:
            continue
        if set(other.members) & set(bill.members) or {c.key for c in other.credits} & {
            c.key for c in bill.credits
        }:
            return blocked("OVERLAPPING_SCOPE"), bill
    if any(
        r.kind == "reference"
        and (
            r.state == "prepared"
            or (r.state == "revoked" and r.payload.get("has_approval_history", True))
        )
        for r in rows
    ):
        return blocked("UNAPPROVED_FACT"), bill
    for r in rows:
        if r.kind == "billing_scope" and r.state == "prepared" and r.key != bill.key:
            other = BillingScope.model_validate(r.payload["value"])
            if (
                set(other.members) & set(bill.members)
                or {c.key for c in other.credits} & {c.key for c in bill.credits}
                or other.allocation_parent == bill.key
                or other.key == bill.allocation_parent
                or (bill.allocation_parent and other.allocation_parent == bill.allocation_parent)
            ):
                return blocked("INPUT_CONFLICT"), bill
    association_row = active_value(rows, "association")
    if association_row is None:
        candidates = candidate_ids(rows, bill)
        return blocked("AMBIGUOUS_MATCH" if len(candidates) > 1 else "UNMATCHED"), bill
    association = Association.model_validate(association_row.payload["value"])
    contract_rows = [r for r in rows if r.source_id == association.contract_source_id]
    reference_row = active_value(contract_rows, "reference")
    reference = Reference.model_validate(reference_row.payload["value"]) if reference_row else None
    invoice_reference = active_value([r for r in rows if r.source_id == invoice.id], "reference")
    invoice_ref = (
        Reference.model_validate(invoice_reference.payload["value"]) if invoice_reference else None
    )
    contract_refs = set(bill.contract_references)
    po_refs = set(bill.po_references)
    if invoice_ref:
        if invoice_ref.contract_reference:
            contract_refs.add(invoice_ref.contract_reference)
        if invoice_ref.po_reference:
            po_refs.add(invoice_ref.po_reference)
    if (
        len(contract_refs) > 1
        or len(po_refs) > 1
        or (contract_refs and (not reference or contract_refs != {reference.contract_reference}))
        or (po_refs and (not reference or po_refs != {reference.po_reference}))
    ):
        return blocked("CONFLICTING_IDENTIFIERS"), bill
    if association.method == "exact_reference" and (
        not association.identifier
        or contract_refs != {association.identifier}
        or not reference
        or reference.contract_reference != association.identifier
    ):
        return blocked("AMBIGUOUS_MATCH"), bill
    if association.method == "approved_po" and (
        not association.identifier
        or po_refs != {association.identifier}
        or not reference
        or reference.po_reference != association.identifier
    ):
        return blocked("AMBIGUOUS_MATCH"), bill
    packet_row = active_value(contract_rows, "packet")
    if packet_row is None:
        return blocked("PACKET_INCOMPLETE"), bill
    packet = Packet.model_validate(packet_row.payload["value"])
    scoped_term_rows = [
        r
        for r in contract_rows
        if r.kind == "term" and r.payload["value"].get("scope") == bill.scope
    ]
    if any(
        r.state == "prepared"
        or (r.state == "revoked" and r.payload.get("has_approval_history", True))
        for r in scoped_term_rows
    ):
        return blocked("UNAPPROVED_FACT"), bill
    terms_rows = [r for r in scoped_term_rows if r.state == "approved"]
    packet_docs = {str(d.document_id) for d in packet.documents}
    if any(str(e["document_id"]) not in packet_docs for r in terms_rows for e in r.provenance):
        return blocked("PACKET_INCOMPLETE"), bill
    for i, _component in enumerate(bill.base_components):
        path = f"/base_components/{i}/contractual_gross"
        if not any(
            e["document_id"] in packet_docs and path in e["supports"] for e in bill_row.provenance
        ):
            return blocked("DISCOUNT_BASE_UNRESOLVED"), bill
    terms = tuple(Term.model_validate(r.payload["value"]) for r in terms_rows)
    return evaluate(terms, bill, packet), bill


def semantic_inputs(rows, invoice, scope_key):
    """Separate calculation/guard inputs from disjoint contextual records."""
    bill_row = next(
        (
            r
            for r in rows
            if r.source_id == invoice.id and r.kind == "billing_scope" and r.key == scope_key
        ),
        None,
    )
    bill = BillingScope.model_validate(bill_row.payload["value"]) if bill_row else None
    association = next(
        (r for r in rows if r.source_id == invoice.id and r.kind == "association"), None
    )
    contract_id = (
        association.contract_source_id if association and association.state == "approved" else None
    )
    selected = []
    for row in rows:
        include = (
            row.source_id == invoice.id
            and row.kind in {"reference", "association"}
            and (row.state != "revoked" or row.payload.get("has_approval_history", True))
        )
        if row.kind == "billing_scope" and row.source_id == invoice.id:
            other = BillingScope.model_validate(row.payload["value"])
            include = row.key == scope_key or (
                row.state != "revoked"
                and bill is not None
                and (
                    bool(set(other.members) & set(bill.members))
                    or bool({c.key for c in other.credits} & {c.key for c in bill.credits})
                    or other.key == bill.allocation_parent
                    or other.allocation_parent == bill.key
                    or (
                        bill.allocation_parent is not None
                        and other.allocation_parent == bill.allocation_parent
                    )
                )
            )
        elif row.source_id == contract_id:
            include = (
                row.kind in {"reference", "packet"}
                and (row.state != "revoked" or row.payload.get("has_approval_history", True))
            ) or (
                row.kind == "term"
                and (row.state != "revoked" or row.payload.get("has_approval_history", True))
                and bill is not None
                and row.payload["value"].get("scope") == bill.scope
            )
        elif contract_id is None and row.kind == "term" and bill:
            include = (
                row.payload["value"].get("supplier_party") == bill.supplier_party
                and row.payload["value"].get("customer_party") == bill.customer_party
                and row.payload["value"].get("scope") == bill.scope
            )
        if include:
            selected.append(row)
    return selected


def semantic_snapshot(rows, invoice, organization_id, scope_key):
    return {
        "schema": SNAPSHOT_VERSION,
        "compiler": COMPILER_VERSION,
        "rules": RULE_VERSION,
        "invoice_source_id": str(invoice.id),
        "organization_id": str(organization_id),
        "scope_key": scope_key,
        "inputs": inputs_snapshot(semantic_inputs(rows, invoice, scope_key)),
    }


def evaluate_scope(session: Session, access: OrganizationAccess, source_id: UUID, body: Evaluate):
    started = perf_counter()
    lock_authority(session, access, final=True)
    invoice = source(session, access, source_id)
    if invoice.kind != "invoice":
        fail("SOURCE_KIND", "Evaluate an invoice source", 422)
    rows = pinned_inputs(session, access, invoice)
    pinned = {r.id for r in rows}
    if pinned != set(body.expected_revisions):
        fail("STALE_INPUT", "Approved inputs changed. Reload their revisions before evaluation")
    snapshot = {
        "schema": SNAPSHOT_VERSION,
        "compiler": COMPILER_VERSION,
        "rules": RULE_VERSION,
        "invoice_source_id": str(invoice.id),
        "organization_id": str(access.organization_id),
        "scope_key": body.scope_key,
        "inputs": inputs_snapshot(rows),
    }
    semantic = semantic_snapshot(rows, invoice, access.organization_id, body.scope_key)
    snapshot["calculation_driving_revision_ids"] = [r["id"] for r in semantic["inputs"]]
    digest = fingerprint(semantic)
    existing = session.scalar(
        select(FinancialEvaluation).where(
            FinancialEvaluation.organization_id == access.organization_id,
            FinancialEvaluation.fingerprint == digest,
        )
    )
    result, bill = run_engine(rows, body.scope_key, invoice)
    # Final fence: verify heads AND evidence hashes, while the tenant lock is still held.
    current = pinned_inputs(session, access, invoice)
    if {r.id for r in current} != pinned:
        fail("STALE_INPUT", "Financial revisions changed during assessment")
    hashes = {e["document_id"]: e["sha256"] for r in rows for e in r.provenance}
    for row in rows:
        for doc in row.payload.get("document_hashes", []):
            if doc["document_id"] in hashes and hashes[doc["document_id"]] != doc["sha256"]:
                fail("STALE_INPUT", "Evidence hash conflict")
            hashes[doc["document_id"]] = doc["sha256"]
    for doc_id, sha in hashes.items():
        doc = session.scalar(
            select(Document)
            .where(Document.organization_id == access.organization_id, Document.id == UUID(doc_id))
            .with_for_update(read=True)
        )
        if doc is None or doc.sha256 != sha:
            fail("STALE_INPUT", "Source evidence changed during assessment")
    if existing:
        return existing
    snapshot["calculation"] = result.trace
    snapshot["billing_scope"] = bill.model_dump(mode="json") if bill else None
    snapshot["match_outcome"] = (
        "AMBIGUOUS"
        if result.reason == "AMBIGUOUS_MATCH"
        else "NEEDS_REVIEW"
        if result.reason == "CONFLICTING_IDENTIFIERS"
        else "MATCHED"
        if active_value(rows, "association")
        else "CANDIDATE"
        if bill and candidate_ids(rows, bill)
        else "UNMATCHED"
    )
    snapshot["coverage"] = "Only the named, approved, non-overlapping billing scope is assessed."
    row = FinancialEvaluation(
        organization_id=access.organization_id,
        invoice_source_id=invoice.id,
        scope_key=body.scope_key,
        actor_id=access.user_id,
        fingerprint=digest,
        outcome=result.outcome,
        reason_code=result.reason,
        explanation=result.explanation,
        currency=result.currency,
        expected=result.expected,
        actual=result.actual,
        discrepancy=result.discrepancy,
        potential=result.potential,
        snapshot=snapshot,
    )
    session.add(row)
    session.flush()
    logger.info(
        "financial_evaluation_created",
        extra={
            "organization_id": str(access.organization_id),
            "evaluation_id": str(row.id),
            "rule_version": RULE_VERSION,
            "outcome": result.outcome,
            "duration_ms": round((perf_counter() - started) * 1000),
        },
    )
    return row


def is_stale(session, access, evaluation):
    invoice = source(session, access, evaluation.invoice_source_id)
    current = pinned_inputs(session, access, invoice)
    return (
        fingerprint(
            semantic_snapshot(current, invoice, access.organization_id, evaluation.scope_key)
        )
        != evaluation.fingerprint
    )


def evaluation_query(access):
    return select(FinancialEvaluation).where(
        FinancialEvaluation.organization_id == access.organization_id
    )


def get_evaluation(session, access, evaluation_id):
    row = session.scalar(evaluation_query(access).where(FinancialEvaluation.id == evaluation_id))
    if row is None:
        fail("NOT_FOUND", "Evaluation not found", 404)
    return row


def latest_decision(session, access, evaluation_id):
    return session.scalar(
        select(FinancialFindingDecision)
        .where(
            FinancialFindingDecision.organization_id == access.organization_id,
            FinancialFindingDecision.evaluation_id == evaluation_id,
        )
        .order_by(FinancialFindingDecision.number.desc())
        .limit(1)
    )


def decide(session, access, evaluation_id, body: FindingDecision):
    lock_authority(session, access, final=True)
    row = get_evaluation(session, access, evaluation_id)
    if row.potential is None:
        fail("NOT_FINDING", "This assessment has no monetary finding", 422)
    if is_stale(session, access, row):
        fail("STALE_INPUT", "Reassess changed inputs before validating this finding")
    previous = latest_decision(session, access, row.id)
    if (previous.id if previous else None) != body.expected_decision:
        fail("STALE_INPUT", "Finding review changed. Reload before deciding")
    decision = FinancialFindingDecision(
        organization_id=access.organization_id,
        evaluation_id=row.id,
        actor_id=access.user_id,
        number=previous.number + 1 if previous else 1,
        status=body.status,
        reason=body.reason,
    )
    session.add(decision)
    session.flush()
    return decision


def serialize_evaluation(session, access, row, *, detail=False):
    from app.financial.presentation import queue_context

    decision = latest_decision(session, access, row.id)
    stale = is_stale(session, access, row)
    result = {
        "id": str(row.id),
        "invoice_source_id": str(row.invoice_source_id),
        "scope_key": row.scope_key,
        "outcome": row.outcome,
        "reason_code": row.reason_code,
        "explanation": row.explanation,
        "currency": row.currency,
        "expected": format(row.expected, ".6f") if row.expected is not None else None,
        "actual": format(row.actual, ".6f") if row.actual is not None else None,
        "discrepancy": format(row.discrepancy, ".6f") if row.discrepancy is not None else None,
        "potential": format(row.potential, ".6f") if row.potential is not None else None,
        "status": "needs_review"
        if stale and row.potential
        else (decision.status if decision else "detected" if row.potential else None),
        "stale": stale,
        "decision_id": str(decision.id) if decision else None,
        "created_at": row.created_at.isoformat(),
        "queue_context": queue_context(row.snapshot, row.invoice_source_id),
    }
    billed_scope = row.snapshot.get("billing_scope") or {}
    selected_keys = set((row.snapshot.get("calculation") or {}).get("economic_dates", {}))
    rates = [
        r["payload"]["value"].get("rate")
        for r in row.snapshot["inputs"]
        if r["kind"] == "term"
        and r["key"] in selected_keys
        and r["payload"]["value"].get("family") == "unit_price"
    ]
    result["scope_summary"] = {
        "label": billed_scope.get("label"),
        "quantity": billed_scope.get("quantity"),
        "unit": billed_scope.get("unit"),
        "contracted_rate": rates[0] if len(rates) == 1 else None,
        "billed_rate": billed_scope.get("billed_rate"),
    }
    if detail:
        result["snapshot"] = row.snapshot
        result["fingerprint"] = row.fingerprint
    return result
