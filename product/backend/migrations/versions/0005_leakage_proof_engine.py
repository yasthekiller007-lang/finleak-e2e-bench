"""Immutable tenant-bound proof content and audited presentation records.

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

TABLES = [
    "proof_families",
    "proof_packages",
    "proof_bindings",
    "proof_events",
    "proof_artifacts",
    "proof_requests",
    "proof_successors",
]


def upgrade():
    op.create_unique_constraint(
        "uq_financial_revision_evidence_organization_id_id",
        "financial_revision_evidence",
        ["organization_id", "id"],
    )
    op.execute("""

CREATE TABLE proof_families (
    evaluation_id UUID NOT NULL, 
    kind VARCHAR(40) NOT NULL, 
    actor_id UUID NOT NULL, 
    organization_id UUID NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_proof_families PRIMARY KEY (id), 
    CONSTRAINT uq_proof_families_organization_id_id UNIQUE (organization_id, id), 
    CONSTRAINT uq_proof_families_organization_id_evaluation_id_kind UNIQUE (organization_id,
    evaluation_id, kind),
    CONSTRAINT fk_proof_families_organization_id_financial_evaluations FOREIGN
    KEY(organization_id, evaluation_id) REFERENCES financial_evaluations (organization_id, id),
    CONSTRAINT ck_proof_families_proof_kind CHECK (kind IN ('MONETARY_FINDING_PROOF',
    'ASSESSED_COMPARISON_EVIDENCE', 'BLOCKED_ASSESSMENT_EVIDENCE')),
    CONSTRAINT fk_proof_families_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id), 
    CONSTRAINT fk_proof_families_organization_id_organizations FOREIGN KEY(organization_id)
    REFERENCES organizations (id)
)


""")
    op.execute("CREATE INDEX ix_proof_families_organization_id ON proof_families (organization_id)")
    op.execute("""

CREATE TABLE proof_packages (
    family_id UUID NOT NULL, 
    number INTEGER NOT NULL, 
    previous_id UUID, 
    revision_reason VARCHAR(32), 
    actor_id UUID NOT NULL, 
    audit_id UUID NOT NULL, 
    fingerprint VARCHAR(64) NOT NULL, 
    completeness VARCHAR(12) NOT NULL, 
    core JSONB NOT NULL, 
    envelope JSONB NOT NULL, 
    organization_id UUID NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_proof_packages PRIMARY KEY (id), 
    CONSTRAINT uq_proof_packages_organization_id_id UNIQUE (organization_id, id), 
    CONSTRAINT uq_proof_packages_organization_id_family_id_id UNIQUE (organization_id,
    family_id, id),
    CONSTRAINT uq_proof_packages_organization_id_family_id_number UNIQUE (organization_id,
    family_id, number),
    CONSTRAINT uq_proof_packages_organization_id_family_id_fingerprint UNIQUE (organization_id,
    family_id, fingerprint),
    CONSTRAINT fk_proof_packages_organization_id_proof_families FOREIGN KEY(organization_id,
    family_id) REFERENCES proof_families (organization_id, id),
    CONSTRAINT fk_proof_packages_organization_id_financial_audit FOREIGN KEY(organization_id,
    audit_id) REFERENCES financial_audit (organization_id, id) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT fk_proof_packages_organization_id_proof_packages FOREIGN KEY(organization_id,
    family_id, previous_id) REFERENCES proof_packages (organization_id, family_id, id),
    CONSTRAINT ck_proof_packages_proof_revision_positive CHECK (number > 0), 
    CONSTRAINT ck_proof_packages_proof_fingerprint CHECK (fingerprint ~ '^[a-f0-9]{64}$'), 
    CONSTRAINT ck_proof_packages_proof_completeness CHECK (completeness IN ('COMPLETE',
    'INCOMPLETE')),
    CONSTRAINT ck_proof_packages_proof_revision_reason CHECK ((number = 1 AND previous_id IS
    NULL AND revision_reason IS NULL) OR (number > 1 AND previous_id IS NOT NULL AND
    revision_reason IN ('REPAIRED_EVIDENCE', 'SCHEMA_EVOLUTION', 'ASSEMBLY_EVOLUTION'))),
    CONSTRAINT fk_proof_packages_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id), 
    CONSTRAINT fk_proof_packages_organization_id_organizations FOREIGN KEY(organization_id)
    REFERENCES organizations (id)
)


