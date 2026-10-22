"""Tenant-bound, append-only proof content, presentation and operation identities."""

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    LargeBinary,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdentityTimestamps
from app.db.models import OrganizationOwned


def tenant_reference(table, column, *, deferred=False, name=None):
    return ForeignKeyConstraint(
        ["organization_id", column],
        [f"{table}.organization_id", f"{table}.id"],
        deferrable=True if deferred else None,
        initially="DEFERRED" if deferred else None,
        name=name,
    )


class ProofFamily(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "proof_families"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "evaluation_id", "kind"),
        tenant_reference("financial_evaluations", "evaluation_id"),
        CheckConstraint(
            "kind IN ('MONETARY_FINDING_PROOF', 'ASSESSED_COMPARISON_EVIDENCE', "
            "'BLOCKED_ASSESSMENT_EVIDENCE')",
            name="proof_kind",
        ),
    )
    evaluation_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(String(40))
    actor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))


class ProofPackage(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "proof_packages"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "family_id", "id"),
        UniqueConstraint("organization_id", "family_id", "number"),
        UniqueConstraint("organization_id", "family_id", "fingerprint"),
        tenant_reference("proof_families", "family_id"),
        tenant_reference("financial_audit", "audit_id", deferred=True),
        ForeignKeyConstraint(
            ["organization_id", "family_id", "previous_id"],
            ["proof_packages.organization_id", "proof_packages.family_id", "proof_packages.id"],
        ),
        CheckConstraint("number > 0", name="proof_revision_positive"),
        CheckConstraint("fingerprint ~ '^[a-f0-9]{64}$'", name="proof_fingerprint"),
        CheckConstraint("completeness IN ('COMPLETE', 'INCOMPLETE')", name="proof_completeness"),
        CheckConstraint(
            "(number = 1 AND previous_id IS NULL AND revision_reason IS NULL) OR "
            "(number > 1 AND previous_id IS NOT NULL AND revision_reason IN "
            "('REPAIRED_EVIDENCE', 'SCHEMA_EVOLUTION', 'ASSEMBLY_EVOLUTION'))",
            name="proof_revision_reason",
        ),
    )
    family_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    number: Mapped[int]
    previous_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    revision_reason: Mapped[str | None] = mapped_column(String(32))
    actor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    audit_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    fingerprint: Mapped[str] = mapped_column(String(64))
    completeness: Mapped[str] = mapped_column(String(12))
    core: Mapped[dict] = mapped_column(JSONB)
    envelope: Mapped[dict] = mapped_column(JSONB)


class ProofBinding(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "proof_bindings"
    __table_args__ = (
        tenant_reference("proof_packages", "package_id"),
        tenant_reference("financial_revisions", "revision_id"),
        tenant_reference("financial_revision_evidence", "evidence_id"),
        tenant_reference("documents", "document_id"),
        ForeignKeyConstraint(
            ["organization_id", "document_id", "run_id", "field_id"],
            [
                "extracted_fields.organization_id",
                "extracted_fields.document_id",
                "extracted_fields.extraction_run_id",
                "extracted_fields.id",
            ],
        ),
        UniqueConstraint("organization_id", "package_id", "binding_id", "input_pointer"),
        CheckConstraint("(field_id IS NULL) = (run_id IS NULL)", name="proof_binding_lineage"),
    )
    package_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    revision_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    evidence_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    field_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    binding_id: Mapped[str] = mapped_column(String(64))
    input_pointer: Mapped[str] = mapped_column(String(2000))


class ProofEvent(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "proof_events"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "package_id", "id"),
        UniqueConstraint("organization_id", "package_id", "number"),
        CheckConstraint("number > 0", name="proof_event_number"),
        tenant_reference("proof_packages", "package_id"),
        tenant_reference("financial_audit", "audit_id", deferred=True),
        ForeignKeyConstraint(
            ["organization_id", "package_id", "previous_id"],
            ["proof_events.organization_id", "proof_events.package_id", "proof_events.id"],
        ),
        CheckConstraint(
            "kind IN ('annotation.appended', 'annotation.retracted', 'review.proposed', "
            "'review.finalized', 'disclosure.proposed', 'disclosure.approved', "
            "'artifact.downloaded', 'source.downloaded', 'integrity.observed')",
            name="proof_event_kind",
        ),
    )
    package_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    number: Mapped[int]
    previous_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    actor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    audit_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(String(40))
    detail: Mapped[dict] = mapped_column(JSONB)


class ProofArtifact(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "proof_artifacts"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "package_id", "content_hash"),
        tenant_reference("proof_packages", "package_id"),
        ForeignKeyConstraint(
            ["organization_id", "package_id", "disclosure_id"],
            ["proof_events.organization_id", "proof_events.package_id", "proof_events.id"],
        ),
        tenant_reference("financial_audit", "audit_id", deferred=True),
        CheckConstraint("content_hash ~ '^[a-f0-9]{64}$'", name="artifact_hash"),
        CheckConstraint("octet_length(content) > 0", name="artifact_nonempty"),
    )
    package_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    disclosure_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    actor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    audit_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    content_hash: Mapped[str] = mapped_column(String(64))
    # Private immutable bytes; every read goes through current authorization and hash checking.
    content: Mapped[bytes] = mapped_column(LargeBinary)


class ProofRequest(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "proof_requests"
    __table_args__ = (
        UniqueConstraint("organization_id", "request_key"),
        tenant_reference("financial_audit", "audit_id", deferred=True),
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    audit_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    request_key: Mapped[str] = mapped_column(String(36))
    request_hash: Mapped[str] = mapped_column(String(64))
    command: Mapped[str] = mapped_column(String(40))
    counted: Mapped[bool]
    result: Mapped[dict] = mapped_column(JSONB)


class ProofSuccessor(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "proof_successors"
    __table_args__ = (
        tenant_reference("proof_packages", "predecessor_id", name="fk_proof_successor_predecessor"),
        tenant_reference("proof_packages", "successor_id", name="fk_proof_successor_successor"),
        tenant_reference("financial_audit", "audit_id", deferred=True),
        UniqueConstraint("organization_id", "predecessor_id"),
        UniqueConstraint("organization_id", "successor_id"),
        CheckConstraint("predecessor_id <> successor_id", name="successor_distinct"),
    )
    predecessor_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    successor_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    actor_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    audit_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    reason: Mapped[str] = mapped_column(String(2000))
