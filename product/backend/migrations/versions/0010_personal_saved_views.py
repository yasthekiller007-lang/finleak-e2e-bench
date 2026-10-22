"""Candidate personal criteria storage; never changes financial tables.

Revision ID: 0010
Revises: 0009
Not applied to a native database in Product V2.0.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "saved_exception_views",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("normalized_name", sa.String(240, collation="C"), nullable=False),
        sa.Column("view_type", sa.String(9), nullable=False),
        sa.Column("format_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("criteria", postgresql.JSONB(), nullable=False),
        sa.Column("page_size", sa.Integer(), nullable=False),
        sa.Column("revision", sa.BigInteger(), server_default="1", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("organization_id", "user_id", "view_type", "normalized_name"),
        sa.UniqueConstraint("organization_id", "user_id", "slot"),
        sa.CheckConstraint("slot BETWEEN 1 AND 50", name="personal_view_slot"),
        sa.CheckConstraint("view_type IN ('anomalies','review')", name="personal_view_type"),
        sa.CheckConstraint("format_version = 1", name="personal_view_format"),
        sa.CheckConstraint("page_size IN (20,50,100)", name="personal_view_page_size"),
        sa.CheckConstraint(
            "revision BETWEEN 1 AND 9007199254740991", name="personal_view_revision"
        ),
        sa.CheckConstraint("length(name) BETWEEN 1 AND 80", name="personal_view_name"),
        sa.CheckConstraint(
            "length(normalized_name) BETWEEN 1 AND 240", name="personal_view_normalized"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(criteria) = 'object'", name="personal_view_criteria_object"
        ),
        sa.CheckConstraint(
            "octet_length(criteria::text) <= 4096", name="personal_view_criteria_size"
        ),
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT EXISTS(SELECT 1 FROM saved_exception_views)")):
        raise RuntimeError("Export personal views before explicitly authorizing their removal")
    op.drop_table("saved_exception_views")