""")
    op.execute("CREATE INDEX ix_proof_packages_organization_id ON proof_packages (organization_id)")
    op.execute("""

CREATE TABLE proof_bindings (
    package_id UUID NOT NULL, 
    revision_id UUID NOT NULL, 
    evidence_id UUID NOT NULL, 
    document_id UUID NOT NULL, 
    run_id UUID, 
    field_id UUID, 
    binding_id VARCHAR(64) NOT NULL, 
    input_pointer VARCHAR(2000) NOT NULL, 
    organization_id UUID NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_proof_bindings PRIMARY KEY (id), 
    CONSTRAINT fk_proof_bindings_organization_id_proof_packages FOREIGN KEY(organization_id,
    package_id) REFERENCES proof_packages (organization_id, id),
    CONSTRAINT fk_proof_bindings_organization_id_financial_revisions FOREIGN
    KEY(organization_id, revision_id) REFERENCES financial_revisions (organization_id, id),
    CONSTRAINT fk_proof_bindings_organization_id_financial_revision_evidence FOREIGN
    KEY(organization_id, evidence_id) REFERENCES financial_revision_evidence (organization_id,
    id),
    CONSTRAINT fk_proof_bindings_organization_id_documents FOREIGN KEY(organization_id,
    document_id) REFERENCES documents (organization_id, id),
    CONSTRAINT fk_proof_bindings_organization_id_extracted_fields FOREIGN KEY(organization_id,
    document_id, run_id, field_id) REFERENCES extracted_fields (organization_id, document_id,
    extraction_run_id, id),
    CONSTRAINT uq_proof_bindings_organization_id_package_id_binding_id_5ce4 UNIQUE
    (organization_id, package_id, binding_id, input_pointer),
    CONSTRAINT ck_proof_bindings_proof_binding_lineage CHECK ((field_id IS NULL) = (run_id IS
    NULL)),
    CONSTRAINT fk_proof_bindings_organization_id_organizations FOREIGN KEY(organization_id)
    REFERENCES organizations (id)
)


""")
    op.execute("CREATE INDEX ix_proof_bindings_organization_id ON proof_bindings (organization_id)")
    op.execute("""

CREATE TABLE proof_events (
    package_id UUID NOT NULL, 
    number INTEGER NOT NULL,
    previous_id UUID, 
    actor_id UUID NOT NULL, 
    audit_id UUID NOT NULL, 
    kind VARCHAR(40) NOT NULL, 
    detail JSONB NOT NULL, 
    organization_id UUID NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_proof_events PRIMARY KEY (id),
    CONSTRAINT uq_proof_events_organization_id_package_id_number UNIQUE (organization_id,
    package_id, number),
    CONSTRAINT ck_proof_events_proof_event_number CHECK (number > 0),
    CONSTRAINT uq_proof_events_organization_id_id UNIQUE (organization_id, id), 
    CONSTRAINT uq_proof_events_organization_id_package_id_id UNIQUE (organization_id,
    package_id, id),
    CONSTRAINT fk_proof_events_organization_id_proof_packages FOREIGN KEY(organization_id,
    package_id) REFERENCES proof_packages (organization_id, id),
    CONSTRAINT fk_proof_events_organization_id_financial_audit FOREIGN KEY(organization_id,
    audit_id) REFERENCES financial_audit (organization_id, id) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT fk_proof_events_organization_id_proof_events FOREIGN KEY(organization_id,
    package_id, previous_id) REFERENCES proof_events (organization_id, package_id, id),
    CONSTRAINT ck_proof_events_proof_event_kind CHECK (kind IN ('annotation.appended',
    'annotation.retracted', 'review.proposed', 'review.finalized', 'disclosure.proposed',
    'disclosure.approved', 'artifact.downloaded', 'source.downloaded', 'integrity.observed')),
    CONSTRAINT fk_proof_events_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id), 
    CONSTRAINT fk_proof_events_organization_id_organizations FOREIGN KEY(organization_id)
    REFERENCES organizations (id)
)


