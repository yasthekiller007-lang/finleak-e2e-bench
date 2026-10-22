"""initial tenant-scoped financial schema

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
    )
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "contracts",
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("counterparty_name", sa.String(length=255), nullable=False),
        sa.Column("external_reference", sa.String(length=255), nullable=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_contracts_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contracts")),
        sa.UniqueConstraint("organization_id", "id", name=op.f("uq_contracts_organization_id_id")),
    )
    op.create_index(
        op.f("ix_contracts_organization_id"), "contracts", ["organization_id"], unique=False
    )
    op.create_table(
        "documents",
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=127), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "document_type",
            sa.Enum(
                "contract",
                "invoice",
                "other",
                name="document_type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "processing_status",
            sa.Enum(
                "pending",
                "processing",
                "processed",
                "failed",
                name="processing_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("sha256 ~ '^[a-f0-9]{64}$'", name=op.f("ck_documents_sha256_format")),
        sa.CheckConstraint("file_size >= 0", name=op.f("ck_documents_file_size_nonnegative")),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_documents_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
        sa.UniqueConstraint("organization_id", "id", name=op.f("uq_documents_organization_id_id")),
        sa.UniqueConstraint(
            "organization_id", "storage_key", name=op.f("uq_documents_organization_id_storage_key")
        ),
    )
    op.create_index(
        "ix_documents_org_checksum", "documents", ["organization_id", "sha256"], unique=False
    )
    op.create_index(
        op.f("ix_documents_organization_id"), "documents", ["organization_id"], unique=False
    )
    op.create_table(
        "organization_memberships",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=20), server_default="member", nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('owner', 'member')", name=op.f("ck_organization_memberships_membership_role")
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_organization_memberships_organization_id_organizations"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_organization_memberships_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organization_memberships")),
        sa.UniqueConstraint(
            "organization_id",
            "user_id",
            name=op.f("uq_organization_memberships_organization_id_user_id"),
        ),
    )
    op.create_index(
        op.f("ix_organization_memberships_organization_id"),
        "organization_memberships",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_organization_memberships_user_id"),
        "organization_memberships",
        ["user_id"],
        unique=False,
    )
    op.create_table(
        "contract_versions",
        sa.Column("contract_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "original",
                "amendment",
                name="version_kind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("terms_text", sa.Text(), nullable=True),
        sa.Column("agreed_amount", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "currency IS NULL OR currency ~ '^[A-Z]{3}$'",
            name=op.f("ck_contract_versions_currency_format"),
        ),
        sa.CheckConstraint(
            "(agreed_amount IS NULL) = (currency IS NULL)",
            name=op.f("ck_contract_versions_amount_currency_pair"),
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name=op.f("ck_contract_versions_effective_interval"),
        ),
        sa.CheckConstraint(
            "version_number > 0", name=op.f("ck_contract_versions_positive_version")
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "contract_id"],
            ["contracts.organization_id", "contracts.id"],
            name=op.f("fk_contract_versions_organization_id_contracts"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "document_id"],
            ["documents.organization_id", "documents.id"],
            name=op.f("fk_contract_versions_organization_id_documents"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_contract_versions_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contract_versions")),
        sa.UniqueConstraint(
            "organization_id",
            "contract_id",
            "version_number",
            name=op.f("uq_contract_versions_organization_id_contract_id_version_number"),
        ),
        sa.UniqueConstraint(
            "organization_id", "id", name=op.f("uq_contract_versions_organization_id_id")
        ),
    )
    op.create_index(
        op.f("ix_contract_versions_organization_id"),
        "contract_versions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_versions_org_contract_effective",
        "contract_versions",
        ["organization_id", "contract_id", "effective_from"],
        unique=False,
    )
    op.create_table(
        "invoices",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("contract_id", sa.Uuid(), nullable=True),
        sa.Column("invoice_number", sa.String(length=255), nullable=False),
        sa.Column("supplier_name", sa.String(length=255), nullable=False),
        sa.Column("issued_on", sa.Date(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("total_amount", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name=op.f("ck_invoices_currency_format")),
        sa.ForeignKeyConstraint(
            ["organization_id", "contract_id"],
            ["contracts.organization_id", "contracts.id"],
            name=op.f("fk_invoices_organization_id_contracts"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "document_id"],
            ["documents.organization_id", "documents.id"],
            name=op.f("fk_invoices_organization_id_documents"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_invoices_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invoices")),
        sa.UniqueConstraint(
            "organization_id",
            "id",
            "currency",
            name=op.f("uq_invoices_organization_id_id_currency"),
        ),
        sa.UniqueConstraint("organization_id", "id", name=op.f("uq_invoices_organization_id_id")),
    )
    op.create_index(
        op.f("ix_invoices_organization_id"), "invoices", ["organization_id"], unique=False
    )
    op.create_table(
        "invoice_line_items",
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column("unit_amount", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column("line_amount", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "line_number > 0", name=op.f("ck_invoice_line_items_positive_line_number")
        ),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_invoice_line_items_positive_quantity")),
        sa.ForeignKeyConstraint(
            ["organization_id", "invoice_id", "currency"],
            ["invoices.organization_id", "invoices.id", "invoices.currency"],
            name=op.f("fk_invoice_line_items_organization_id_invoices"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_invoice_line_items_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invoice_line_items")),
        sa.UniqueConstraint(
            "organization_id", "id", name=op.f("uq_invoice_line_items_organization_id_id")
        ),
        sa.UniqueConstraint(
            "organization_id",
            "invoice_id",
            "line_number",
            name=op.f("uq_invoice_line_items_organization_id_invoice_id_line_number"),
        ),
    )
    op.create_index(
        op.f("ix_invoice_line_items_organization_id"),
        "invoice_line_items",
        ["organization_id"],
        unique=False,
    )
    op.create_table(
        "leakage_cases",
        sa.Column("contract_id", sa.Uuid(), nullable=True),
        sa.Column("invoice_id", sa.Uuid(), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("potential_exposure", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column("validated_exposure", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("recovered_amount", sa.Numeric(precision=20, scale=6), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column(
            "priority",
            sa.Enum(
                "low",
                "normal",
                "high",
                "critical",
                name="case_priority",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="normal",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "detected",
                "needs_review",
                "confirmed",
                "false_positive",
                "investigating",
                "resolved",
                name="case_status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="detected",
            nullable=False,
        ),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "currency ~ '^[A-Z]{3}$'", name=op.f("ck_leakage_cases_currency_format")
        ),
        sa.CheckConstraint(
            "confidence_score BETWEEN 0 AND 1", name=op.f("ck_leakage_cases_confidence_range")
        ),
        sa.CheckConstraint(
            "potential_exposure >= 0", name=op.f("ck_leakage_cases_potential_nonnegative")
        ),
        sa.CheckConstraint(
            "recovered_amount >= 0", name=op.f("ck_leakage_cases_recovered_nonnegative")
        ),
        sa.CheckConstraint(
            "validated_exposure >= 0", name=op.f("ck_leakage_cases_validated_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "contract_id"],
            ["contracts.organization_id", "contracts.id"],
            name=op.f("fk_leakage_cases_organization_id_contracts"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "invoice_id", "currency"],
            ["invoices.organization_id", "invoices.id", "invoices.currency"],
            name=op.f("fk_leakage_cases_organization_id_invoices"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_leakage_cases_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_leakage_cases")),
        sa.UniqueConstraint(
            "organization_id",
            "id",
            "currency",
            name=op.f("uq_leakage_cases_organization_id_id_currency"),
        ),
        sa.UniqueConstraint(
            "organization_id", "id", name=op.f("uq_leakage_cases_organization_id_id")
        ),
    )
    op.create_index(
        "ix_cases_org_status", "leakage_cases", ["organization_id", "status"], unique=False
    )
    op.create_index(
        op.f("ix_leakage_cases_organization_id"), "leakage_cases", ["organization_id"], unique=False
    )
    op.create_table(
        "leakage_case_documents",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id"],
            ["leakage_cases.organization_id", "leakage_cases.id"],
            name=op.f("fk_leakage_case_documents_organization_id_leakage_cases"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "document_id"],
            ["documents.organization_id", "documents.id"],
            name=op.f("fk_leakage_case_documents_organization_id_documents"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_leakage_case_documents_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint(
            "organization_id", "case_id", "document_id", name=op.f("pk_leakage_case_documents")
        ),
    )
    op.create_table(
        "leakage_evidence",
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("extracted_field", sa.String(length=255), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("source_location", sa.Text(), nullable=True),
        sa.Column("calculation_reference", sa.String(length=255), nullable=True),
        sa.Column("calculation_expression", sa.Text(), nullable=True),
        sa.Column("calculation_result", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "page_number IS NULL OR page_number > 0", name=op.f("ck_leakage_evidence_positive_page")
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "case_id", "currency"],
            ["leakage_cases.organization_id", "leakage_cases.id", "leakage_cases.currency"],
            name=op.f("fk_leakage_evidence_organization_id_leakage_cases"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "document_id"],
            ["documents.organization_id", "documents.id"],
            name=op.f("fk_leakage_evidence_organization_id_documents"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_leakage_evidence_organization_id_organizations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_leakage_evidence")),
        sa.UniqueConstraint(
            "organization_id", "id", name=op.f("uq_leakage_evidence_organization_id_id")
        ),
    )
    op.create_index(
        op.f("ix_leakage_evidence_organization_id"),
        "leakage_evidence",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_leakage_evidence_organization_id"), table_name="leakage_evidence")
    op.drop_table("leakage_evidence")
    op.drop_table("leakage_case_documents")
    op.drop_index(op.f("ix_leakage_cases_organization_id"), table_name="leakage_cases")
    op.drop_index("ix_cases_org_status", table_name="leakage_cases")
    op.drop_table("leakage_cases")
    op.drop_index(op.f("ix_invoice_line_items_organization_id"), table_name="invoice_line_items")
    op.drop_table("invoice_line_items")
    op.drop_index(op.f("ix_invoices_organization_id"), table_name="invoices")
    op.drop_table("invoices")
    op.drop_index("ix_versions_org_contract_effective", table_name="contract_versions")
    op.drop_index(op.f("ix_contract_versions_organization_id"), table_name="contract_versions")
    op.drop_table("contract_versions")
    op.drop_index(
        op.f("ix_organization_memberships_user_id"), table_name="organization_memberships"
    )
    op.drop_index(
        op.f("ix_organization_memberships_organization_id"), table_name="organization_memberships"
    )
    op.drop_table("organization_memberships")
    op.drop_index(op.f("ix_documents_organization_id"), table_name="documents")
    op.drop_index("ix_documents_org_checksum", table_name="documents")
    op.drop_table("documents")
    op.drop_index(op.f("ix_contracts_organization_id"), table_name="contracts")
    op.drop_table("contracts")
    op.drop_table("users")
    op.drop_table("organizations")
