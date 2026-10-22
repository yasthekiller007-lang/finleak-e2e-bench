"""Exact-byte operational quarantine and immutable controlled release.

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

# Frozen operational schema. No financial money, policy or canonical proof changes.
SCHEMA = """
CREATE TABLE pilot_source_scans (
    organization_id UUID NOT NULL,
    document_id UUID NOT NULL,
    actor_id UUID NOT NULL,
    request_key UUID NOT NULL,
    sequence INTEGER NOT NULL,
    sha256 VARCHAR(64) NOT NULL,
    file_size INTEGER NOT NULL,
    actual_sha256 VARCHAR(64),
    actual_file_size INTEGER,
    verdict VARCHAR(16) NOT NULL,
    scanner_profile VARCHAR(32) NOT NULL,
    scanner_version VARCHAR(100),
    reason VARCHAR(4000) NOT NULL,
    db_principal VARCHAR(63) DEFAULT session_user NOT NULL,
    effective_role VARCHAR(63) DEFAULT current_user NOT NULL,
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_pilot_source_scans PRIMARY KEY (id),
CONSTRAINT fk_pilot_source_scans_organization_id_documents FOREIGN KEY(organization_id,
document_id) REFERENCES documents (organization_id, id),
CONSTRAINT uq_pilot_source_scans_organization_id_document_id_id UNIQUE (organization_id,
document_id, id),
CONSTRAINT uq_pilot_source_scans_organization_id_document_id_sequence UNIQUE (organization_id,
document_id, sequence),
CONSTRAINT uq_pilot_source_scans_organization_id_request_key UNIQUE (organization_id,
request_key),
    CONSTRAINT ck_pilot_source_scans_scan_sequence CHECK (sequence > 0),
    CONSTRAINT ck_pilot_source_scans_scan_sha256 CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_pilot_source_scans_scan_size CHECK (file_size BETWEEN 1 AND 104857600),
CONSTRAINT ck_pilot_source_scans_scan_verdict CHECK (verdict IN
('CLEAN','INFECTED','SUSPICIOUS','UNAVAILABLE','TIMEOUT','MISMATCH','UNKNOWN')),
    CONSTRAINT ck_pilot_source_scans_scan_reason CHECK (length(reason) BETWEEN 1 AND 4000),
CONSTRAINT ck_pilot_source_scans_scan_clean_bytes CHECK (verdict <> 'CLEAN' OR
(actual_sha256=sha256 AND actual_file_size=file_size AND actual_sha256 IS NOT NULL AND
actual_file_size IS NOT NULL AND scanner_version IS NOT NULL)),
    CONSTRAINT fk_pilot_source_scans_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id)
);
CREATE INDEX ix_pilot_source_scans_organization_id ON pilot_source_scans (organization_id);
CREATE TABLE pilot_source_releases (
    organization_id UUID NOT NULL,
    document_id UUID NOT NULL,
    scan_id UUID NOT NULL,
    actor_id UUID NOT NULL,
    request_key UUID NOT NULL,
    verified_sha256 VARCHAR(64) NOT NULL,
    verified_file_size INTEGER NOT NULL,
    reason VARCHAR(4000) NOT NULL,
    db_principal VARCHAR(63) DEFAULT session_user NOT NULL,
    effective_role VARCHAR(63) DEFAULT current_user NOT NULL,
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_pilot_source_releases PRIMARY KEY (id),
CONSTRAINT fk_pilot_source_releases_organization_id_pilot_source_scans FOREIGN
KEY(organization_id, document_id, scan_id) REFERENCES pilot_source_scans (organization_id,
document_id, id),
CONSTRAINT uq_pilot_source_releases_organization_id_request_key UNIQUE (organization_id,
request_key),
CONSTRAINT uq_pilot_source_releases_organization_id_document_id_scan_id UNIQUE
(organization_id, document_id, scan_id),
    CONSTRAINT ck_pilot_source_releases_release_reason CHECK (length(reason) BETWEEN 1 AND 4000),
    CONSTRAINT fk_pilot_source_releases_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id)
);
CREATE INDEX ix_pilot_source_releases_organization_id ON pilot_source_releases
(organization_id);
CREATE TABLE pilot_source_requests (
    organization_id UUID NOT NULL,
    document_id UUID NOT NULL,
    actor_id UUID NOT NULL,
    request_key UUID NOT NULL,
    operation VARCHAR(7) NOT NULL,
    fingerprint VARCHAR(64) NOT NULL,
    result_id UUID NOT NULL,
    reason VARCHAR(4000) NOT NULL,
    db_principal VARCHAR(63) DEFAULT session_user NOT NULL,
    effective_role VARCHAR(63) DEFAULT current_user NOT NULL,
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_pilot_source_requests PRIMARY KEY (id),
CONSTRAINT fk_pilot_source_requests_organization_id_documents FOREIGN KEY(organization_id,
document_id) REFERENCES documents (organization_id, id),
CONSTRAINT uq_pilot_source_requests_organization_id_request_key UNIQUE (organization_id,
request_key),
CONSTRAINT ck_pilot_source_requests_source_request_operation CHECK (operation IN
('SCAN','RELEASE')),
CONSTRAINT ck_pilot_source_requests_source_request_fingerprint CHECK (fingerprint ~
'^[0-9a-f]{64}$'),
CONSTRAINT ck_pilot_source_requests_source_request_reason CHECK (length(reason) BETWEEN 1 AND
4000),
    CONSTRAINT fk_pilot_source_requests_actor_id_users FOREIGN KEY(actor_id) REFERENCES users (id)
);
CREATE INDEX ix_pilot_source_requests_organization_id ON pilot_source_requests
(organization_id);
"""

GUARDS = """
CREATE FUNCTION pilot_source_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Operational source history is immutable'; END $$;

