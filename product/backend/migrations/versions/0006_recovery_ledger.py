"""Immutable Recovery Ledger identity, evidence, authority and audit guards.

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

TABLES = [
    "recovery_cases",
    "recovery_instruments",
    "recovery_proposals",
    "recovery_evidence",
    "recovery_records",
    "recovery_aliases",
    "recovery_requests",
    "recovery_publications",
]

# Frozen schema snapshot: this migration never imports application model definitions.
SCHEMA = """
CREATE TABLE recovery_cases (
	evaluation_id UUID NOT NULL,
	actor_id UUID NOT NULL,
	audit_id UUID NOT NULL,
	organization_id UUID NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_recovery_cases PRIMARY KEY (id),
	CONSTRAINT uq_recovery_cases_organization_id_id UNIQUE (organization_id, id),
        CONSTRAINT uq_recovery_cases_organization_id_evaluation_id UNIQUE (organization_id,
evaluation_id),
        CONSTRAINT fk_recovery_cases_organization_id_financial_evaluations FOREIGN
KEY(organization_id, evaluation_id) REFERENCES financial_evaluations (organization_id, id),
        CONSTRAINT fk_recovery_cases_organization_id_financial_audit FOREIGN
KEY(organization_id, audit_id) REFERENCES financial_audit (organization_id, id) DEFERRABLE
INITIALLY DEFERRED,
	CONSTRAINT fk_recovery_cases_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id),
        CONSTRAINT fk_recovery_cases_organization_id_organizations FOREIGN KEY(organization_id)
REFERENCES organizations (id)
);
CREATE INDEX ix_recovery_cases_organization_id ON recovery_cases (organization_id);
CREATE TABLE recovery_instruments (
	kind VARCHAR(16) NOT NULL,
	namespace VARCHAR(120) NOT NULL,
	issuer VARCHAR(120) NOT NULL,
	reference VARCHAR(120) NOT NULL,
	currency VARCHAR(3) NOT NULL,
	identity_hash VARCHAR(64) NOT NULL,
	actor_id UUID NOT NULL,
	audit_id UUID NOT NULL,
	organization_id UUID NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_recovery_instruments PRIMARY KEY (id),
	CONSTRAINT uq_recovery_instruments_organization_id_id UNIQUE (organization_id, id),
        CONSTRAINT uq_recovery_instruments_organization_id_identity_hash UNIQUE
(organization_id, identity_hash),
        CONSTRAINT fk_recovery_instruments_organization_id_financial_audit FOREIGN
KEY(organization_id, audit_id) REFERENCES financial_audit (organization_id, id) DEFERRABLE
INITIALLY DEFERRED,
	CONSTRAINT ck_recovery_instruments_instrument_currency CHECK (currency ~ '^[A-Z]{3}$'),
        CONSTRAINT ck_recovery_instruments_instrument_kind CHECK (kind IN
('CASH','CREDIT','LIABILITY','COST','SETTLEMENT')),
	CONSTRAINT ck_recovery_instruments_instrument_identity CHECK (identity_hash ~ '^[a-f0-9]{64}$'),
	CONSTRAINT fk_recovery_instruments_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id),
        CONSTRAINT fk_recovery_instruments_organization_id_organizations FOREIGN
