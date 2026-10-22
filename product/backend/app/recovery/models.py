"""Stable economic identities and immutable reviewed authority/history."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdentityTimestamps
from app.db.models import OrganizationOwned
from app.db.types import ExactNumeric
from app.proof.models import tenant_reference


class RecoveryCase(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "recovery_cases"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "evaluation_id"),
        tenant_reference("financial_evaluations", "evaluation_id"),
        tenant_reference("financial_audit", "audit_id", deferred=True),
    )
    evaluation_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    actor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    audit_id: Mapped[uuid.UUID] = mapped_column(Uuid)


class RecoveryInstrument(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "recovery_instruments"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "identity_hash"),
        tenant_reference("financial_audit", "audit_id", deferred=True),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="instrument_currency"),
        CheckConstraint(
            "kind IN ('CASH','CREDIT','LIABILITY','COST','SETTLEMENT')", name="instrument_kind"
        ),
        CheckConstraint("identity_hash ~ '^[a-f0-9]{64}$'", name="instrument_identity"),
    )
    kind: Mapped[str] = mapped_column(String(16))
    namespace: Mapped[str] = mapped_column(String(120))
    issuer: Mapped[str] = mapped_column(String(120))
    reference: Mapped[str] = mapped_column(String(120))
    currency: Mapped[str] = mapped_column(String(3))
    identity_hash: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    audit_id: Mapped[uuid.UUID] = mapped_column(Uuid)


class RecoveryProposal(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "recovery_proposals"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "case_id", "semantic_hash"),
        tenant_reference("recovery_cases", "case_id"),
        tenant_reference("financial_audit", "audit_id", deferred=True),
        CheckConstraint("semantic_hash ~ '^[a-f0-9]{64}$'", name="proposal_hash"),
    )
    case_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    actor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    audit_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(String(24))
    semantic_hash: Mapped[str] = mapped_column(String(64))
    value: Mapped[dict] = mapped_column(JSONB)
    authority: Mapped[dict] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(String(4000))


class RecoveryEvidence(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "recovery_evidence"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "proposal_id", "document_id", "binding_hash"),
        tenant_reference("recovery_proposals", "proposal_id"),
        tenant_reference("documents", "document_id"),
        CheckConstraint("sha256 ~ '^[a-f0-9]{64}$'", name="source_hash"),
        CheckConstraint("file_size >= 0", name="source_size"),
    )
    proposal_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    sha256: Mapped[str] = mapped_column(String(64))
    file_size: Mapped[int]
    media_type: Mapped[str] = mapped_column(String(120))
    binding_hash: Mapped[str] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSONB)


class RecoveryRecord(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "recovery_records"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "case_id", "number"),
        UniqueConstraint("organization_id", "proposal_id"),
        tenant_reference("recovery_cases", "case_id"),
        tenant_reference("recovery_records", "previous_id", name="fk_recovery_record_previous"),
        tenant_reference("recovery_records", "original_id", name="fk_recovery_record_original"),
        tenant_reference("recovery_instruments", "instrument_id"),
        tenant_reference("recovery_proposals", "proposal_id"),
        tenant_reference("financial_audit", "audit_id", deferred=True),
        CheckConstraint("number > 0", name="record_number"),
        CheckConstraint("currency IS NULL OR currency ~ '^[A-Z]{3}$'", name="record_currency"),
        CheckConstraint(
            "(kind IN ('realization','reversal')) = (amount IS NOT NULL)",
            name="allocation_presence",
        ),
        CheckConstraint("kind <> 'realization' OR amount > 0", name="realization_positive"),
        CheckConstraint(
            "kind <> 'reversal' OR (amount < 0 AND original_id IS NOT NULL)",
            name="reversal_negative",
        ),
        CheckConstraint(
            "kind NOT IN ('realization','reversal') OR instrument_id IS NOT NULL",
            name="allocation_instrument",
        ),
        CheckConstraint("principal IS NULL OR principal >= 0", name="principal_nonnegative"),
        CheckConstraint(
            "kind IN ('readiness','party','party_revoked','instrument','alias','credit_state',"
            "'claim','vendor','realization','reversal','cost','lifecycle',"
            "'workflow','note','observation','rejected','withdrawn','retire')",
            name="record_kind",
        ),
    )
    case_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    number: Mapped[int]
    previous_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    original_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    instrument_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    proposal_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    actor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    audit_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(String(24))
    amount: Mapped[Decimal | None] = mapped_column(ExactNumeric(20, 6))
    principal: Mapped[Decimal | None] = mapped_column(ExactNumeric(20, 6))
    gross: Mapped[Decimal | None] = mapped_column(ExactNumeric(20, 6))
    tax: Mapped[Decimal | None] = mapped_column(ExactNumeric(20, 6))
    fees: Mapped[Decimal | None] = mapped_column(ExactNumeric(20, 6))
    withholding: Mapped[Decimal | None] = mapped_column(ExactNumeric(20, 6))
    net_cash: Mapped[Decimal | None] = mapped_column(ExactNumeric(20, 6))
    other: Mapped[Decimal | None] = mapped_column(ExactNumeric(20, 6))
    currency: Mapped[str | None] = mapped_column(String(3))
    economic: Mapped[dict | None] = mapped_column(JSONB)
    # clock_timestamp is assigned by the guard; callers cannot backdate knowledge.
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    value: Mapped[dict] = mapped_column(JSONB)
    pins: Mapped[dict] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(String(4000))


class RecoveryAlias(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "recovery_aliases"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "alias_hash"),
        tenant_reference("recovery_instruments", "instrument_id"),
        tenant_reference("recovery_records", "record_id"),
    )
    instrument_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    record_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    alias_hash: Mapped[str] = mapped_column(String(64))


class RecoveryRequest(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "recovery_requests"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "actor_id", "request_key"),
        tenant_reference("financial_audit", "audit_id", deferred=True),
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    audit_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    request_key: Mapped[uuid.UUID] = mapped_column(Uuid)
    request_hash: Mapped[str] = mapped_column(String(64))
    command: Mapped[str] = mapped_column(String(32))
    counted: Mapped[bool]
    result: Mapped[dict] = mapped_column(JSONB)


class RecoveryPublication(OrganizationOwned, IdentityTimestamps, Base):
    """Durable actual commit time; never substitutes insert time for known-at."""

    __tablename__ = "recovery_publications"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "case_id"),
        UniqueConstraint("organization_id", "record_id"),
        tenant_reference("recovery_cases", "case_id"),
        tenant_reference("recovery_records", "record_id"),
        tenant_reference("financial_audit", "audit_id", deferred=True),
        CheckConstraint("(case_id IS NULL) <> (record_id IS NULL)", name="publication_subject"),
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    record_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    audit_id: Mapped[uuid.UUID] = mapped_column(Uuid)
