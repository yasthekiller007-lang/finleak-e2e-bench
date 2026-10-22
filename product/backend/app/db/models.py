import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdentityTimestamps
from app.db.types import ExactNumeric
from app.domain.types import CaseStatus, DocumentType, Priority, ProcessingStatus, VersionKind


def enum_type(enum_class: type, name: str) -> Enum:
    return Enum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        values_callable=lambda cls: [entry.value for entry in cls],
    )


class OrganizationOwned:
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id"), nullable=False, index=True
    )


class User(IdentityTimestamps, Base):
    __tablename__ = "users"
    email: Mapped[str | None] = mapped_column(String(320))
    display_name: Mapped[str] = mapped_column(String(200))


class UserIdentity(IdentityTimestamps, Base):
    __tablename__ = "user_identities"
    __table_args__ = (UniqueConstraint("issuer", "subject"),)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    issuer: Mapped[str] = mapped_column(String(512))
    subject: Mapped[str] = mapped_column(String(255))


class Organization(IdentityTimestamps, Base):
    __tablename__ = "organizations"
    name: Mapped[str] = mapped_column(String(200))


class OrganizationMembership(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id"),
        CheckConstraint("role IN ('owner', 'admin', 'analyst', 'viewer')", name="membership_role"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="analyst", server_default="analyst")


class Document(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "storage_key"),
        CheckConstraint("file_size >= 0", name="file_size_nonnegative"),
        CheckConstraint("sha256 ~ '^[a-f0-9]{64}$'", name="sha256_format"),
        UniqueConstraint("organization_id", "sha256"),
    )
    original_filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(127))
    file_size: Mapped[int] = mapped_column(BigInteger)
    storage_key: Mapped[str] = mapped_column(String(512))
    sha256: Mapped[str] = mapped_column(String(64))
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))
    document_type: Mapped[DocumentType] = mapped_column(enum_type(DocumentType, "document_type"))
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        enum_type(ProcessingStatus, "processing_status"),
        default=ProcessingStatus.PENDING,
        server_default="pending",
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Contract(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "contracts"
    __table_args__ = (UniqueConstraint("organization_id", "id"),)
    title: Mapped[str] = mapped_column(String(255))
    counterparty_name: Mapped[str] = mapped_column(String(255))
    external_reference: Mapped[str | None] = mapped_column(String(255))


class ContractVersion(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "contract_versions"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "contract_id", "version_number"),
        ForeignKeyConstraint(
            ["organization_id", "contract_id"], ["contracts.organization_id", "contracts.id"]
        ),
        ForeignKeyConstraint(
            ["organization_id", "document_id"], ["documents.organization_id", "documents.id"]
        ),
        CheckConstraint("version_number > 0", name="positive_version"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from", name="effective_interval"
        ),
        CheckConstraint(
            "(agreed_amount IS NULL) = (currency IS NULL)", name="amount_currency_pair"
        ),
        CheckConstraint("currency IS NULL OR currency ~ '^[A-Z]{3}$'", name="currency_format"),
        Index(
            "ix_versions_org_contract_effective", "organization_id", "contract_id", "effective_from"
        ),
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    version_number: Mapped[int]
    kind: Mapped[VersionKind] = mapped_column(enum_type(VersionKind, "version_kind"))
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    terms_text: Mapped[str | None] = mapped_column(Text)
    agreed_amount: Mapped[Decimal | None] = mapped_column(ExactNumeric(20, 6))
    currency: Mapped[str | None] = mapped_column(String(3))


class Invoice(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "id", "currency"),
        ForeignKeyConstraint(
            ["organization_id", "document_id"], ["documents.organization_id", "documents.id"]
        ),
        ForeignKeyConstraint(
            ["organization_id", "contract_id"], ["contracts.organization_id", "contracts.id"]
        ),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_format"),
    )
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    contract_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    invoice_number: Mapped[str] = mapped_column(String(255))
    supplier_name: Mapped[str] = mapped_column(String(255))
    issued_on: Mapped[date] = mapped_column(Date)
    due_on: Mapped[date | None] = mapped_column(Date)
    total_amount: Mapped[Decimal] = mapped_column(ExactNumeric(20, 6))
    currency: Mapped[str] = mapped_column(String(3))


