"""Operational access controls and append-only operator attribution.

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

# Frozen operational schema; no financial model, amount or policy is changed.
SCHEMA = """
CREATE TABLE pilot_access_journal (
    actor_id UUID,
    organization_id UUID,
    user_id UUID,
    target_id UUID NOT NULL,
    request_id UUID,
    db_principal VARCHAR(63) NOT NULL,
    effective_role VARCHAR(63) NOT NULL,
    action VARCHAR(64) NOT NULL,
    reason VARCHAR(4000) NOT NULL,
    detail JSONB NOT NULL,
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_pilot_access_journal PRIMARY KEY (id),
    CONSTRAINT ck_pilot_access_journal_access_reason CHECK (length(reason) BETWEEN 1 AND 4000),
    CONSTRAINT ck_pilot_access_journal_access_detail CHECK (jsonb_typeof(detail) = 'object')
);
CREATE INDEX ix_pilot_access_journal_organization_id ON pilot_access_journal (organization_id);
CREATE INDEX ix_pilot_access_journal_user_id ON pilot_access_journal (user_id);
CREATE TABLE pilot_tenant_access (
    organization_id UUID NOT NULL,
    active BOOLEAN DEFAULT true NOT NULL,
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_pilot_tenant_access PRIMARY KEY (id),
    CONSTRAINT uq_pilot_tenant_access_organization_id UNIQUE (organization_id),
    CONSTRAINT fk_pilot_tenant_access_organization_id_organizations FOREIGN KEY(organization_id)
REFERENCES organizations (id)
);
CREATE TABLE pilot_user_access (
    user_id UUID NOT NULL,
    active BOOLEAN DEFAULT true NOT NULL,
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_pilot_user_access PRIMARY KEY (id),
    CONSTRAINT uq_pilot_user_access_user_id UNIQUE (user_id),
    CONSTRAINT fk_pilot_user_access_user_id_users FOREIGN KEY(user_id) REFERENCES users (id)
);
"""

GUARDS = """
CREATE FUNCTION pilot_identity_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE before_row jsonb := to_jsonb(OLD); after_row jsonb := to_jsonb(NEW);
BEGIN
  IF before_row->'id' IS DISTINCT FROM after_row->'id' THEN
    RAISE EXCEPTION 'Stable identity cannot be changed';
  END IF;
  IF TG_TABLE_NAME IN ('organization_memberships','documents','pilot_tenant_access')
     AND before_row->'organization_id' IS DISTINCT FROM after_row->'organization_id' THEN
    RAISE EXCEPTION 'Stable tenant identity cannot be changed';
  END IF;
  IF TG_TABLE_NAME IN ('organization_memberships','user_identities','pilot_user_access')
     AND before_row->'user_id' IS DISTINCT FROM after_row->'user_id' THEN
    RAISE EXCEPTION 'Stable user identity cannot be changed';
  END IF;
  IF TG_TABLE_NAME = 'user_identities' AND
     (before_row->'issuer' IS DISTINCT FROM after_row->'issuer' OR
      before_row->'subject' IS DISTINCT FROM after_row->'subject') THEN
    RAISE EXCEPTION 'Verified identity cannot be reassigned';
  END IF;
  IF TG_TABLE_NAME = 'documents' AND
     before_row->'storage_key' IS DISTINCT FROM after_row->'storage_key' THEN
    RAISE EXCEPTION 'Original storage identity cannot be changed';
  END IF;
  RETURN NEW;
END $$;

CREATE FUNCTION pilot_access_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE row_data jsonb := CASE WHEN TG_OP = 'DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
  old_data jsonb := CASE WHEN TG_OP = 'INSERT' THEN '{}'::jsonb ELSE to_jsonb(OLD) END;
  org uuid := (row_data->>'organization_id')::uuid;
  subject_id uuid := (row_data->>'user_id')::uuid;
  tenant_enabled boolean; privileged_fixture boolean;
  actor uuid; purpose text;
BEGIN
  SELECT rolsuper INTO privileged_fixture FROM pg_roles WHERE rolname = current_user;
  IF NOT privileged_fixture THEN
    actor := nullif(current_setting('fla.operator_actor',true),'')::uuid;
    purpose := current_setting('fla.operator_reason',true);
    IF actor IS NULL OR purpose IS NULL OR length(purpose) NOT BETWEEN 1 AND 4000
       OR NOT EXISTS(SELECT 1 FROM users WHERE id=actor) THEN
      RAISE EXCEPTION 'Attributed operator context required';
    END IF;
  END IF;
  IF TG_TABLE_NAME = 'pilot_user_access' THEN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Access state cannot be erased'; END IF;
    PERFORM pg_advisory_xact_lock(hashtextextended(subject_id::text,7002));
  ELSIF TG_TABLE_NAME = 'pilot_tenant_access' THEN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Access state cannot be erased'; END IF;
    PERFORM 1 FROM organizations WHERE id=org FOR UPDATE;
  ELSIF TG_TABLE_NAME = 'organizations' AND TG_OP <> 'DELETE' THEN
    RETURN NEW;
  ELSIF TG_TABLE_NAME = 'organization_memberships' THEN
    SELECT coalesce((SELECT active FROM pilot_tenant_access WHERE organization_id=org),true)
      INTO tenant_enabled;
    IF NOT privileged_fixture AND tenant_enabled THEN
      PERFORM pg_advisory_xact_lock(hashtextextended(subject_id::text,7002));
    END IF;
    PERFORM 1 FROM organizations WHERE id=org FOR UPDATE;
    SELECT coalesce((SELECT active FROM pilot_tenant_access WHERE organization_id=org),true)
      INTO tenant_enabled;
    IF NOT privileged_fixture AND TG_OP <> 'DELETE' THEN
      IF NOT tenant_enabled OR EXISTS(SELECT 1 FROM pilot_user_access
                                      WHERE user_id=subject_id AND NOT active) THEN
        RAISE EXCEPTION 'Deactivated access cannot obtain membership';
      END IF;
    END IF;
    IF NOT privileged_fixture AND tenant_enabled AND old_data->>'role' = 'owner'
       AND (TG_OP = 'DELETE' OR row_data->>'role' <> 'owner')
       AND NOT EXISTS(SELECT 1 FROM organization_memberships
                       WHERE organization_id=org AND role='owner' AND id<>OLD.id) THEN
      RAISE EXCEPTION 'Transfer ownership before removing the last owner';
    END IF;
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END $$;

