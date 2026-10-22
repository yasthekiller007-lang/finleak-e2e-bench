"""OIDC identity mapping, membership roles, and authorized uploads.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    duplicate = connection.execute(
        sa.text(
            "SELECT 1 FROM documents GROUP BY organization_id, sha256 HAVING count(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate:
        raise RuntimeError("Resolve existing same-organization duplicate documents before upgrade")
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.alter_column("users", "email", existing_type=sa.String(320), nullable=True)
    op.create_table(
        "user_identities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_identities_user_id_users"),
        sa.UniqueConstraint("issuer", "subject", name="uq_user_identities_issuer_subject"),
    )
    op.create_index("ix_user_identities_user_id", "user_identities", ["user_id"])
    op.drop_constraint(
        op.f("ck_organization_memberships_membership_role"),
        "organization_memberships",
        type_="check",
    )
    connection.execute(
        sa.text("UPDATE organization_memberships SET role = 'analyst' WHERE role = 'member'")
    )
    op.alter_column(
        "organization_memberships", "role", existing_type=sa.String(20), server_default="analyst"
    )
    op.create_check_constraint(
        "membership_role",
        "organization_memberships",
        "role IN ('owner', 'admin', 'analyst', 'viewer')",
    )
    op.add_column("documents", sa.Column("uploaded_by", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_documents_uploaded_by_users", "documents", "users", ["uploaded_by"], ["id"]
    )
    op.drop_index("ix_documents_org_checksum", table_name="documents")
    op.create_unique_constraint(
        "uq_documents_organization_id_sha256", "documents", ["organization_id", "sha256"]
    )
    op.drop_constraint(op.f("ck_documents_document_type"), "documents", type_="check")
    op.alter_column("documents", "document_type", existing_type=sa.String(8), type_=sa.String(14))
    op.create_check_constraint(
        "document_type",
        "documents",
        "document_type IN ('contract', 'invoice', 'purchase_order', 'credit_note', 'other')",
    )
    op.drop_constraint(op.f("ck_documents_processing_status"), "documents", type_="check")
    op.create_check_constraint(
        "processing_status",
        "documents",
        "processing_status IN ('pending', 'queued', 'processing', 'processed', 'failed')",
    )


def downgrade() -> None:
    connection = op.get_bind()
    # Do not silently discard identities, uploader attribution, or new classification/roles.
    blocked = connection.execute(
        sa.text("""
        SELECT EXISTS(SELECT 1 FROM user_identities)
            OR EXISTS(SELECT 1 FROM documents WHERE uploaded_by IS NOT NULL
                OR document_type IN ('purchase_order', 'credit_note')
                OR processing_status = 'queued')
            OR EXISTS(SELECT 1 FROM organization_memberships WHERE role IN ('admin', 'viewer'))
            OR EXISTS(SELECT 1 FROM users WHERE email IS NULL)
            OR EXISTS(SELECT email FROM users GROUP BY email HAVING count(*) > 1)
    """)
    ).scalar()
    if blocked:
        raise RuntimeError(
            "Downgrade would lose Phase 2 data; restore/reconcile it explicitly first"
        )
    op.drop_constraint(op.f("ck_documents_processing_status"), "documents", type_="check")
    op.create_check_constraint(
        "processing_status",
        "documents",
        "processing_status IN ('pending', 'processing', 'processed', 'failed')",
    )
    op.drop_constraint(op.f("ck_documents_document_type"), "documents", type_="check")
    op.alter_column("documents", "document_type", existing_type=sa.String(14), type_=sa.String(8))
    op.create_check_constraint(
        "document_type", "documents", "document_type IN ('contract', 'invoice', 'other')"
    )
    op.drop_constraint("uq_documents_organization_id_sha256", "documents", type_="unique")
    op.create_index("ix_documents_org_checksum", "documents", ["organization_id", "sha256"])
    op.drop_constraint("fk_documents_uploaded_by_users", "documents", type_="foreignkey")
    op.drop_column("documents", "uploaded_by")
    op.drop_constraint(
        op.f("ck_organization_memberships_membership_role"),
        "organization_memberships",
        type_="check",
    )
    connection.execute(
        sa.text("UPDATE organization_memberships SET role = 'member' WHERE role = 'analyst'")
    )
    op.alter_column(
        "organization_memberships", "role", existing_type=sa.String(20), server_default="member"
    )
    op.create_check_constraint(
        "membership_role", "organization_memberships", "role IN ('owner', 'member')"
    )
    op.drop_index("ix_user_identities_user_id", table_name="user_identities")
    op.drop_table("user_identities")
    op.alter_column("users", "email", existing_type=sa.String(320), nullable=False)
    op.create_unique_constraint("uq_users_email", "users", ["email"])