KEY(organization_id) REFERENCES organizations (id)
);
CREATE INDEX ix_recovery_instruments_organization_id ON recovery_instruments (organization_id);
CREATE TABLE recovery_proposals (
	case_id UUID NOT NULL,
	actor_id UUID NOT NULL,
	audit_id UUID NOT NULL,
	kind VARCHAR(24) NOT NULL,
	semantic_hash VARCHAR(64) NOT NULL,
	value JSONB NOT NULL,
	authority JSONB NOT NULL,
	reason VARCHAR(4000) NOT NULL,
	organization_id UUID NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_recovery_proposals PRIMARY KEY (id),
	CONSTRAINT uq_recovery_proposals_organization_id_id UNIQUE (organization_id, id),
        CONSTRAINT uq_recovery_proposals_organization_id_case_id_semantic_hash UNIQUE
(organization_id, case_id, semantic_hash),
        CONSTRAINT fk_recovery_proposals_organization_id_recovery_cases FOREIGN
KEY(organization_id, case_id) REFERENCES recovery_cases (organization_id, id),
        CONSTRAINT fk_recovery_proposals_organization_id_financial_audit FOREIGN
KEY(organization_id, audit_id) REFERENCES financial_audit (organization_id, id) DEFERRABLE
INITIALLY DEFERRED,
	CONSTRAINT ck_recovery_proposals_proposal_hash CHECK (semantic_hash ~ '^[a-f0-9]{64}$'),
	CONSTRAINT fk_recovery_proposals_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id),
        CONSTRAINT fk_recovery_proposals_organization_id_organizations FOREIGN
KEY(organization_id) REFERENCES organizations (id)
);
CREATE INDEX ix_recovery_proposals_organization_id ON recovery_proposals (organization_id);
CREATE TABLE recovery_evidence (
	proposal_id UUID NOT NULL,
	document_id UUID NOT NULL,
	sha256 VARCHAR(64) NOT NULL,
	file_size INTEGER NOT NULL,
	media_type VARCHAR(120) NOT NULL,
	binding_hash VARCHAR(64) NOT NULL,
	detail JSONB NOT NULL,
	organization_id UUID NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_recovery_evidence PRIMARY KEY (id),
	CONSTRAINT uq_recovery_evidence_organization_id_id UNIQUE (organization_id, id),
        CONSTRAINT uq_recovery_evidence_organization_id_proposal_id_docume_1dc0 UNIQUE
(organization_id, proposal_id, document_id, binding_hash),
        CONSTRAINT fk_recovery_evidence_organization_id_recovery_proposals FOREIGN
KEY(organization_id, proposal_id) REFERENCES recovery_proposals (organization_id, id),
        CONSTRAINT fk_recovery_evidence_organization_id_documents FOREIGN KEY(organization_id,
document_id) REFERENCES documents (organization_id, id),
	CONSTRAINT ck_recovery_evidence_source_hash CHECK (sha256 ~ '^[a-f0-9]{64}$'),
	CONSTRAINT ck_recovery_evidence_source_size CHECK (file_size >= 0),
        CONSTRAINT fk_recovery_evidence_organization_id_organizations FOREIGN
KEY(organization_id) REFERENCES organizations (id)
);
CREATE INDEX ix_recovery_evidence_organization_id ON recovery_evidence (organization_id);
CREATE TABLE recovery_records (
	case_id UUID NOT NULL,
	number INTEGER NOT NULL,
	previous_id UUID,
	original_id UUID,
	instrument_id UUID,
	proposal_id UUID,
	actor_id UUID NOT NULL,
	audit_id UUID NOT NULL,
	kind VARCHAR(24) NOT NULL,
	amount NUMERIC(20, 6),
	principal NUMERIC(20, 6),
	gross NUMERIC(20, 6),
	tax NUMERIC(20, 6),
	fees NUMERIC(20, 6),
	withholding NUMERIC(20, 6),
	net_cash NUMERIC(20, 6),
	other NUMERIC(20, 6),
	currency VARCHAR(3),
	economic JSONB,
	recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
	value JSONB NOT NULL,
	pins JSONB NOT NULL,
	reason VARCHAR(4000) NOT NULL,
	organization_id UUID NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_recovery_records PRIMARY KEY (id),
	CONSTRAINT uq_recovery_records_organization_id_id UNIQUE (organization_id, id),
        CONSTRAINT uq_recovery_records_organization_id_case_id_number UNIQUE (organization_id,
case_id, number),
	CONSTRAINT uq_recovery_records_organization_id_proposal_id UNIQUE
    (organization_id, proposal_id),
        CONSTRAINT fk_recovery_records_organization_id_recovery_cases FOREIGN
KEY(organization_id, case_id) REFERENCES recovery_cases (organization_id, id),
        CONSTRAINT fk_recovery_record_previous FOREIGN
KEY(organization_id, previous_id) REFERENCES recovery_records (organization_id, id),
        CONSTRAINT fk_recovery_record_original FOREIGN
KEY(organization_id, original_id) REFERENCES recovery_records (organization_id, id),
        CONSTRAINT fk_recovery_records_organization_id_recovery_instruments FOREIGN
KEY(organization_id, instrument_id) REFERENCES recovery_instruments (organization_id, id),
        CONSTRAINT fk_recovery_records_organization_id_recovery_proposals FOREIGN
KEY(organization_id, proposal_id) REFERENCES recovery_proposals (organization_id, id),
        CONSTRAINT fk_recovery_records_organization_id_financial_audit FOREIGN
KEY(organization_id, audit_id) REFERENCES financial_audit (organization_id, id) DEFERRABLE
INITIALLY DEFERRED,
	CONSTRAINT ck_recovery_records_record_number CHECK (number > 0),
        CONSTRAINT ck_recovery_records_record_currency CHECK (currency IS NULL OR currency ~
'^[A-Z]{3}$'),
        CONSTRAINT ck_recovery_records_allocation_presence CHECK ((kind IN
('realization','reversal')) = (amount IS NOT NULL)),
	CONSTRAINT ck_recovery_records_realization_positive CHECK (kind <> 'realization' OR amount > 0),
        CONSTRAINT ck_recovery_records_reversal_negative CHECK (kind <> 'reversal' OR (amount <
0 AND original_id IS NOT NULL)),
        CONSTRAINT ck_recovery_records_allocation_instrument CHECK (kind NOT IN
('realization','reversal') OR instrument_id IS NOT NULL),
	CONSTRAINT ck_recovery_records_principal_nonnegative CHECK
    (principal IS NULL OR principal >= 0),
        CONSTRAINT ck_recovery_records_record_kind CHECK (kind IN
('readiness','party','party_revoked','instrument','alias','credit_state','claim','vendor','realization','reversal','cost','lifecycle','workflow','note','observation','rejected','withdrawn','retire')),
	CONSTRAINT fk_recovery_records_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id),
        CONSTRAINT fk_recovery_records_organization_id_organizations FOREIGN
