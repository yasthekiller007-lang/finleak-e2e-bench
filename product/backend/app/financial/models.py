"""Stable reviewed sources and append-only financial records."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdentityTimestamps
from app.db.models import OrganizationOwned
from app.db.types import ExactNumeric


class ReviewedFinancialSource(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "reviewed_financial_sources"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "document_id", "kind"),
        ForeignKeyConstraint(
            ["organization_id", "document_id"], ["documents.organization_id", "documents.id"]
        ),
        CheckConstraint("kind IN ('contract', 'invoice')", name="source_kind"),
    )
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(String(12))
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))


class FinancialRevision(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "financial_revisions"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "source_id", "id"),
        UniqueConstraint("organization_id", "source_id", "kind", "key", "number"),
        UniqueConstraint("organization_id", "request_key"),
        ForeignKeyConstraint(
            ["organization_id", "source_id"],
            ["reviewed_financial_sources.organization_id", "reviewed_financial_sources.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "source_id", "previous_id"],
            [
                "financial_revisions.organization_id",
                "financial_revisions.source_id",
                "financial_revisions.id",
            ],
        ),
        ForeignKeyConstraint(
            ["organization_id", "contract_source_id"],
            ["reviewed_financial_sources.organization_id", "reviewed_financial_sources.id"],
            name="fk_financial_revision_contract_source",
        ),
        CheckConstraint("number > 0", name="revision_positive"),
        CheckConstraint(
            "kind IN ('term', 'billing_scope', 'reference', 'packet', 'association')",
            name="revision_kind",
        ),
        CheckConstraint("state IN ('prepared', 'approved', 'revoked')", name="revision_state"),
    )
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    contract_source_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(String(20))
    key: Mapped[str] = mapped_column(String(120))
    number: Mapped[int]
    previous_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    state: Mapped[str] = mapped_column(String(12))
    actor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    request_key: Mapped[str] = mapped_column(String(36))
    request_hash: Mapped[str] = mapped_column(String(64))
    knowledge_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Schema-versioned typed decimal strings retain source precision, never JSON floats.
    payload: Mapped[dict] = mapped_column(JSONB)
    provenance: Mapped[list] = mapped_column(JSONB)


class FinancialEvaluation(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "financial_evaluations"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "fingerprint"),
        ForeignKeyConstraint(
            ["organization_id", "invoice_source_id"],
            ["reviewed_financial_sources.organization_id", "reviewed_financial_sources.id"],
        ),
        CheckConstraint("currency IS NULL OR currency ~ '^[A-Z]{3}$'", name="currency_format"),
        CheckConstraint("potential IS NULL OR potential > 0", name="potential_positive"),
        CheckConstraint(
            "(outcome = 'POTENTIAL_LEAKAGE') = (potential IS NOT NULL)", name="finding_presence"
        ),
    )
    invoice_source_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    scope_key: Mapped[str] = mapped_column(String(120))
    actor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    fingerprint: Mapped[str] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(32))
    reason_code: Mapped[str] = mapped_column(String(64))
    explanation: Mapped[str] = mapped_column(String(2000))
    currency: Mapped[str | None] = mapped_column(String(3))
    expected: Mapped[Decimal | None] = mapped_column(ExactNumeric(20, 6))
    actual: Mapped[Decimal | None] = mapped_column(ExactNumeric(20, 6))
    discrepancy: Mapped[Decimal | None] = mapped_column(ExactNumeric(20, 6))
    potential: Mapped[Decimal | None] = mapped_column(ExactNumeric(20, 6))
    snapshot: Mapped[dict] = mapped_column(JSONB)


class FinancialAudit(OrganizationOwned, Base):
    __tablename__ = "financial_audit"
    __table_args__ = (UniqueConstraint("organization_id", "id"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(60))
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    detail: Mapped[dict] = mapped_column(JSONB)


class FinancialFindingDecision(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "financial_finding_decisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "evaluation_id"],
            ["financial_evaluations.organization_id", "financial_evaluations.id"],
        ),
        UniqueConstraint("organization_id", "evaluation_id", "number"),
        CheckConstraint(
            "status IN ('confirmed', 'false_positive', 'needs_review')", name="finding_status"
        ),
    )
    evaluation_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    actor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    number: Mapped[int]
    status: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(2000))


class FinancialRevisionEvidence(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "financial_revision_evidence"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        ForeignKeyConstraint(
            ["organization_id", "revision_id"],
            ["financial_revisions.organization_id", "financial_revisions.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "document_id"], ["documents.organization_id", "documents.id"]
        ),
        ForeignKeyConstraint(
            ["organization_id", "document_id", "run_id"],
            [
                "extraction_runs.organization_id",
                "extraction_runs.document_id",
                "extraction_runs.id",
            ],
        ),
        ForeignKeyConstraint(
            ["organization_id", "document_id", "run_id", "field_id"],
            [
                "extracted_fields.organization_id",
                "extracted_fields.document_id",
                "extracted_fields.extraction_run_id",
                "extracted_fields.id",
            ],
        ),
        CheckConstraint("(field_id IS NULL) = (run_id IS NULL)", name="evidence_lineage"),
    )
    revision_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    field_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    detail: Mapped[dict] = mapped_column(JSONB)