CREATE FUNCTION pilot_source_authority_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE doc documents; scanned pilot_source_scans; latest integer; actor_role text;
  final_action boolean; version_parts text[];
BEGIN
 PERFORM pg_advisory_xact_lock_shared(hashtextextended(NEW.actor_id::text,7002));
 PERFORM 1 FROM organizations WHERE id=NEW.organization_id FOR UPDATE;
 IF EXISTS(SELECT 1 FROM pilot_user_access WHERE user_id=NEW.actor_id AND NOT active)
 OR EXISTS(SELECT 1 FROM pilot_tenant_access
           WHERE organization_id=NEW.organization_id AND NOT active) THEN
  RAISE EXCEPTION 'Current source action authority required';
 END IF;
 SELECT role INTO actor_role FROM organization_memberships WHERE
   organization_id=NEW.organization_id AND user_id=NEW.actor_id;
 final_action := TG_TABLE_NAME='pilot_source_releases' OR
   (TG_TABLE_NAME='pilot_source_requests' AND to_jsonb(NEW)->>'operation'='RELEASE');
 IF actor_role IS NULL OR actor_role='viewer' OR
    (final_action AND actor_role NOT IN ('owner','admin')) THEN
  RAISE EXCEPTION 'Current source action authority required';
 END IF;
 SELECT * INTO doc FROM documents WHERE organization_id=NEW.organization_id
   AND id=NEW.document_id FOR UPDATE;
 IF doc.id IS NULL THEN RAISE EXCEPTION 'Tenant source identity required'; END IF;
 SELECT coalesce(max(sequence),0) INTO latest FROM pilot_source_scans
   WHERE organization_id=NEW.organization_id AND document_id=NEW.document_id;
 IF TG_TABLE_NAME='pilot_source_scans' THEN
  IF NEW.sequence <> latest+1 OR NEW.sha256<>doc.sha256 OR NEW.file_size<>doc.file_size
     OR NEW.scanner_profile<>'private-clamav/1' THEN
   RAISE EXCEPTION 'Pinned current source scan required';
  END IF;
  IF NEW.verdict='CLEAN' AND
     (NEW.scanner_version IS NULL OR NEW.scanner_version !~
       '^clamav/1[.](4|5)[.][0-9]+;database/[0-9]{1,10}$') THEN
   RAISE EXCEPTION 'Qualified private scanner version required';
  END IF;
  IF NEW.verdict='CLEAN' THEN
   version_parts := regexp_match(NEW.scanner_version,'^clamav/1[.]([45])[.]([0-9]+);');
   IF (version_parts[1]='4' AND version_parts[2]::int<6) OR
      (version_parts[1]='5' AND version_parts[2]::int<4) THEN
    RAISE EXCEPTION 'Qualified private scanner version required';
   END IF;
  END IF;
 ELSIF TG_TABLE_NAME='pilot_source_releases' THEN
  SELECT * INTO scanned FROM pilot_source_scans WHERE organization_id=NEW.organization_id
    AND document_id=NEW.document_id AND id=NEW.scan_id;
  IF scanned.id IS NULL OR scanned.sequence<>latest OR scanned.verdict<>'CLEAN'
     OR scanned.sha256<>doc.sha256 OR scanned.file_size<>doc.file_size
     OR NEW.verified_sha256<>doc.sha256 OR NEW.verified_file_size<>doc.file_size THEN
   RAISE EXCEPTION 'Current clean verified source release required';
  END IF;
 ELSE
  IF NEW.operation='SCAN' THEN
   IF NOT has_table_privilege(current_user,'pilot_source_scans','INSERT') OR
      NOT EXISTS(SELECT 1 FROM pilot_source_scans WHERE organization_id=NEW.organization_id
                  AND document_id=NEW.document_id AND id=NEW.result_id) THEN
    RAISE EXCEPTION 'Private scanner request binding required';
   END IF;
  ELSIF NEW.operation='RELEASE' THEN
   IF NOT EXISTS(SELECT 1 FROM pilot_source_releases WHERE organization_id=NEW.organization_id
                  AND document_id=NEW.document_id AND id=NEW.result_id) THEN
    RAISE EXCEPTION 'Controlled release request binding required';
   END IF;
  ELSE
   RAISE EXCEPTION 'Supported operational source action required';
  END IF;
 END IF;
 NEW.db_principal := session_user; NEW.effective_role := current_user;
 NEW.created_at := clock_timestamp(); NEW.updated_at := NEW.created_at;
 RETURN NEW;