KEY(organization_id) REFERENCES organizations (id)
);
CREATE INDEX ix_recovery_records_organization_id ON recovery_records (organization_id);
CREATE TABLE recovery_aliases (
	instrument_id UUID NOT NULL,
	record_id UUID NOT NULL,
	alias_hash VARCHAR(64) NOT NULL,
	organization_id UUID NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_recovery_aliases PRIMARY KEY (id),
	CONSTRAINT uq_recovery_aliases_organization_id_id UNIQUE (organization_id, id),
	CONSTRAINT uq_recovery_aliases_organization_id_alias_hash UNIQUE (organization_id, alias_hash),
        CONSTRAINT fk_recovery_aliases_organization_id_recovery_instruments FOREIGN
KEY(organization_id, instrument_id) REFERENCES recovery_instruments (organization_id, id),
        CONSTRAINT fk_recovery_aliases_organization_id_recovery_records FOREIGN
KEY(organization_id, record_id) REFERENCES recovery_records (organization_id, id),
        CONSTRAINT fk_recovery_aliases_organization_id_organizations FOREIGN
KEY(organization_id) REFERENCES organizations (id)
);
CREATE INDEX ix_recovery_aliases_organization_id ON recovery_aliases (organization_id);
CREATE TABLE recovery_requests (
	actor_id UUID NOT NULL,
	audit_id UUID NOT NULL,
	request_key UUID NOT NULL,
	request_hash VARCHAR(64) NOT NULL,
	command VARCHAR(32) NOT NULL,
	counted BOOLEAN NOT NULL,
	result JSONB NOT NULL,
	organization_id UUID NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_recovery_requests PRIMARY KEY (id),
	CONSTRAINT uq_recovery_requests_organization_id_id UNIQUE (organization_id, id),
        CONSTRAINT uq_recovery_requests_organization_id_actor_id_request_key UNIQUE
(organization_id, actor_id, request_key),
        CONSTRAINT fk_recovery_requests_organization_id_financial_audit FOREIGN
KEY(organization_id, audit_id) REFERENCES financial_audit (organization_id, id) DEFERRABLE
INITIALLY DEFERRED,
	CONSTRAINT fk_recovery_requests_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id),
        CONSTRAINT fk_recovery_requests_organization_id_organizations FOREIGN
