from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdentityTimestamps


class SavedExceptionView(IdentityTimestamps, Base):
    __tablename__ = "saved_exception_views"
    __table_args__ = (
        ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        ForeignKeyConstraint(["user_id"], ["users.id"]),
        UniqueConstraint("organization_id", "user_id", "view_type", "normalized_name"),
        UniqueConstraint("organization_id", "user_id", "slot"),
        CheckConstraint("slot BETWEEN 1 AND 50", name="personal_view_slot"),
        CheckConstraint("view_type IN ('anomalies','review')", name="personal_view_type"),
        CheckConstraint("format_version = 1", name="personal_view_format"),
        CheckConstraint("page_size IN (20,50,100)", name="personal_view_page_size"),
        CheckConstraint("revision BETWEEN 1 AND 9007199254740991", name="personal_view_revision"),
        CheckConstraint("length(name) BETWEEN 1 AND 80", name="personal_view_name"),
        CheckConstraint(
            "length(normalized_name) BETWEEN 1 AND 240", name="personal_view_normalized"
        ),
        CheckConstraint("jsonb_typeof(criteria) = 'object'", name="personal_view_criteria_object"),
        CheckConstraint("octet_length(criteria::text) <= 4096", name="personal_view_criteria_size"),
    )
    organization_id: Mapped[UUID]
    user_id: Mapped[UUID]
    slot: Mapped[int]
    name: Mapped[str] = mapped_column(String(80))
    normalized_name: Mapped[str] = mapped_column(String(240, collation="C"))
    view_type: Mapped[str] = mapped_column(String(9))
    format_version: Mapped[int] = mapped_column(default=1, server_default="1")
    criteria: Mapped[dict] = mapped_column(JSONB)
    page_size: Mapped[int]
    revision: Mapped[int] = mapped_column(BigInteger, default=1, server_default="1")