END $$;

CREATE FUNCTION pilot_scanned_original_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF (NEW.sha256 IS DISTINCT FROM OLD.sha256 OR NEW.file_size IS DISTINCT FROM OLD.file_size
     OR NEW.storage_key IS DISTINCT FROM OLD.storage_key) AND
     EXISTS(SELECT 1 FROM pilot_source_scans WHERE organization_id=OLD.organization_id
            AND document_id=OLD.id) THEN
  RAISE EXCEPTION 'Scanned original identity is immutable';
 END IF;
 RETURN NEW;
END $$;
"""


def upgrade():
    op.execute(SCHEMA)
    op.execute(GUARDS)
    for table in ("pilot_source_scans", "pilot_source_releases", "pilot_source_requests"):
        op.execute(
            f"CREATE TRIGGER pilot_source_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION pilot_source_immutable()"
        )
        op.execute(
            f"CREATE TRIGGER pilot_source_authority BEFORE INSERT ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION pilot_source_authority_guard()"
        )
    op.execute(
        "CREATE TRIGGER pilot_scanned_original BEFORE UPDATE ON documents "
        "FOR EACH ROW EXECUTE FUNCTION pilot_scanned_original_guard()"
    )


def downgrade():
    for table in ("pilot_source_scans", "pilot_source_releases", "pilot_source_requests"):
        if op.get_bind().scalar(sa.text(f"SELECT EXISTS(SELECT 1 FROM {table})")):
            raise RuntimeError("Refusing to discard Phase 7 quarantine or release history")
    op.execute("DROP TRIGGER pilot_scanned_original ON documents")
    op.execute("DROP TABLE pilot_source_requests,pilot_source_releases,pilot_source_scans")
    for name in (
        "pilot_source_immutable",
        "pilot_source_authority_guard",
        "pilot_scanned_original_guard",
    ):
        op.execute(f"DROP FUNCTION {name}()")
