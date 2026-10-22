"""Reviewed sources, immutable financial authority, evaluations and transactional audit.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


TABLES = [
    "reviewed_financial_sources",
    "financial_revisions",
    "financial_evaluations",
    "financial_audit",
    "financial_finding_decisions",
    "financial_revision_evidence",
]


def upgrade():
    op.create_unique_constraint(
        "uq_fields_review_lineage",
        "extracted_fields",
        ["organization_id", "document_id", "extraction_run_id", "id"],
    )
    op.execute("""

CREATE TABLE reviewed_financial_sources (
        document_id UUID NOT NULL,
        kind VARCHAR(12) NOT NULL,
        created_by UUID NOT NULL,
        organization_id UUID NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        CONSTRAINT pk_reviewed_financial_sources PRIMARY KEY (id),
        CONSTRAINT uq_reviewed_financial_sources_organization_id_id UNIQUE (organization_id,
id),
        CONSTRAINT uq_reviewed_financial_sources_organization_id_document_id_kind UNIQUE
(organization_id, document_id, kind),
        CONSTRAINT fk_reviewed_financial_sources_organization_id_documents FOREIGN
KEY(organization_id, document_id) REFERENCES documents (organization_id, id),
        CONSTRAINT ck_reviewed_financial_sources_source_kind CHECK (kind IN ('contract',
'invoice')),
        CONSTRAINT fk_reviewed_financial_sources_created_by_users FOREIGN KEY(created_by)
REFERENCES users (id),
        CONSTRAINT fk_reviewed_financial_sources_organization_id_organizations FOREIGN
KEY(organization_id) REFERENCES organizations (id)
)

""")
    op.execute(
        "CREATE INDEX ix_reviewed_financial_sources_organization_id "
        "ON reviewed_financial_sources (organization_id)"
    )
    op.execute("""

CREATE TABLE financial_revisions (
        source_id UUID NOT NULL,
        contract_source_id UUID,
        kind VARCHAR(20) NOT NULL,
        key VARCHAR(120) NOT NULL,
        number INTEGER NOT NULL,
        previous_id UUID,
        state VARCHAR(12) NOT NULL,
        actor_id UUID NOT NULL,
        request_key VARCHAR(36) NOT NULL,
        request_hash VARCHAR(64) NOT NULL,
        knowledge_cutoff TIMESTAMP WITH TIME ZONE NOT NULL,
        payload JSONB NOT NULL,
        provenance JSONB NOT NULL,
        organization_id UUID NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        CONSTRAINT pk_financial_revisions PRIMARY KEY (id),
        CONSTRAINT uq_financial_revisions_organization_id_id UNIQUE (organization_id, id),
        CONSTRAINT uq_financial_revisions_organization_id_source_id_id UNIQUE (organization_id,
source_id, id),
        CONSTRAINT uq_financial_revisions_organization_id_source_id_kind_k_0bdf UNIQUE
(organization_id, source_id, kind, key, number),
        CONSTRAINT uq_financial_revisions_organization_id_request_key UNIQUE (organization_id,
request_key),
        CONSTRAINT fk_financial_revisions_organization_id_reviewed_financi_417e FOREIGN
KEY(organization_id, source_id) REFERENCES reviewed_financial_sources (organization_id, id),
        CONSTRAINT fk_financial_revisions_organization_id_financial_revisions FOREIGN
KEY(organization_id, source_id, previous_id) REFERENCES financial_revisions (organization_id,
source_id, id),
        CONSTRAINT fk_financial_revision_contract_source FOREIGN KEY(organization_id,
contract_source_id) REFERENCES reviewed_financial_sources (organization_id, id),
        CONSTRAINT ck_financial_revisions_revision_positive CHECK (number > 0),
        CONSTRAINT ck_financial_revisions_revision_kind CHECK (kind IN ('term', 'billing_scope',
'reference', 'packet', 'association')),
        CONSTRAINT ck_financial_revisions_revision_state CHECK (state IN ('prepared',
'approved', 'revoked')),
        CONSTRAINT fk_financial_revisions_actor_id_users FOREIGN KEY(actor_id) REFERENCES users
(id),
        CONSTRAINT fk_financial_revisions_organization_id_organizations FOREIGN
KEY(organization_id) REFERENCES organizations (id)
)

""")
    op.execute(
        "CREATE INDEX ix_financial_revisions_organization_id "
        "ON financial_revisions (organization_id)"
    )
    op.execute("""