""")
    op.execute("CREATE INDEX ix_proof_events_organization_id ON proof_events (organization_id)")
    op.execute("""

CREATE TABLE proof_artifacts (
    package_id UUID NOT NULL, 
    disclosure_id UUID, 
    actor_id UUID NOT NULL, 
    audit_id UUID NOT NULL, 
    content_hash VARCHAR(64) NOT NULL, 
    content BYTEA NOT NULL, 
    organization_id UUID NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_proof_artifacts PRIMARY KEY (id), 
    CONSTRAINT uq_proof_artifacts_organization_id_id UNIQUE (organization_id, id), 
    CONSTRAINT uq_proof_artifacts_organization_id_package_id_content_hash UNIQUE
    (organization_id, package_id, content_hash),
    CONSTRAINT fk_proof_artifacts_organization_id_proof_packages FOREIGN KEY(organization_id,
    package_id) REFERENCES proof_packages (organization_id, id),
    CONSTRAINT fk_proof_artifacts_organization_id_proof_events FOREIGN KEY(organization_id,
    package_id, disclosure_id) REFERENCES proof_events (organization_id, package_id, id),
    CONSTRAINT fk_proof_artifacts_organization_id_financial_audit FOREIGN KEY(organization_id,
    audit_id) REFERENCES financial_audit (organization_id, id) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT ck_proof_artifacts_artifact_hash CHECK (content_hash ~ '^[a-f0-9]{64}$'), 
    CONSTRAINT ck_proof_artifacts_artifact_nonempty CHECK (octet_length(content) > 0), 
    CONSTRAINT fk_proof_artifacts_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id), 
    CONSTRAINT fk_proof_artifacts_organization_id_organizations FOREIGN KEY(organization_id)
    REFERENCES organizations (id)
)


""")
    op.execute(
        "CREATE INDEX ix_proof_artifacts_organization_id ON proof_artifacts (organization_id)"
    )
    op.execute("""

CREATE TABLE proof_requests (
    actor_id UUID NOT NULL, 
    audit_id UUID NOT NULL, 
    request_key VARCHAR(36) NOT NULL, 
    request_hash VARCHAR(64) NOT NULL, 
    command VARCHAR(40) NOT NULL, 
    counted BOOLEAN NOT NULL, 
    result JSONB NOT NULL, 
    organization_id UUID NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_proof_requests PRIMARY KEY (id), 
    CONSTRAINT uq_proof_requests_organization_id_request_key UNIQUE (organization_id, request_key), 
    CONSTRAINT fk_proof_requests_organization_id_financial_audit FOREIGN KEY(organization_id,
    audit_id) REFERENCES financial_audit (organization_id, id) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT fk_proof_requests_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id), 
    CONSTRAINT fk_proof_requests_organization_id_organizations FOREIGN KEY(organization_id)
    REFERENCES organizations (id)
)


""")
    op.execute("CREATE INDEX ix_proof_requests_organization_id ON proof_requests (organization_id)")
    op.execute("""

