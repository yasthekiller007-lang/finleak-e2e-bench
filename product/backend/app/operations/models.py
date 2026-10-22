"""Access availability and attributed operator history; no monetary authority."""

from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Uuid, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdentityTimestamps


class PilotUserAccess(IdentityTimestamps, Base):
    __tablename__ = "pilot_user_access"
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, server_default=true())


class PilotTenantAccess(IdentityTimestamps, Base):
    __tablename__ = "pilot_tenant_access"
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, server_default=true())


class PilotAccessJournal(IdentityTimestamps, Base):
    __tablename__ = "pilot_access_journal"
    __table_args__ = (
        CheckConstraint("length(reason) BETWEEN 1 AND 4000", name="access_reason"),
        CheckConstraint("jsonb_typeof(detail) = 'object'", name="access_detail"),
    )
    actor_id: Mapped[UUID | None] = mapped_column(Uuid)
    organization_id: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    user_id: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    target_id: Mapped[UUID] = mapped_column(Uuid)
    request_id: Mapped[UUID | None] = mapped_column(Uuid)
    db_principal: Mapped[str] = mapped_column(String(63))
    effective_role: Mapped[str] = mapped_column(String(63))
    action: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(String(4000))
    detail: Mapped[dict] = mapped_column(JSONB)


class PilotIntakeProfile(IdentityTimestamps, Base):
    __tablename__ = "pilot_intake_profiles"
    __table_args__ = (
        CheckConstraint("jsonb_typeof(configuration)='object'", name="intake_configuration"),
    )
    name: Mapped[str] = mapped_column(String(32), unique=True)
    actor_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    configuration: Mapped[dict] = mapped_column(JSONB)


class PilotIntakeAttempt(IdentityTimestamps, Base):
    __tablename__ = "pilot_intake_attempts"
    __table_args__ = (
        CheckConstraint("operation IN ('upload','process')", name="intake_operation"),
        CheckConstraint("slot BETWEEN 0 AND 3", name="intake_slot"),
        Index("ix_pilot_intake_attempts_actor_created", "actor_id", "created_at"),
    )
    organization_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), index=True)
    actor_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    profile: Mapped[str] = mapped_column(String(32), ForeignKey("pilot_intake_profiles.name"))
    operation: Mapped[str] = mapped_column(String(7))
    slot: Mapped[int] = mapped_column(Integer)