CREATE TABLE financial_evaluations (
        invoice_source_id UUID NOT NULL,
        scope_key VARCHAR(120) NOT NULL,
        actor_id UUID NOT NULL,
        fingerprint VARCHAR(64) NOT NULL,
        outcome VARCHAR(32) NOT NULL,
        reason_code VARCHAR(64) NOT NULL,
        explanation VARCHAR(2000) NOT NULL,
        currency VARCHAR(3),
        expected NUMERIC(20, 6),
        actual NUMERIC(20, 6),
        discrepancy NUMERIC(20, 6),
        potential NUMERIC(20, 6),
        snapshot JSONB NOT NULL,
        organization_id UUID NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        CONSTRAINT pk_financial_evaluations PRIMARY KEY (id),
        CONSTRAINT uq_financial_evaluations_organization_id_id UNIQUE (organization_id, id),
        CONSTRAINT uq_financial_evaluations_organization_id_fingerprint UNIQUE (organization_id,
fingerprint),
        CONSTRAINT fk_financial_evaluations_organization_id_reviewed_finan_ef8e FOREIGN
KEY(organization_id, invoice_source_id) REFERENCES reviewed_financial_sources (organization_id,
id),
        CONSTRAINT ck_financial_evaluations_currency_format CHECK (currency IS NULL OR currency
~ '^[A-Z]{3}$'),
        CONSTRAINT ck_financial_evaluations_potential_positive CHECK (potential IS NULL OR
potential > 0),
        CONSTRAINT ck_financial_evaluations_finding_presence CHECK ((outcome =
'POTENTIAL_LEAKAGE') = (potential IS NOT NULL)),
        CONSTRAINT fk_financial_evaluations_actor_id_users FOREIGN KEY(actor_id) REFERENCES
users (id),
        CONSTRAINT fk_financial_evaluations_organization_id_organizations FOREIGN
KEY(organization_id) REFERENCES organizations (id)
)

""")
    op.execute(
        "CREATE INDEX ix_financial_evaluations_organization_id "
        "ON financial_evaluations (organization_id)"
    )
    op.execute("""

CREATE TABLE financial_audit (
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        actor_id UUID NOT NULL,
        action VARCHAR(60) NOT NULL,
        target_id UUID NOT NULL,
        detail JSONB NOT NULL,
        organization_id UUID NOT NULL,
        CONSTRAINT pk_financial_audit PRIMARY KEY (id),
        CONSTRAINT uq_financial_audit_organization_id_id UNIQUE (organization_id, id),
        CONSTRAINT fk_financial_audit_actor_id_users FOREIGN KEY(actor_id) REFERENCES users
(id),
        CONSTRAINT fk_financial_audit_organization_id_organizations FOREIGN KEY(organization_id)
REFERENCES organizations (id)
)

""")
    op.execute(
        "CREATE INDEX ix_financial_audit_organization_id ON financial_audit (organization_id)"
    )
    op.execute("""

CREATE TABLE financial_finding_decisions (
        evaluation_id UUID NOT NULL,
        actor_id UUID NOT NULL,
        number INTEGER NOT NULL,
        status VARCHAR(20) NOT NULL,
        reason VARCHAR(2000) NOT NULL,
        organization_id UUID NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        CONSTRAINT pk_financial_finding_decisions PRIMARY KEY (id),
        CONSTRAINT fk_financial_finding_decisions_organization_id_financia_89cb FOREIGN
KEY(organization_id, evaluation_id) REFERENCES financial_evaluations (organization_id, id),
        CONSTRAINT uq_financial_finding_decisions_organization_id_evaluati_97ff UNIQUE
(organization_id, evaluation_id, number),
        CONSTRAINT ck_financial_finding_decisions_finding_status CHECK (status IN ('confirmed',
'false_positive', 'needs_review')),
        CONSTRAINT fk_financial_finding_decisions_actor_id_users FOREIGN KEY(actor_id)
REFERENCES users (id),
        CONSTRAINT fk_financial_finding_decisions_organization_id_organizations FOREIGN
KEY(organization_id) REFERENCES organizations (id)
)

""")
    op.execute(
        "CREATE INDEX ix_financial_finding_decisions_organization_id "
        "ON financial_finding_decisions (organization_id)"
    )
    op.execute("""

CREATE TABLE financial_revision_evidence (
        revision_id UUID NOT NULL,
        document_id UUID NOT NULL,
        run_id UUID,
        field_id UUID,
        detail JSONB NOT NULL,
        organization_id UUID NOT NULL,
        id UUID NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
        CONSTRAINT pk_financial_revision_evidence PRIMARY KEY (id),
        CONSTRAINT fk_financial_revision_evidence_organization_id_financia_5482 FOREIGN
KEY(organization_id, revision_id) REFERENCES financial_revisions (organization_id, id),
        CONSTRAINT fk_financial_revision_evidence_organization_id_documents FOREIGN
KEY(organization_id, document_id) REFERENCES documents (organization_id, id),
        CONSTRAINT fk_financial_revision_evidence_organization_id_extraction_runs FOREIGN
KEY(organization_id, document_id, run_id) REFERENCES extraction_runs (organization_id,
document_id, id),
        CONSTRAINT fk_financial_revision_evidence_organization_id_extracted_fields FOREIGN
KEY(organization_id, document_id, run_id, field_id) REFERENCES extracted_fields
(organization_id, document_id, extraction_run_id, id),
        CONSTRAINT ck_financial_revision_evidence_evidence_lineage CHECK ((field_id IS NULL) =
(run_id IS NULL)),
        CONSTRAINT fk_financial_revision_evidence_organization_id_organizations FOREIGN
KEY(organization_id) REFERENCES organizations (id)
)