class InvoiceLineItem(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "invoice_line_items"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "invoice_id", "line_number"),
        ForeignKeyConstraint(
            ["organization_id", "invoice_id", "currency"],
            ["invoices.organization_id", "invoices.id", "invoices.currency"],
        ),
        CheckConstraint("line_number > 0", name="positive_line_number"),
        CheckConstraint("quantity > 0", name="positive_quantity"),
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    line_number: Mapped[int]
    description: Mapped[str] = mapped_column(Text)
    quantity: Mapped[Decimal] = mapped_column(ExactNumeric(20, 6))
    unit_amount: Mapped[Decimal] = mapped_column(ExactNumeric(20, 6))
    line_amount: Mapped[Decimal] = mapped_column(ExactNumeric(20, 6))
    currency: Mapped[str] = mapped_column(String(3))


class LeakageCase(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "leakage_cases"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "id", "currency"),
        ForeignKeyConstraint(
            ["organization_id", "contract_id"], ["contracts.organization_id", "contracts.id"]
        ),
        ForeignKeyConstraint(
            ["organization_id", "invoice_id", "currency"],
            ["invoices.organization_id", "invoices.id", "invoices.currency"],
        ),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_format"),
        CheckConstraint("potential_exposure >= 0", name="potential_nonnegative"),
        CheckConstraint("validated_exposure >= 0", name="validated_nonnegative"),
        CheckConstraint("recovered_amount >= 0", name="recovered_nonnegative"),
        CheckConstraint("confidence_score BETWEEN 0 AND 1", name="confidence_range"),
        Index("ix_cases_org_status", "organization_id", "status"),
    )
    contract_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    category: Mapped[str] = mapped_column(String(100))
    potential_exposure: Mapped[Decimal] = mapped_column(ExactNumeric(20, 6))
    validated_exposure: Mapped[Decimal | None] = mapped_column(ExactNumeric(20, 6))
    recovered_amount: Mapped[Decimal] = mapped_column(ExactNumeric(20, 6), default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(3))
    confidence_score: Mapped[Decimal | None] = mapped_column(ExactNumeric(5, 4))
    priority: Mapped[Priority] = mapped_column(
        enum_type(Priority, "case_priority"), default=Priority.NORMAL, server_default="normal"
    )
    status: Mapped[CaseStatus] = mapped_column(
        enum_type(CaseStatus, "case_status"), default=CaseStatus.DETECTED, server_default="detected"
    )
    explanation: Mapped[str] = mapped_column(Text)