CREATE TABLE proof_successors (
    predecessor_id UUID NOT NULL, 
    successor_id UUID NOT NULL, 
    actor_id UUID NOT NULL, 
    audit_id UUID NOT NULL, 
    reason VARCHAR(2000) NOT NULL, 
    organization_id UUID NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    CONSTRAINT pk_proof_successors PRIMARY KEY (id), 
    CONSTRAINT fk_proof_successor_predecessor FOREIGN KEY(organization_id,
    predecessor_id) REFERENCES proof_packages (organization_id, id),
    CONSTRAINT fk_proof_successor_successor FOREIGN KEY(organization_id,
    successor_id) REFERENCES proof_packages (organization_id, id),
    CONSTRAINT fk_proof_successors_organization_id_financial_audit FOREIGN KEY(organization_id,
    audit_id) REFERENCES financial_audit (organization_id, id) DEFERRABLE INITIALLY DEFERRED,
    CONSTRAINT uq_proof_successors_organization_id_predecessor_id UNIQUE (organization_id,
    predecessor_id),
    CONSTRAINT uq_proof_successors_organization_id_successor_id UNIQUE (organization_id,
    successor_id),
    CONSTRAINT ck_proof_successors_successor_distinct CHECK (predecessor_id <> successor_id), 
    CONSTRAINT fk_proof_successors_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id), 
    CONSTRAINT fk_proof_successors_organization_id_organizations FOREIGN KEY(organization_id)
    REFERENCES organizations (id)
)


