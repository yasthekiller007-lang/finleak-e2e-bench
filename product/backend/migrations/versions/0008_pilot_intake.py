"""Immutable operational admission profiles and worker-shared attempts.

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

# Frozen schema: no financial model or monetary column.
SCHEMA = """
CREATE TABLE pilot_intake_profiles (
 name VARCHAR(32) NOT NULL, actor_id UUID NOT NULL, configuration JSONB NOT NULL,
 id UUID NOT NULL, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
 updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
 CONSTRAINT pk_pilot_intake_profiles PRIMARY KEY(id),
 CONSTRAINT uq_pilot_intake_profiles_name UNIQUE(name),
 CONSTRAINT ck_pilot_intake_profiles_intake_configuration
 CHECK(jsonb_typeof(configuration)='object'),
 CONSTRAINT fk_pilot_intake_profiles_actor_id_users FOREIGN KEY(actor_id) REFERENCES users(id)
);
CREATE TABLE pilot_intake_attempts (
 organization_id UUID NOT NULL, actor_id UUID NOT NULL, profile VARCHAR(32) NOT NULL,
 operation VARCHAR(7) NOT NULL, slot INTEGER NOT NULL, id UUID NOT NULL,
 created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
 updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
 CONSTRAINT pk_pilot_intake_attempts PRIMARY KEY(id),
 CONSTRAINT ck_pilot_intake_attempts_intake_operation CHECK(operation IN ('upload','process')),
 CONSTRAINT ck_pilot_intake_attempts_intake_slot CHECK(slot BETWEEN 0 AND 3),
 CONSTRAINT fk_pilot_intake_attempts_organization_id_organizations
 FOREIGN KEY(organization_id) REFERENCES organizations(id),
 CONSTRAINT fk_pilot_intake_attempts_actor_id_users FOREIGN KEY(actor_id) REFERENCES users(id),
 CONSTRAINT fk_pilot_intake_attempts_profile_pilot_intake_profiles
 FOREIGN KEY(profile) REFERENCES pilot_intake_profiles(name)
);
CREATE INDEX ix_pilot_intake_attempts_organization_id ON pilot_intake_attempts(organization_id);
CREATE INDEX ix_pilot_intake_attempts_actor_created ON pilot_intake_attempts(actor_id,created_at);
"""

GUARDS = """
CREATE FUNCTION pilot_intake_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Operational admission history is immutable'; END $$;

CREATE FUNCTION pilot_intake_profile_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE config jsonb := NEW.configuration;
BEGIN
 IF NEW.name <> 'pilot-intake/1' OR config->>'profile' IS DISTINCT FROM NEW.name
 OR (SELECT count(*) FROM jsonb_object_keys(config)) <> 4
 OR jsonb_typeof(config->'upload_slots') IS DISTINCT FROM 'number'
 OR jsonb_typeof(config->'process_slots') IS DISTINCT FROM 'number'
 OR jsonb_typeof(config->'actor_operations_per_minute') IS DISTINCT FROM 'number'
 OR (config->>'upload_slots')::int NOT BETWEEN 1 AND 4
 OR (config->>'process_slots')::int NOT BETWEEN 1 AND 4
 OR (config->>'actor_operations_per_minute')::int NOT BETWEEN 1 AND 1000 THEN
  RAISE EXCEPTION 'Invalid versioned admission profile';
 END IF;
 NEW.created_at := clock_timestamp(); NEW.updated_at := NEW.created_at;
 RETURN NEW;
END $$;

CREATE FUNCTION pilot_intake_attempt_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE config jsonb; slot_key bigint;
BEGIN
 PERFORM pg_advisory_xact_lock_shared(hashtextextended(NEW.actor_id::text,7002));
 PERFORM pg_advisory_xact_lock_shared(hashtextextended(NEW.organization_id::text,7005));
 IF EXISTS(SELECT 1 FROM pilot_user_access WHERE user_id=NEW.actor_id AND NOT active)
 OR EXISTS(SELECT 1 FROM pilot_tenant_access
           WHERE organization_id=NEW.organization_id AND NOT active)
 OR NOT EXISTS(SELECT 1 FROM organization_memberships WHERE
    user_id=NEW.actor_id AND organization_id=NEW.organization_id AND role<>'viewer') THEN
  RAISE EXCEPTION 'Current document intake authority required';
 END IF;
 SELECT configuration INTO config FROM pilot_intake_profiles WHERE name=NEW.profile;
 IF config IS NULL OR NEW.slot NOT BETWEEN 0 AND (config->>(NEW.operation||'_slots'))::int-1 THEN
  RAISE EXCEPTION 'Configured admission slot required';
 END IF;
 slot_key := hashtextextended(
   NEW.organization_id::text||':'||NEW.operation||':'||NEW.slot::text,7003);
 IF NOT EXISTS(SELECT 1 FROM pg_locks WHERE locktype='advisory' AND pid=pg_backend_pid()
   AND granted AND mode='ExclusiveLock' AND objsubid=1
   AND ((classid::bigint << 32) | objid::bigint)=slot_key) THEN
  RAISE EXCEPTION 'Worker-shared admission slot must be held';
 END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(NEW.actor_id::text,7004));
 NEW.created_at := clock_timestamp(); NEW.updated_at := NEW.created_at;
 IF (SELECT count(*) FROM pilot_intake_attempts WHERE actor_id=NEW.actor_id
      AND created_at >= NEW.created_at - interval '1 minute')
      >= (config->>'actor_operations_per_minute')::int THEN
  RAISE EXCEPTION USING ERRCODE='P7001',MESSAGE='Shared actor admission limit reached';
 END IF;
 RETURN NEW;
END $$;

CREATE FUNCTION pilot_tenant_intake_fence() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 PERFORM pg_advisory_xact_lock(hashtextextended(NEW.organization_id::text,7005));
 RETURN NEW;
END $$;
"""


def upgrade():
    op.execute(SCHEMA)
    op.execute(GUARDS)
    for table in ("pilot_intake_profiles", "pilot_intake_attempts"):
        op.execute(
            f"CREATE TRIGGER pilot_intake_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION pilot_intake_immutable()"
        )
    op.execute(
        "CREATE TRIGGER pilot_intake_profile BEFORE INSERT ON pilot_intake_profiles "
        "FOR EACH ROW EXECUTE FUNCTION pilot_intake_profile_guard()"
    )
    op.execute(
        "CREATE TRIGGER pilot_intake_attempt BEFORE INSERT ON pilot_intake_attempts "
        "FOR EACH ROW EXECUTE FUNCTION pilot_intake_attempt_guard()"
    )
    # Trigger names execute alphabetically: this precedes the existing organization fence.
    op.execute(
        "CREATE TRIGGER pilot_0_tenant_intake BEFORE INSERT OR UPDATE ON pilot_tenant_access "
        "FOR EACH ROW EXECUTE FUNCTION pilot_tenant_intake_fence()"
    )


def downgrade():
    for table in ("pilot_intake_profiles", "pilot_intake_attempts"):
        if op.get_bind().scalar(sa.text(f"SELECT EXISTS(SELECT 1 FROM {table})")):
            raise RuntimeError("Refusing to discard Phase 7 admission history")
    op.execute("DROP TRIGGER pilot_0_tenant_intake ON pilot_tenant_access")
    op.execute("DROP TABLE pilot_intake_attempts,pilot_intake_profiles")
    for name in (
        "pilot_intake_immutable",
        "pilot_intake_profile_guard",
        "pilot_intake_attempt_guard",
        "pilot_tenant_intake_fence",
    ):
        op.execute(f"DROP FUNCTION {name}()")