CREATE FUNCTION pilot_access_audit() RETURNS trigger LANGUAGE plpgsql
SECURITY DEFINER SET search_path FROM CURRENT AS $$
DECLARE data jsonb := CASE WHEN TG_OP='DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
  prior jsonb := CASE WHEN TG_OP='INSERT' THEN '{}'::jsonb ELSE to_jsonb(OLD) END;
  actor uuid := nullif(current_setting('fla.operator_actor',true),'')::uuid;
  purpose text := coalesce(nullif(current_setting('fla.operator_reason',true),''),
                          'Privileged database change: attribution requires operator review');
  org uuid := (data->>'organization_id')::uuid;
BEGIN
  IF TG_TABLE_NAME='organizations' THEN org := (data->>'id')::uuid; END IF;
  IF TG_OP='UPDATE' AND data IS NOT DISTINCT FROM prior THEN RETURN NEW; END IF;
  INSERT INTO pilot_access_journal(id,actor_id,organization_id,user_id,target_id,request_id,
      db_principal,effective_role,action,reason,detail)
  VALUES(gen_random_uuid(),actor,org,(data->>'user_id')::uuid,(data->>'id')::uuid,
      nullif(current_setting('fla.operator_request',true),'')::uuid,
      session_user,coalesce(nullif(current_setting('role'),'none'),session_user),
      TG_TABLE_NAME||'.'||lower(TG_OP),purpose,
      jsonb_strip_nulls(jsonb_build_object('previous_role',prior->'role','role',data->'role',
          'previous_active',prior->'active','active',data->'active')));
  IF TG_OP='DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END $$;

CREATE FUNCTION pilot_journal_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Operator history is immutable'; END $$;

CREATE FUNCTION pilot_original_registration_lock() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(NEW.storage_key,7001));
  RETURN NEW;
END $$;
"""

IDENTITY_TABLES = [
    "users",
    "organizations",
    "organization_memberships",
    "user_identities",
    "documents",
    "pilot_user_access",
    "pilot_tenant_access",
]
ACCESS_TABLES = [
    "organizations",
    "organization_memberships",
    "pilot_user_access",
    "pilot_tenant_access",
]


def upgrade():
    op.execute(SCHEMA)
    op.execute(GUARDS)
    for table in IDENTITY_TABLES:
        op.execute(
            f"CREATE TRIGGER pilot_identity BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION pilot_identity_guard()"
        )
    for table in ACCESS_TABLES:
        op.execute(
            f"CREATE TRIGGER pilot_access BEFORE INSERT OR UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION pilot_access_guard()"
        )
        op.execute(
            f"CREATE TRIGGER pilot_access_audit AFTER INSERT OR UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION pilot_access_audit()"
        )
    op.execute(
        "CREATE TRIGGER pilot_journal_immutable BEFORE UPDATE OR DELETE "
        "ON pilot_access_journal FOR EACH ROW EXECUTE FUNCTION pilot_journal_immutable()"
    )
    op.execute(
        "CREATE TRIGGER pilot_original_registration BEFORE INSERT ON documents "
        "FOR EACH ROW EXECUTE FUNCTION pilot_original_registration_lock()"
    )


def downgrade():
    for table in ("pilot_user_access", "pilot_tenant_access", "pilot_access_journal"):
        if op.get_bind().scalar(sa.text(f"SELECT EXISTS(SELECT 1 FROM {table})")):
            raise RuntimeError("Refusing to discard Phase 7 access state or operator history")
    op.execute("DROP TRIGGER pilot_original_registration ON documents")
    for table in IDENTITY_TABLES:
        op.execute(f"DROP TRIGGER pilot_identity ON {table}")
    for table in ACCESS_TABLES:
        op.execute(f"DROP TRIGGER pilot_access ON {table}")
        op.execute(f"DROP TRIGGER pilot_access_audit ON {table}")
    op.execute("DROP TABLE pilot_access_journal,pilot_user_access,pilot_tenant_access")
    for name in (
        "pilot_identity_guard",
        "pilot_access_guard",
        "pilot_access_audit",
        "pilot_journal_immutable",
        "pilot_original_registration_lock",
    ):
        op.execute(f"DROP FUNCTION {name}()")