""")
    op.execute(
        "CREATE INDEX ix_proof_successors_organization_id ON proof_successors (organization_id)"
    )
    op.execute(r"""
        CREATE FUNCTION proof_canonical(value jsonb) RETURNS text LANGUAGE plpgsql IMMUTABLE AS $$
        DECLARE result text; item record; character text; code integer; original text;
        BEGIN
            CASE jsonb_typeof(value)
            WHEN 'null' THEN RETURN 'null';
            WHEN 'boolean' THEN RETURN value::text;
            WHEN 'number' THEN
                IF value::text !~ '^-?(0|[1-9][0-9]*)$' THEN
                    RAISE EXCEPTION 'Proof numeric tokens must be integers';
                END IF;
                RETURN value::text;
            WHEN 'string' THEN
                original := value #>> '{}'; result := '"';
                FOR position IN 1..length(original) LOOP
                    character := substr(original, position, 1); code := ascii(character);
                    IF code < 32 THEN result := result || chr(92) || 'u' ||
                    lpad(to_hex(code),4,'0');
                    ELSIF code IN (34,92) THEN result := result || chr(92) || character;
                    ELSE result := result || character; END IF;
                END LOOP;
                RETURN result || '"';
            WHEN 'array' THEN
                result := '[';
                FOR item IN SELECT v FROM jsonb_array_elements(value) AS a(v) LOOP
                    IF result <> '[' THEN result := result || ','; END IF;
                    result := result || proof_canonical(item.v);
                END LOOP;
                RETURN result || ']';
            WHEN 'object' THEN
                result := '{';
                FOR item IN SELECT k,v FROM jsonb_each(value) AS a(k,v) ORDER BY k COLLATE "C" LOOP
                    IF result <> '{' THEN result := result || ','; END IF;
                    result := result || proof_canonical(to_jsonb(item.k)) || ':'
                    || proof_canonical(item.v);
                END LOOP;
                RETURN result || '}';
            ELSE RAISE EXCEPTION 'Unsupported canonical data';
            END CASE;
        END $$;

        CREATE FUNCTION proof_scope(core jsonb) RETURNS jsonb LANGUAGE sql IMMUTABLE AS $$
            SELECT jsonb_build_object(
                'invoice',core->'identity'->'invoice_source_id',
                'key',core->'identity'->'scope_key',
                'members',(SELECT jsonb_agg(v ORDER BY v::text COLLATE "C")
                    FROM jsonb_array_elements(core->'billing'->'scope'->'members') AS a(v)),
                'scope',core->'billing'->'scope'->'scope',
                'currency',core->'billing'->'scope'->'currency',
                'unit',core->'billing'->'scope'->'unit',
                'service_from',core->'billing'->'scope'->'service_from',
                'service_to',core->'billing'->'scope'->'service_to',
                'invoice_date',core->'billing'->'scope'->'invoice_date',
                'event_date',core->'billing'->'scope'->'event_date',
                'cycle',core->'billing'->'scope'->'cycle',
                'allocation_parent',core->'billing'->'scope'->'allocation_parent');
        $$;

        CREATE FUNCTION proof_authority_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE actor_role text; final_action boolean; e financial_evaluations;
                family proof_families; predecessor proof_packages; successor proof_packages;
                previous proof_events; evidence financial_revision_evidence;
                computed text; expected_kind text; artifact jsonb;
        BEGIN
            PERFORM id FROM organizations WHERE id=NEW.organization_id FOR UPDATE;
            IF TG_TABLE_NAME = 'proof_bindings' THEN
                SELECT * INTO evidence FROM financial_revision_evidence
                    WHERE organization_id=NEW.organization_id AND id=NEW.evidence_id;
                IF evidence.revision_id IS DISTINCT FROM NEW.revision_id OR
                   evidence.document_id IS DISTINCT FROM NEW.document_id OR
                   evidence.run_id IS DISTINCT FROM NEW.run_id OR
                   evidence.field_id IS DISTINCT FROM NEW.field_id OR
                   NOT (evidence.detail->'supports' ? NEW.input_pointer) THEN
                    RAISE EXCEPTION 'Proof binding disagrees with historical evidence';
                END IF;
                RETURN NEW;
            END IF;
            SELECT role INTO actor_role FROM organization_memberships
                WHERE organization_id=NEW.organization_id AND user_id=NEW.actor_id FOR SHARE;
            final_action := TG_TABLE_NAME IN ('proof_artifacts','proof_successors') OR
                (TG_TABLE_NAME='proof_events' AND to_jsonb(NEW)->>'kind' IN
                    ('review.finalized','disclosure.approved','artifact.downloaded')) OR
                (TG_TABLE_NAME='proof_requests' AND to_jsonb(NEW)->>'command' IN
                    ('export','successor','review.finalized','disclosure.approved'));
            IF actor_role IS NULL OR (actor_role='viewer' AND NOT
                (TG_TABLE_NAME='proof_events' AND to_jsonb(NEW)->>'kind' IN
                ('source.downloaded','integrity.observed'))) OR
                (final_action AND actor_role NOT IN ('owner','admin')) THEN
                RAISE EXCEPTION 'Proof action requires a current authorized membership';
            END IF;
            IF TG_TABLE_NAME='proof_families' THEN
                SELECT * INTO e FROM financial_evaluations
                    WHERE organization_id=NEW.organization_id AND id=NEW.evaluation_id;
                expected_kind := CASE WHEN e.outcome='POTENTIAL_LEAKAGE' THEN
                'MONETARY_FINDING_PROOF'
                    WHEN e.outcome='NEEDS_REVIEW' THEN 'BLOCKED_ASSESSMENT_EVIDENCE'
                    WHEN e.outcome IN ('NO_OVERCHARGE','UNDERCHARGE') THEN
                    'ASSESSED_COMPARISON_EVIDENCE'
                    ELSE NULL END;
                IF expected_kind IS DISTINCT FROM NEW.kind THEN
                    RAISE EXCEPTION 'Proof kind must preserve the financial outcome';
                END IF;
            ELSIF TG_TABLE_NAME='proof_packages' THEN
                SELECT * INTO family FROM proof_families
                    WHERE organization_id=NEW.organization_id AND id=NEW.family_id;
                SELECT * INTO e FROM financial_evaluations
                    WHERE organization_id=NEW.organization_id AND id=family.evaluation_id;
                computed := encode(sha256(convert_to('FLA-PROOF-MANIFEST/1' || chr(10) ||
                    proof_canonical(NEW.core),'UTF8')),'hex');
                IF computed IS DISTINCT FROM NEW.fingerprint OR
                    NEW.envelope->>'manifest_fingerprint' IS DISTINCT FROM computed OR
                    NEW.envelope->>'audit_id' IS DISTINCT FROM NEW.audit_id::text OR
                    NEW.envelope->>'package_id' IS DISTINCT FROM NEW.id::text OR
                    NEW.core->'identity'->>'organization_id' IS DISTINCT FROM
                    NEW.organization_id::text OR
                    NEW.core->'identity'->>'evaluation_id' IS DISTINCT FROM e.id::text OR
                    NEW.core->'identity'->>'evaluation_fingerprint' IS DISTINCT
                    FROM e.fingerprint OR
                    NEW.core->'identity'->>'kind' IS DISTINCT FROM family.kind OR
                    NEW.core->'financial'->>'outcome' IS DISTINCT FROM e.outcome OR
                    NEW.core->'financial'->>'reason_code' IS DISTINCT FROM e.reason_code OR
                    (NEW.core->'financial'->>'currency') IS DISTINCT FROM e.currency OR
                    (NEW.core->'financial'->>'expected') IS DISTINCT FROM e.expected::text OR
                    (NEW.core->'financial'->>'actual') IS DISTINCT FROM e.actual::text OR
                    (NEW.core->'financial'->>'discrepancy') IS DISTINCT FROM e.discrepancy::text OR
                    (NEW.core->'financial'->>'potential') IS DISTINCT FROM e.potential::text OR
                    NEW.core->'completeness'->>'state' IS DISTINCT FROM NEW.completeness OR
                    (NEW.core->'identity'->>'finding_id') IS DISTINCT FROM
                        (CASE WHEN e.outcome='POTENTIAL_LEAKAGE' THEN e.id::text ELSE NULL END) THEN
                    RAISE EXCEPTION 'Proof core must preserve immutable
                    financial truth and identity';
                END IF;
                IF NEW.previous_id IS NOT NULL THEN
                    SELECT * INTO predecessor FROM proof_packages
                        WHERE organization_id=NEW.organization_id AND id=NEW.previous_id;
                    IF predecessor.number+1 <> NEW.number OR EXISTS (
                        SELECT 1 FROM proof_packages WHERE organization_id=NEW.organization_id
                        AND family_id=NEW.family_id AND number>=NEW.number) THEN
                        RAISE EXCEPTION 'Proof revision predecessor is stale';
                    END IF;
                END IF;
            ELSIF TG_TABLE_NAME='proof_events' THEN
                IF NEW.kind IN ('review.proposed','review.finalized') AND
                    COALESCE(NEW.detail->>'status','') NOT IN ('REVIEWED','NEEDS_REVIEW') THEN
                    RAISE EXCEPTION 'Proof review status is invalid';
                END IF;
                IF NEW.number <> (SELECT COALESCE(max(number),0)+1 FROM proof_events
                    WHERE organization_id=NEW.organization_id AND package_id=NEW.package_id) THEN
                    RAISE EXCEPTION 'Proof event sequence is stale';
                END IF;
                IF NEW.kind='review.finalized' AND NEW.previous_id IS DISTINCT FROM (
                    SELECT id FROM proof_events WHERE organization_id=NEW.organization_id
                    AND package_id=NEW.package_id AND kind='review.finalized'
                    ORDER BY number DESC LIMIT 1) THEN
                    RAISE EXCEPTION 'Proof review predecessor is stale';
                END IF;
                IF NEW.kind LIKE 'annotation.%%' AND NEW.previous_id IS NOT NULL AND EXISTS (
                    SELECT 1 FROM proof_events WHERE organization_id=NEW.organization_id
                    AND previous_id=NEW.previous_id AND kind LIKE 'annotation.%%') THEN
                    RAISE EXCEPTION 'Proof annotation predecessor is stale';
                END IF;
                IF NEW.kind IN ('annotation.retracted','disclosure.approved') OR
                    (NEW.previous_id IS NOT NULL AND NEW.kind IN
                    ('annotation.appended','disclosure.proposed')) THEN
                    SELECT * INTO previous FROM proof_events WHERE
                    organization_id=NEW.organization_id
                        AND package_id=NEW.package_id AND id=NEW.previous_id;
                    IF previous.id IS NULL OR (NEW.kind='disclosure.approved' AND
                        previous.kind<>'disclosure.proposed') OR
                        (NEW.kind LIKE 'annotation.%%' AND
                        (previous.kind<>'annotation.appended' OR
                         (actor_role='analyst' AND previous.actor_id<>NEW.actor_id))) OR
                        (NEW.kind='disclosure.proposed' AND
                         previous.kind<>'disclosure.proposed') OR
                        (NEW.kind IN ('disclosure.proposed','disclosure.approved') AND EXISTS (
                            SELECT 1 FROM proof_events WHERE organization_id=NEW.organization_id
                            AND previous_id=NEW.previous_id AND kind=NEW.kind)) THEN
                        RAISE EXCEPTION 'Proof event predecessor is invalid';
                    END IF;
                END IF;
            ELSIF TG_TABLE_NAME='proof_artifacts' THEN
                IF encode(sha256(NEW.content),'hex') <> NEW.content_hash THEN
                    RAISE EXCEPTION 'Artifact bytes disagree with checksum';
                END IF;
                SELECT * INTO predecessor FROM proof_packages WHERE
                    organization_id=NEW.organization_id AND id=NEW.package_id;
                artifact := convert_from(NEW.content,'UTF8')::jsonb;
                IF convert_to(proof_canonical(artifact),'UTF8') IS DISTINCT FROM NEW.content THEN
                    RAISE EXCEPTION 'Artifact must use the canonical JSON profile';
                END IF;
                IF NEW.disclosure_id IS NULL THEN
                    IF artifact->'core' IS DISTINCT FROM predecessor.core OR
                       artifact->'envelope' IS DISTINCT FROM predecessor.envelope THEN
                        RAISE EXCEPTION 'Artifact cannot change canonical proof content';
                    END IF;
                ELSIF artifact ? 'core' OR artifact ? 'envelope' OR
                    artifact->'disclosure'->>'parent_manifest_fingerprint' IS DISTINCT
                        FROM predecessor.fingerprint OR
                    artifact->'disclosure'->>'approval_id' IS DISTINCT
                        FROM NEW.disclosure_id::text OR
                    artifact->>'disclosure_hash' IS DISTINCT FROM encode(sha256(convert_to(
                        'FLA-PROOF-DISCLOSURE/1' || chr(10) ||
                        proof_canonical(artifact->'disclosure'),'UTF8')),'hex') THEN
                    RAISE EXCEPTION 'Disclosure artifact identity is invalid';
                END IF;
                IF NEW.disclosure_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM proof_events WHERE organization_id=NEW.organization_id
                    AND package_id=NEW.package_id AND id=NEW.disclosure_id AND
                    kind='disclosure.approved') THEN
                    RAISE EXCEPTION 'Export requires an approved disclosure';
                END IF;
            ELSIF TG_TABLE_NAME='proof_successors' THEN
                SELECT * INTO predecessor FROM proof_packages
                    WHERE organization_id=NEW.organization_id AND id=NEW.predecessor_id;
                SELECT * INTO successor FROM proof_packages
                    WHERE organization_id=NEW.organization_id AND id=NEW.successor_id;
                IF predecessor.core->'billing'->'scope' IS NULL OR
                    predecessor.core->'billing'->'scope'='null'::jsonb OR
                    successor.core->'billing'->'scope'='null'::jsonb OR
                    predecessor.core->'billing'->'scope'->>'currency' IS NULL OR
                    successor.core->'billing'->'scope'->>'currency' IS NULL OR
                    proof_scope(predecessor.core) IS DISTINCT FROM proof_scope(successor.core) OR
                    predecessor.family_id=successor.family_id THEN
                    RAISE EXCEPTION 'Successors require distinct evaluations of
                    the same known scope';
                END IF;
                IF EXISTS (WITH RECURSIVE chain(id) AS (
                    SELECT NEW.successor_id UNION
                    SELECT s.successor_id FROM proof_successors s JOIN chain c
                    ON c.id=s.predecessor_id
                    WHERE s.organization_id=NEW.organization_id)
                    SELECT 1 FROM chain WHERE id=NEW.predecessor_id) THEN
                    RAISE EXCEPTION 'Proof successor cycle is forbidden';
                END IF;
            END IF;
            RETURN NEW;
        END $$;

        CREATE FUNCTION proof_record_audit() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE action_name text;
        BEGIN
            action_name := CASE TG_TABLE_NAME
                WHEN 'proof_packages' THEN 'proof.issued'
                WHEN 'proof_events' THEN 'proof.' || (to_jsonb(NEW)->>'kind')
                WHEN 'proof_artifacts' THEN 'proof.artifact.created'
                WHEN 'proof_successors' THEN 'proof.successor.created'
                ELSE CASE WHEN to_jsonb(NEW)->'result' ? 'error' THEN 'proof.operation.failed'
                          ELSE 'proof.operation.completed' END END;
            INSERT INTO financial_audit(id,organization_id,actor_id,action,target_id,detail)
            VALUES(NEW.audit_id,NEW.organization_id,NEW.actor_id,action_name,NEW.id,
                jsonb_build_object('table',TG_TABLE_NAME,'number',to_jsonb(NEW)->'number',
                    'previous_id',to_jsonb(NEW)->'previous_id',
                    'fingerprint',to_jsonb(NEW)->'fingerprint',
                    'package_id',to_jsonb(NEW)->'package_id',
                    'request_key',to_jsonb(NEW)->'request_key',
                    'command',to_jsonb(NEW)->'command',
                    'error_code',to_jsonb(NEW)->'result'->'error'->'code',
                    'detail',to_jsonb(NEW)->'detail',
                    'predecessor_id',to_jsonb(NEW)->'predecessor_id',
                    'successor_id',to_jsonb(NEW)->'successor_id',
                    'reason',to_jsonb(NEW)->'reason',
                    'role_at_action',(SELECT role FROM organization_memberships
                        WHERE organization_id=NEW.organization_id AND user_id=NEW.actor_id)));
            RETURN NEW;
        END $$;
    """)
    for table in TABLES:
        op.execute(
            f"CREATE TRIGGER proof_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION financial_immutable()"
        )
        op.execute(
            f"CREATE TRIGGER proof_authority BEFORE INSERT ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION proof_authority_guard()"
        )
        if table not in {"proof_families", "proof_bindings"}:
            op.execute(
                f"CREATE TRIGGER proof_audit AFTER INSERT ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION proof_record_audit()"
            )
    op.execute("""
        CREATE FUNCTION proof_document_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF (TG_OP='DELETE' OR NEW.sha256 IS DISTINCT FROM OLD.sha256 OR
                NEW.storage_key IS DISTINCT FROM OLD.storage_key OR
                NEW.file_size IS DISTINCT FROM OLD.file_size OR
                NEW.document_type IS DISTINCT FROM OLD.document_type) AND EXISTS (
                SELECT 1 FROM proof_packages WHERE organization_id=OLD.organization_id AND
                core->'sources' @> jsonb_build_array(
                    jsonb_build_object('document_id',OLD.id::text))) THEN
                RAISE EXCEPTION 'Historical proof source evidence is immutable';
            END IF;
            IF TG_OP='DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER proof_source_guard BEFORE UPDATE OR DELETE ON documents
            FOR EACH ROW EXECUTE FUNCTION proof_document_guard();
    """)


def downgrade():
    connection = op.get_bind()
    if any(
        connection.scalar(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table})")) for table in TABLES
    ):
        raise RuntimeError(
            "Downgrade would lose Phase 5 proof history; explicit migration required"
        )
    # Includes failed operations whose authoritative audit history must also survive.
    if connection.scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM financial_audit WHERE action LIKE 'proof.%')")
    ):
        raise RuntimeError("Downgrade would lose Phase 5 audit history")
    for table in reversed(TABLES):
        op.drop_table(table)
    op.execute("DROP TRIGGER proof_source_guard ON documents")
    op.execute("DROP FUNCTION proof_document_guard()")
    op.execute("DROP FUNCTION proof_record_audit()")
    op.execute("DROP FUNCTION proof_authority_guard()")
    op.execute("DROP FUNCTION proof_scope(jsonb)")
    op.execute("DROP FUNCTION proof_canonical(jsonb)")
    op.drop_constraint(
        "uq_financial_revision_evidence_organization_id_id", "financial_revision_evidence"
    )