KEY(organization_id) REFERENCES organizations (id)
);
CREATE INDEX ix_recovery_requests_organization_id ON recovery_requests (organization_id);

CREATE TABLE recovery_publications (
	case_id UUID,
	record_id UUID,
	committed_at TIMESTAMP WITH TIME ZONE NOT NULL,
	actor_id UUID NOT NULL,
	audit_id UUID NOT NULL,
	organization_id UUID NOT NULL,
	id UUID NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_recovery_publications PRIMARY KEY (id),
	CONSTRAINT uq_recovery_publications_organization_id_id UNIQUE (organization_id, id),
	CONSTRAINT uq_recovery_publications_organization_id_case_id UNIQUE (organization_id, case_id),
        CONSTRAINT uq_recovery_publications_organization_id_record_id UNIQUE (organization_id,
record_id),
        CONSTRAINT fk_recovery_publications_organization_id_recovery_cases FOREIGN
KEY(organization_id, case_id) REFERENCES recovery_cases (organization_id, id),
        CONSTRAINT fk_recovery_publications_organization_id_recovery_records FOREIGN
KEY(organization_id, record_id) REFERENCES recovery_records (organization_id, id),
        CONSTRAINT fk_recovery_publications_organization_id_financial_audit FOREIGN
KEY(organization_id, audit_id) REFERENCES financial_audit (organization_id, id) DEFERRABLE
INITIALLY DEFERRED,
        CONSTRAINT ck_recovery_publications_publication_subject CHECK ((case_id IS NULL) <>
(record_id IS NULL)),
        CONSTRAINT fk_recovery_publications_actor_id_users FOREIGN KEY(actor_id) REFERENCES
users (id),
        CONSTRAINT fk_recovery_publications_organization_id_organizations FOREIGN
KEY(organization_id) REFERENCES organizations (id)
)

;
CREATE INDEX ix_recovery_publications_organization_id ON recovery_publications
(organization_id);

"""


def upgrade():
    op.execute(SCHEMA)
    op.execute(GUARDS)
    for table in TABLES:
        op.execute(
            f"CREATE TRIGGER recovery_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION financial_immutable()"
        )
        op.execute(
            f"CREATE TRIGGER recovery_authority BEFORE INSERT ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION recovery_guard()"
        )
        if table not in {"recovery_aliases", "recovery_evidence"}:
            op.execute(
                f"CREATE TRIGGER recovery_audit AFTER INSERT ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION recovery_audit()"
            )


def downgrade():
    connection = op.get_bind()
    for table in TABLES:
        if connection.scalar(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table})")):
            raise RuntimeError("Downgrade would destroy Recovery Ledger history")
    if connection.scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM financial_audit WHERE action LIKE 'recovery.%')")
    ):
        raise RuntimeError("Downgrade would destroy Recovery Ledger audit history")
    op.execute("DROP TRIGGER recovery_source_guard ON documents")
    for table in reversed(TABLES):
        op.drop_table(table)
    for name in ["recovery_guard", "recovery_audit", "recovery_document_guard"]:
        op.execute(f"DROP FUNCTION {name}()")


GUARDS = r"""
CREATE FUNCTION recovery_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actual_commit timestamptz; actor_role text; p recovery_proposals; c recovery_cases;
        e financial_evaluations; previous recovery_records; ready recovery_records;
        decision financial_finding_decisions; original recovery_records;
        used numeric; ceiling numeric; instrument_review recovery_records;
        party recovery_records; proof proof_packages; family proof_families;