leakage_case_documents = Table(
    "leakage_case_documents",
    Base.metadata,
    Column("organization_id", Uuid, ForeignKey("organizations.id"), primary_key=True),
    Column("case_id", Uuid, primary_key=True),
    Column("document_id", Uuid, primary_key=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    ForeignKeyConstraint(
        ["organization_id", "case_id"], ["leakage_cases.organization_id", "leakage_cases.id"]
    ),
    ForeignKeyConstraint(
        ["organization_id", "document_id"], ["documents.organization_id", "documents.id"]
    ),
)


class LeakageEvidence(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "leakage_evidence"
    __table_args__ = (
        UniqueConstraint("organization_id", "id"),
        ForeignKeyConstraint(
            ["organization_id", "case_id", "currency"],
            ["leakage_cases.organization_id", "leakage_cases.id", "leakage_cases.currency"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "document_id"], ["documents.organization_id", "documents.id"]
        ),
        CheckConstraint("page_number IS NULL OR page_number > 0", name="positive_page"),
    )
    case_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    page_number: Mapped[int | None]
    extracted_field: Mapped[str | None] = mapped_column(String(255))
    source_text: Mapped[str | None] = mapped_column(Text)
    source_location: Mapped[str | None] = mapped_column(Text)
    calculation_reference: Mapped[str | None] = mapped_column(String(255))
    calculation_expression: Mapped[str | None] = mapped_column(Text)
    calculation_result: Mapped[Decimal | None] = mapped_column(ExactNumeric(20, 6))
    currency: Mapped[str] = mapped_column(String(3))


class ExtractionRun(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "extraction_runs"
    __table_args__ = (
        UniqueConstraint("organization_id", "document_id", "id"),
        UniqueConstraint("organization_id", "document_id", "version_number"),
        UniqueConstraint("organization_id", "document_id", "request_key"),
        ForeignKeyConstraint(
            ["organization_id", "document_id"], ["documents.organization_id", "documents.id"]
        ),
        ForeignKeyConstraint(
            ["organization_id", "document_id", "previous_run_id"],
            [
                "extraction_runs.organization_id",
                "extraction_runs.document_id",
                "extraction_runs.id",
            ],
        ),
        CheckConstraint("version_number > 0", name="positive_version"),
        CheckConstraint(
            "status IN ('queued', 'processing', 'processed', "
            "'needs_review', 'needs_ocr', 'failed')",
            name="extraction_status",
        ),
        Index(
            "ix_extraction_runs_one_active",
            "organization_id",
            "document_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'processing')"),
        ),
    )
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    initiated_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    previous_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    version_number: Mapped[int]
    request_key: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(12))
    parser_version: Mapped[str] = mapped_column(String(100))
    extractor_version: Mapped[str] = mapped_column(String(100))
    schema_version: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(128))
    document_sha256: Mapped[str] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    structured: Mapped[dict] = mapped_column(JSONB, default=dict)
    warnings: Mapped[list] = mapped_column(JSONB, default=list)
    processing_limits: Mapped[dict] = mapped_column(JSONB)


class ExtractedField(OrganizationOwned, IdentityTimestamps, Base):
    __tablename__ = "extracted_fields"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "document_id",
            "extraction_run_id",
            "id",
            name="uq_fields_review_lineage",
        ),
        ForeignKeyConstraint(
            ["organization_id", "document_id", "extraction_run_id"],
            [
                "extraction_runs.organization_id",
                "extraction_runs.document_id",
                "extraction_runs.id",
            ],
        ),
        CheckConstraint("confidence IN ('high', 'medium', 'low')", name="field_confidence"),
        CheckConstraint(
            "value_type IN ('text', 'decimal', 'date', 'currency', 'boolean')", name="field_type"
        ),
        CheckConstraint("value_type = 'decimal' OR numeric_value IS NULL", name="numeric_type"),
        CheckConstraint(
            "value_type <> 'decimal' OR (normalized_value IS NULL) = (numeric_value IS NULL)",
            name="numeric_presence",
        ),
        CheckConstraint("source ? 'format' AND source ? 'source_id'", name="field_source"),
    )
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    extraction_run_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    path: Mapped[str] = mapped_column(String(255))
    raw_value: Mapped[str] = mapped_column(Text)
    normalized_value: Mapped[str | None] = mapped_column(Text)
    numeric_value: Mapped[Decimal | None] = mapped_column(ExactNumeric(20, 6))
    value_type: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[str] = mapped_column(String(6))
    reason: Mapped[str] = mapped_column(String(100))
    source: Mapped[dict] = mapped_column(JSONB)


# Keep one metadata registry for migrations and tenant integrity checks.
from app.financial import models as financial_models  # noqa: E402, F401
from app.operations import models as operations_models  # noqa: E402, F401
from app.operations import source_models as source_models  # noqa: E402, F401
from app.proof import models as proof_models  # noqa: E402, F401
from app.recovery import models as recovery_models  # noqa: E402, F401
from app.saved_views import models as saved_view_models  # noqa: E402, F401