""")
    op.execute(
        "CREATE INDEX ix_financial_revision_evidence_organization_id "
        "ON financial_revision_evidence (organization_id)"
    )
    op.execute("""
        CREATE FUNCTION financial_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Financial history is immutable; create a new revision';
        END $$
    """)
    op.execute("""
        CREATE FUNCTION financial_authority_lock() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE membership_role text; actor uuid;
        BEGIN
            PERFORM id FROM organizations WHERE id = NEW.organization_id FOR UPDATE;
            actor := COALESCE(to_jsonb(NEW)->>'actor_id', to_jsonb(NEW)->>'created_by')::uuid;
            IF actor IS NOT NULL THEN
                SELECT role INTO membership_role FROM organization_memberships
                    WHERE organization_id = NEW.organization_id AND user_id = actor FOR SHARE;
                IF membership_role IS NULL OR membership_role = 'viewer' OR
                    (TG_TABLE_NAME IN ('financial_evaluations', 'financial_finding_decisions')
                     OR (TG_TABLE_NAME = 'financial_revisions' AND
                         (to_jsonb(NEW)->>'state') <> 'prepared'))
                    AND membership_role NOT IN ('owner', 'admin') THEN
                    RAISE EXCEPTION 'Financial authority requires a current authorized membership';
                END IF;
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute("""
        CREATE FUNCTION financial_record_audit() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            INSERT INTO financial_audit (id, organization_id, actor_id, action, target_id, detail)
            VALUES (gen_random_uuid(), NEW.organization_id, NEW.actor_id,
                CASE WHEN TG_TABLE_NAME = 'financial_revisions' THEN
                    'review.' || (to_jsonb(NEW)->>'kind') || '.' || (to_jsonb(NEW)->>'state')
                WHEN TG_TABLE_NAME = 'financial_evaluations' THEN 'evaluation.created'
                ELSE 'finding.' || (to_jsonb(NEW)->>'status') END,
                NEW.id, jsonb_build_object('table', TG_TABLE_NAME,
                    'number', to_jsonb(NEW)->'number',
                    'previous_id', to_jsonb(NEW)->'previous_id',
                    'request_key', to_jsonb(NEW)->'request_key',
                    'reason', COALESCE(to_jsonb(NEW)->'reason', to_jsonb(NEW)->'payload'->'reason'),
                    'fingerprint', to_jsonb(NEW)->'fingerprint',
                    'role_at_action', (SELECT role FROM organization_memberships
                         WHERE organization_id = NEW.organization_id AND user_id = NEW.actor_id)));
            RETURN NEW;
        END $$
    """)
    op.execute("""
        CREATE FUNCTION financial_audit_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF pg_trigger_depth() < 2 THEN
                RAISE EXCEPTION 'Financial audit must originate from an authoritative record';
            END IF;
            RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER audit_origin BEFORE INSERT ON financial_audit "
        "FOR EACH ROW EXECUTE FUNCTION financial_audit_guard()"
    )
    op.execute("""
        CREATE FUNCTION financial_document_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF (TG_OP = 'DELETE' OR NEW.sha256 <> OLD.sha256 OR
                NEW.storage_key <> OLD.storage_key OR NEW.file_size <> OLD.file_size OR
                NEW.document_type <> OLD.document_type) AND (
                EXISTS (SELECT 1 FROM reviewed_financial_sources WHERE document_id = OLD.id) OR
                EXISTS (SELECT 1 FROM financial_revision_evidence WHERE document_id = OLD.id) OR
                EXISTS (SELECT 1 FROM financial_revisions WHERE payload->'document_hashes'
                        @> jsonb_build_array(jsonb_build_object('document_id', OLD.id::text)))) THEN
                RAISE EXCEPTION 'Financial source evidence is immutable';
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER financial_source_guard BEFORE UPDATE OR DELETE ON documents "
        "FOR EACH ROW EXECUTE FUNCTION financial_document_guard()"
    )
    for table in TABLES:
        op.execute(
            f"CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION financial_immutable()"
        )
        if table != "financial_audit":
            op.execute(
                f"CREATE TRIGGER serialize_authority BEFORE INSERT ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION financial_authority_lock()"
            )
        if table in {"financial_revisions", "financial_evaluations", "financial_finding_decisions"}:
            op.execute(
                f"CREATE TRIGGER audit_authority AFTER INSERT ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION financial_record_audit()"
            )


def downgrade():
    connection = op.get_bind()
    # No silent deletion of reviewed evidence, financial results or audit history.
    if any(connection.scalar(sa.text(f"SELECT EXISTS(SELECT 1 FROM {table})")) for table in TABLES):
        raise RuntimeError("Downgrade would lose Phase 4 financial data; refusing data loss")
    op.execute("DROP TRIGGER financial_source_guard ON documents")
    op.execute("DROP FUNCTION financial_document_guard()")
    for table in reversed(TABLES):
        op.drop_table(table)
    op.drop_constraint(
        "uq_fields_review_lineage",
        "extracted_fields",
        type_="unique",
    )
    op.execute("DROP FUNCTION financial_audit_guard()")
    op.execute("DROP FUNCTION financial_record_audit()")
    op.execute("DROP FUNCTION financial_authority_lock()")
    op.execute("DROP FUNCTION financial_immutable()")