BEGIN
    PERFORM id FROM organizations WHERE id=NEW.organization_id FOR UPDATE;
    NEW.created_at := clock_timestamp();
    NEW.updated_at := NEW.created_at;
    IF TG_TABLE_NAME='recovery_evidence' THEN
        IF EXISTS(SELECT 1 FROM recovery_records WHERE organization_id=NEW.organization_id
            AND proposal_id=NEW.proposal_id) OR NOT EXISTS(SELECT 1 FROM recovery_proposals
            WHERE organization_id=NEW.organization_id AND id=NEW.proposal_id
            AND authority->'evidence_manifest' @> jsonb_build_array(jsonb_build_object(
                'document_id',NEW.document_id::text,'binding_hash',NEW.binding_hash,
                'sha256',NEW.sha256,'file_size',NEW.file_size))) THEN
            RAISE EXCEPTION 'Recovery evidence must preserve its immutable proposal manifest';
        END IF;
        IF NOT EXISTS(SELECT 1 FROM documents WHERE organization_id=NEW.organization_id
            AND id=NEW.document_id AND sha256=NEW.sha256 AND file_size=NEW.file_size
            AND mime_type=NEW.media_type) THEN
            RAISE EXCEPTION 'Recovery evidence must pin the protected original';
        END IF;
        RETURN NEW;
    END IF;
    IF TG_TABLE_NAME='recovery_aliases' THEN
        IF NOT EXISTS(SELECT 1 FROM recovery_records WHERE organization_id=NEW.organization_id
            AND id=NEW.record_id AND kind='alias' AND instrument_id=NEW.instrument_id) THEN
            RAISE EXCEPTION 'Economic aliases require reviewed authority';
        END IF;
        RETURN NEW;
    END IF;
    SELECT role INTO actor_role FROM organization_memberships
        WHERE organization_id=NEW.organization_id AND user_id=NEW.actor_id FOR SHARE;
    IF TG_TABLE_NAME='recovery_publications' THEN
        IF actor_role IS NULL OR current_setting('track_commit_timestamp') <> 'on' THEN
            RAISE EXCEPTION 'Commit provenance requires current membership and commit tracking';
        END IF;
        IF NEW.case_id IS NOT NULL THEN
            SELECT pg_xact_commit_timestamp(xmin) INTO actual_commit FROM recovery_cases
                WHERE organization_id=NEW.organization_id AND id=NEW.case_id;
        ELSE
            SELECT pg_xact_commit_timestamp(xmin) INTO actual_commit FROM recovery_records
                WHERE organization_id=NEW.organization_id AND id=NEW.record_id;
        END IF;
        IF actual_commit IS NULL OR NEW.committed_at IS DISTINCT FROM actual_commit THEN
            RAISE EXCEPTION 'Known-at must be the actual committed source transaction';
        END IF;
        RETURN NEW;
    END IF;
    IF actor_role IS NULL OR actor_role='viewer' THEN
        RAISE EXCEPTION 'Recovery action requires current membership';
    END IF;
    IF TG_TABLE_NAME='recovery_cases' THEN
        SELECT * INTO e FROM financial_evaluations WHERE organization_id=NEW.organization_id
            AND id=NEW.evaluation_id;
        SELECT * INTO decision FROM financial_finding_decisions
            WHERE organization_id=NEW.organization_id AND evaluation_id=e.id
            ORDER BY number DESC LIMIT 1;
        IF e.potential IS NULL OR e.outcome <> 'POTENTIAL_LEAKAGE'
            OR decision.status='false_positive' THEN
            RAISE EXCEPTION 'An eligible positive finding is required';
        END IF;
    ELSIF TG_TABLE_NAME='recovery_records' THEN
        NEW.recorded_at := clock_timestamp();
        SELECT * INTO c FROM recovery_cases WHERE organization_id=NEW.organization_id
            AND id=NEW.case_id;
        SELECT * INTO e FROM financial_evaluations WHERE organization_id=NEW.organization_id
            AND id=c.evaluation_id;
        SELECT * INTO previous FROM recovery_records WHERE organization_id=NEW.organization_id
            AND case_id=NEW.case_id ORDER BY number DESC LIMIT 1;
        IF NEW.number <> COALESCE(previous.number,0)+1 OR
            NEW.previous_id IS DISTINCT FROM previous.id THEN
            RAISE EXCEPTION 'Recovery predecessor changed';
        END IF;
        IF NEW.instrument_id IS NOT NULL AND NEW.kind <> 'alias' AND EXISTS(
            SELECT 1 FROM recovery_records WHERE organization_id=NEW.organization_id
            AND instrument_id=NEW.instrument_id AND kind <> 'alias'
            AND case_id <> NEW.case_id) THEN
            RAISE EXCEPTION 'Recovery instrument cannot obtain authority in another case';
        END IF;
        IF NEW.kind NOT IN ('workflow','note','observation','withdrawn')
            AND actor_role NOT IN ('owner','admin') THEN
            RAISE EXCEPTION 'Recovery final authority requires owner/admin';
        END IF;
        IF NEW.proposal_id IS NOT NULL THEN
            SELECT * INTO p FROM recovery_proposals WHERE organization_id=NEW.organization_id
                AND id=NEW.proposal_id;
            IF p.case_id IS DISTINCT FROM NEW.case_id OR
                (NEW.kind NOT IN ('rejected','withdrawn') AND
                 (p.kind IS DISTINCT FROM NEW.kind OR p.value IS DISTINCT FROM NEW.value)) THEN
                RAISE EXCEPTION 'Approval must preserve the exact reviewed proposal';
            END IF;
        ELSIF NEW.kind NOT IN ('workflow','note','observation','lifecycle') THEN
            RAISE EXCEPTION 'Financial authority requires a pinned proposal';
        END IF;
        IF NEW.kind NOT IN ('rejected','withdrawn','workflow','note','observation','lifecycle') THEN
            IF p.authority->>'head' IS DISTINCT FROM NEW.previous_id::text OR
                jsonb_array_length(p.authority->'evidence_manifest') IS DISTINCT FROM
                    (SELECT count(*)::integer FROM recovery_evidence WHERE
                     organization_id=NEW.organization_id AND proposal_id=p.id) THEN
                RAISE EXCEPTION 'Recovery approval must preserve proposal revision and evidence';
            END IF;
        END IF;
        SELECT * INTO decision FROM financial_finding_decisions WHERE
            organization_id=NEW.organization_id AND evaluation_id=e.id
            ORDER BY number DESC LIMIT 1;
        SELECT * INTO ready FROM recovery_records WHERE organization_id=NEW.organization_id
            AND case_id=c.id AND kind='readiness' ORDER BY number DESC LIMIT 1;
        IF NEW.kind='readiness' THEN
            ceiling := (NEW.value->>'pursuit')::numeric;
            IF NEW.principal IS DISTINCT FROM ceiling THEN
                RAISE EXCEPTION 'Typed pursuit principal must match approved meaning';
            END IF;
            SELECT COALESCE(sum(amount),0) INTO used FROM recovery_records WHERE
                organization_id=NEW.organization_id AND case_id=c.id;
            IF decision.status IS DISTINCT FROM 'confirmed' OR
                decision.id::text IS DISTINCT FROM NEW.value->>'decision_id' OR
                ceiling <= 0 OR ceiling > e.potential OR ceiling < used OR
                NEW.value->>'currency' IS DISTINCT FROM e.currency OR
                NEW.value->>'tax_basis' IS DISTINCT FROM 'EXCLUSIVE' THEN
                RAISE EXCEPTION 'Pursuit revision would invalidate financial authority';
            END IF;
            IF EXISTS(SELECT 1 FROM recovery_records WHERE organization_id=NEW.organization_id
                AND case_id=c.id AND kind='claim' AND value->>'state'='RECORDED_ACTION'
                AND number=(SELECT max(number) FROM recovery_records WHERE
                    organization_id=NEW.organization_id AND case_id=c.id AND kind='claim')
                AND principal > ceiling) THEN
                RAISE EXCEPTION 'Pursuit revision cannot invalidate current action';
            END IF;
        END IF;
        IF NEW.kind IN ('readiness','realization') THEN
            IF decision.status IS DISTINCT FROM 'confirmed' OR
                NEW.pins->>'decision_id' IS DISTINCT FROM decision.id::text OR
                NEW.pins->>'evaluation_fingerprint' IS DISTINCT FROM e.fingerprint OR
                NEW.pins->>'integrity' IS DISTINCT FROM 'VERIFIED' THEN
                RAISE EXCEPTION 'Recovery financial input pins must be verified';
            END IF;
            SELECT * INTO proof FROM proof_packages WHERE organization_id=NEW.organization_id
                AND id=(NEW.pins->>'proof_id')::uuid;
            SELECT * INTO family FROM proof_families WHERE organization_id=NEW.organization_id
                AND id=proof.family_id;
            IF proof.completeness IS DISTINCT FROM 'COMPLETE' OR
                proof.fingerprint IS DISTINCT FROM NEW.pins->>'proof_fingerprint' OR
                family.evaluation_id IS DISTINCT FROM e.id OR
                family.kind IS DISTINCT FROM 'MONETARY_FINDING_PROOF' THEN
                RAISE EXCEPTION 'An exact complete monetary proof is required';
            END IF;
        END IF;
        IF NEW.kind='realization' THEN
            IF ready.id::text IS DISTINCT FROM NEW.value->>'readiness_id' OR
                NEW.currency IS DISTINCT FROM e.currency OR
                NEW.amount IS DISTINCT FROM (p.value->>'amount')::numeric OR
                p.value->>'principal' IS NULL OR
                NEW.amount > (p.value->>'principal')::numeric OR
                NEW.value->>'tax_basis' NOT IN ('EXCLUSIVE','INCLUSIVE') OR
                NEW.value->>'completed' IS DISTINCT FROM 'true' OR
                NEW.value->>'method' NOT IN ('CASH','APPLIED_CREDIT','LIABILITY_REDUCTION') THEN
                RAISE EXCEPTION 'Recovery allocation disagrees with reviewed compatible principal';
            END IF;
            IF EXISTS(SELECT 1 FROM recovery_records WHERE organization_id=NEW.organization_id
                AND case_id=c.id AND kind='retire') OR COALESCE((SELECT value->>'state'
                FROM recovery_records WHERE organization_id=NEW.organization_id AND case_id=c.id
                AND kind='lifecycle' ORDER BY number DESC LIMIT 1),'OPEN') <> 'OPEN' THEN
                RAISE EXCEPTION 'New positive recovery requires an open nonretired case';
            END IF;
            SELECT * INTO party FROM recovery_records WHERE organization_id=NEW.organization_id
                AND id=(NEW.value->>'party_id')::uuid AND case_id=c.id AND kind='party';
            IF party.id IS NULL OR EXISTS(SELECT 1 FROM recovery_records WHERE
                organization_id=NEW.organization_id AND case_id=c.id AND kind='party_revoked'
                AND value->>'party_id'=party.id::text) OR
                party.value->>'payer' IS DISTINCT FROM NEW.value->>'payer' OR
                party.value->>'payee' IS DISTINCT FROM NEW.value->>'payee' OR
                party.value->>'beneficiary' IS DISTINCT FROM NEW.value->>'beneficiary' THEN
                RAISE EXCEPTION 'Recovery parties must match reviewed economic attribution';
            END IF;
            SELECT COALESCE(sum(amount),0) INTO used FROM recovery_records WHERE
                organization_id=NEW.organization_id AND case_id=c.id;
            IF used+NEW.amount > (ready.value->>'pursuit')::numeric THEN
                RAISE EXCEPTION 'Recovery exceeds unused pursuit basis';
            END IF;
            SELECT * INTO instrument_review FROM recovery_records WHERE
                organization_id=NEW.organization_id
                AND id=(NEW.value->>'instrument_review_id')::uuid
                AND instrument_id=NEW.instrument_id AND kind='instrument' AND case_id=c.id;
            IF instrument_review.id IS NULL OR instrument_review.principal IS NULL OR
                instrument_review.value->>'origin' IS DISTINCT FROM 'POST_FINDING_REMEDY' OR
                jsonb_array_length(instrument_review.value->'related_cases') > 1 OR
                EXISTS(SELECT 1 FROM recovery_records WHERE organization_id=NEW.organization_id
                    AND instrument_id=NEW.instrument_id AND kind='realization'
                    AND case_id<>c.id) THEN
                RAISE EXCEPTION 'Unresolved recovery instrument or deferred shared attribution';
            END IF;
            SELECT COALESCE(sum(amount),0) INTO used FROM recovery_records WHERE
                organization_id=NEW.organization_id AND instrument_id=NEW.instrument_id;
            IF used+NEW.amount > instrument_review.principal THEN
                RAISE EXCEPTION 'Recovery exceeds unused economic instrument';
            END IF;
        ELSIF NEW.kind='reversal' THEN
            SELECT * INTO original FROM recovery_records WHERE organization_id=NEW.organization_id
                AND id=NEW.original_id AND case_id=c.id AND kind='realization';
            SELECT COALESCE(sum(amount),0) INTO used FROM recovery_records WHERE
                organization_id=NEW.organization_id AND original_id=original.id AND kind='reversal';
            IF original.id IS NULL OR NEW.instrument_id IS DISTINCT FROM original.instrument_id OR
                NEW.amount IS DISTINCT FROM -(p.value->>'amount')::numeric OR
                original.amount+used+NEW.amount < 0 THEN
                RAISE EXCEPTION 'Reversal must preserve the outstanding original allocation';
            END IF;
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE FUNCTION recovery_audit() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO financial_audit(id,organization_id,actor_id,action,target_id,detail)
    VALUES(NEW.audit_id,NEW.organization_id,NEW.actor_id,
        'recovery.' || CASE TG_TABLE_NAME
            WHEN 'recovery_cases' THEN 'case.created'
            WHEN 'recovery_instruments' THEN 'instrument.created'
            WHEN 'recovery_proposals' THEN 'proposal.prepared'
            WHEN 'recovery_publications' THEN 'commit.recorded'
            WHEN 'recovery_requests' THEN CASE WHEN to_jsonb(NEW)->'result' ? 'error'
                THEN 'operation.failed' ELSE 'operation.completed' END
            ELSE to_jsonb(NEW)->>'kind' END, NEW.id,
        jsonb_build_object('table',TG_TABLE_NAME,'case_id',to_jsonb(NEW)->'case_id',
            'number',to_jsonb(NEW)->'number','previous_id',to_jsonb(NEW)->'previous_id',
            'proposal_id',to_jsonb(NEW)->'proposal_id','request_key',to_jsonb(NEW)->'request_key',
            'original_id',to_jsonb(NEW)->'original_id','reason',to_jsonb(NEW)->'reason',
            'error_code',to_jsonb(NEW)->'result'->'error'->'code',
            'role_at_action',(SELECT role FROM organization_memberships
                WHERE organization_id=NEW.organization_id AND user_id=NEW.actor_id)));
    RETURN NEW;
END $$;
CREATE FUNCTION recovery_document_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (TG_OP='DELETE' OR NEW.sha256 IS DISTINCT FROM OLD.sha256 OR
        NEW.file_size IS DISTINCT FROM OLD.file_size OR
        NEW.storage_key IS DISTINCT FROM OLD.storage_key OR
        NEW.mime_type IS DISTINCT FROM OLD.mime_type) AND EXISTS(SELECT 1 FROM recovery_evidence
            WHERE organization_id=OLD.organization_id AND document_id=OLD.id) THEN
        RAISE EXCEPTION 'Referenced recovery source evidence is immutable';
    END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER recovery_source_guard BEFORE UPDATE OR DELETE ON documents
    FOR EACH ROW EXECUTE FUNCTION recovery_document_guard();
"""
