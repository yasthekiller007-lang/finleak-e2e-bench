"""Immutable operational scan/release history. These are not reviewed financial facts."""

from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdentityTimestamps


class PilotSourceScan(IdentityTimestamps, Base):
    __tablename__ = "pilot_source_scans"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "document_id"], ["documents.organization_id", "documents.id"]
        ),
        UniqueConstraint("organization_id", "document_id", "id"),
        UniqueConstraint("organization_id", "document_id", "sequence"),
        UniqueConstraint("organization_id", "request_key"),
        CheckConstraint("sequence > 0", name="scan_sequence"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="scan_sha256"),
        CheckConstraint("file_size BETWEEN 1 AND 104857600", name="scan_size"),
        CheckConstraint(
            "verdict IN ('CLEAN','INFECTED','SUSPICIOUS','UNAVAILABLE',"
            "'TIMEOUT','MISMATCH','UNKNOWN')",
            name="scan_verdict",
        ),
        CheckConstraint("length(reason) BETWEEN 1 AND 4000", name="scan_reason"),
        CheckConstraint(
            "verdict <> 'CLEAN' OR (actual_sha256=sha256 AND actual_file_size=file_size "
            "AND actual_sha256 IS NOT NULL AND actual_file_size IS NOT NULL "
            "AND scanner_version IS NOT NULL)",
            name="scan_clean_bytes",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    document_id: Mapped[UUID] = mapped_column(Uuid)
    actor_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    request_key: Mapped[UUID] = mapped_column(Uuid)
    sequence: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    file_size: Mapped[int] = mapped_column(Integer)
    actual_sha256: Mapped[str | None] = mapped_column(String(64))
    actual_file_size: Mapped[int | None] = mapped_column(Integer)
    verdict: Mapped[str] = mapped_column(String(16))
    scanner_profile: Mapped[str] = mapped_column(String(32))
    scanner_version: Mapped[str | None] = mapped_column(String(100))
    reason: Mapped[str] = mapped_column(String(4000))
    db_principal: Mapped[str] = mapped_column(String(63), server_default=text("session_user"))
    effective_role: Mapped[str] = mapped_column(String(63), server_default=text("current_user"))


class PilotSourceRelease(IdentityTimestamps, Base):
    __tablename__ = "pilot_source_releases"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "document_id", "scan_id"],
            [
                "pilot_source_scans.organization_id",
                "pilot_source_scans.document_id",
                "pilot_source_scans.id",
            ],
        ),
        UniqueConstraint("organization_id", "request_key"),
        UniqueConstraint("organization_id", "document_id", "scan_id"),
        CheckConstraint("length(reason) BETWEEN 1 AND 4000", name="release_reason"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    document_id: Mapped[UUID] = mapped_column(Uuid)
    scan_id: Mapped[UUID] = mapped_column(Uuid)
    actor_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    request_key: Mapped[UUID] = mapped_column(Uuid)
    verified_sha256: Mapped[str] = mapped_column(String(64))
    verified_file_size: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(4000))
    db_principal: Mapped[str] = mapped_column(String(63), server_default=text("session_user"))
    effective_role: Mapped[str] = mapped_column(String(63), server_default=text("current_user"))


class PilotSourceRequest(IdentityTimestamps, Base):
    __tablename__ = "pilot_source_requests"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "document_id"], ["documents.organization_id", "documents.id"]
        ),
        UniqueConstraint("organization_id", "request_key"),
        CheckConstraint("operation IN ('SCAN','RELEASE')", name="source_request_operation"),
        CheckConstraint("fingerprint ~ '^[0-9a-f]{64}$'", name="source_request_fingerprint"),
        CheckConstraint("length(reason) BETWEEN 1 AND 4000", name="source_request_reason"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    document_id: Mapped[UUID] = mapped_column(Uuid)
    actor_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    request_key: Mapped[UUID] = mapped_column(Uuid)
    operation: Mapped[str] = mapped_column(String(7))
    fingerprint: Mapped[str] = mapped_column(String(64))
    result_id: Mapped[UUID] = mapped_column(Uuid)
    reason: Mapped[str] = mapped_column(String(4000))
    db_principal: Mapped[str] = mapped_column(String(63), server_default=text("session_user"))
    effective_role: Mapped[str] = mapped_column(String(63), server_default=text("current_user"))
