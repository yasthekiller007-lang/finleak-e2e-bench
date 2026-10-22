"""Tenant-scoped extraction attempts and exact, evidence-backed candidate fields.

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def timestamps():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    ]


def upgrade():
    op.drop_constraint(op.f("ck_documents_processing_status"), "documents", type_="check")
    op.alter_column(
        "documents", "processing_status", existing_type=sa.String(10), type_=sa.String(12)
    )
    op.create_check_constraint(
        "processing_status",
        "documents",
        "processing_status IN ('pending', 'queued', 'processing', 'processed', "
        "'failed', 'needs_review', 'needs_ocr')",
    )
    op.create_table(
        "extraction_runs",
        *timestamps(),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("initiated_by", sa.Uuid(), nullable=False),
        sa.Column("previous_run_id", sa.Uuid()),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("request_key", sa.String(36), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("parser_version", sa.String(100), nullable=False),
        sa.Column("extractor_version", sa.String(100), nullable=False),
        sa.Column("schema_version", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(128), nullable=False),
        sa.Column("document_sha256", sa.String(64), nullable=False),
        sa.Column("error_code", sa.String(64)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("structured", JSONB(), nullable=False),
        sa.Column("warnings", JSONB(), nullable=False),
        sa.Column("processing_limits", JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["initiated_by"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["organization_id", "document_id"], ["documents.organization_id", "documents.id"]
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "document_id", "previous_run_id"],
            [
                "extraction_runs.organization_id",
                "extraction_runs.document_id",
                "extraction_runs.id",
            ],
        ),
        sa.UniqueConstraint("organization_id", "document_id", "id"),
        sa.UniqueConstraint("organization_id", "document_id", "version_number"),
        sa.UniqueConstraint("organization_id", "document_id", "request_key"),
        sa.CheckConstraint("version_number > 0", name="positive_version"),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'processed', "
            "'needs_review', 'needs_ocr', 'failed')",
            name="extraction_status",
        ),
    )
    op.create_index("ix_extraction_runs_organization_id", "extraction_runs", ["organization_id"])
    op.create_index(
        "ix_extraction_runs_one_active",
        "extraction_runs",
        ["organization_id", "document_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'processing')"),
    )
    op.create_table(
        "extracted_fields",
        *timestamps(),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("extraction_run_id", sa.Uuid(), nullable=False),
        sa.Column("path", sa.String(255), nullable=False),
        sa.Column("raw_value", sa.Text(), nullable=False),
        sa.Column("normalized_value", sa.Text()),
        sa.Column("numeric_value", sa.Numeric(20, 6)),
        sa.Column("value_type", sa.String(16), nullable=False),
        sa.Column("confidence", sa.String(6), nullable=False),
        sa.Column("reason", sa.String(100), nullable=False),
        sa.Column("source", JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["organization_id", "document_id", "extraction_run_id"],
            [
                "extraction_runs.organization_id",
                "extraction_runs.document_id",
                "extraction_runs.id",
            ],
        ),
        sa.CheckConstraint("confidence IN ('high', 'medium', 'low')", name="field_confidence"),
        sa.CheckConstraint(
            "value_type IN ('text', 'decimal', 'date', 'currency', 'boolean')", name="field_type"
        ),
        sa.CheckConstraint("value_type = 'decimal' OR numeric_value IS NULL", name="numeric_type"),
        sa.CheckConstraint(
            "value_type <> 'decimal' OR (normalized_value IS NULL) = (numeric_value IS NULL)",
            name="numeric_presence",
        ),
        sa.CheckConstraint("source ? 'format' AND source ? 'source_id'", name="field_source"),
    )
    op.create_index("ix_extracted_fields_organization_id", "extracted_fields", ["organization_id"])
    op.create_index(
        "ix_extracted_fields_extraction_run_id", "extracted_fields", ["extraction_run_id"]
    )


def downgrade():
    blocked = (
        op.get_bind()
        .execute(
            sa.text("""
        SELECT EXISTS(SELECT 1 FROM extraction_runs)
        OR EXISTS(SELECT 1 FROM documents WHERE processing_status IN ('needs_review', 'needs_ocr'))
    """)
        )
        .scalar()
    )
    if blocked:
        raise RuntimeError(
            "Downgrade would lose Phase 3 data; restore/reconcile it explicitly first"
        )
    op.drop_table("extracted_fields")
    op.drop_table("extraction_runs")
    op.drop_constraint(op.f("ck_documents_processing_status"), "documents", type_="check")
    op.alter_column(
        "documents", "processing_status", existing_type=sa.String(12), type_=sa.String(10)
    )
    op.create_check_constraint(
        "processing_status",
        "documents",
        "processing_status IN ('pending', 'queued', 'processing', 'processed', 'failed')",
    )
