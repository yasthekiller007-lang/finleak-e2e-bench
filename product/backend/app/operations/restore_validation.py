"""Read-only native-cluster restore qualification. Never publishes recovery known-at."""

import argparse
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from time import monotonic
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.preflight import EXPECTED_SCHEMA_REVISION
from app.db.base import Base
from app.db.models import Document
from app.db.session import create_database_engine
from app.modules.storage import build_storage
from app.operations.source_inventory import reconcile_originals
from app.proof.canonical import canonical, fingerprint
from app.proof.models import ProofPackage
from app.recovery.models import RecoveryCase, RecoveryRecord

PROFILE = "pilot-native-restore/1"


def normalize(value):
    if isinstance(value, UUID | Decimal | datetime | date):
        return {type(value).__name__: str(value)}
    if isinstance(value, bytes):
        return {"bytes_sha256": hashlib.sha256(value).hexdigest(), "size": len(value)}
    if type(value) is float:
        return {"binary_float": value.hex()}
    if isinstance(value, dict):
        return {str(k): normalize(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [normalize(v) for v in value]
    return value


def checksum(value):
    return hashlib.sha256(b"fla-native-restore-v1\0" + canonical(normalize(value))).hexdigest()


def snapshot(session, storage, *, max_rows=20000, work_seconds=25):
    """Requires an operator/admin connection and quiesced repeatable-read snapshot.

    Output is protected operational comparison evidence, not a financial export.
    Financial rows are hashed internally; money, names, quotations and credentials
    are never printed. Native backup preserves cluster/XID/commit provenance;
    logical copies are rejected, never repaired or blessed with new timestamps.
    """
    started = monotonic()
    if not 1 <= max_rows <= 20000 or not 1 <= work_seconds <= 25:
        raise ValueError("restore_invalid_bound")
    session.execute(text("SET TRANSACTION READ ONLY"))
    session.execute(text("SET LOCAL statement_timeout='5s'"))
    if session.scalar(text("SELECT version_num FROM alembic_version")) != EXPECTED_SCHEMA_REVISION:
        raise ValueError("restore_schema_mismatch")
    if session.scalar(text("SHOW track_commit_timestamp")) != "on":
        raise ValueError("restore_commit_tracking_unavailable")
    system = str(session.scalar(text("SELECT system_identifier FROM pg_control_system()")))
    tables, count, byte_count = {}, 0, 0
    for table in sorted(Base.metadata.tables.values(), key=lambda t: t.name):
        if monotonic() - started > work_seconds:
            raise ValueError("restore_work_bound")
        rows = session.execute(select(table).limit(max_rows - count + 1)).mappings().all()
        count += len(rows)
        if count > max_rows:
            raise ValueError("restore_row_bound")
        encoded = sorted(canonical(normalize(dict(row))).decode() for row in rows)
        byte_count += sum(len(row.encode()) for row in encoded)
        if byte_count > 50 * 1024 * 1024:
            raise ValueError("restore_byte_bound")
        tables[table.name] = {"count": len(rows), "sha256": checksum(encoded)}
    proofs = session.scalars(select(ProofPackage)).all()
    if any(fingerprint(row.core) != row.fingerprint for row in proofs):
        raise ValueError("restore_proof_fingerprint_mismatch")
    provenance = []
    for table, column in ((RecoveryCase, "case_id"), (RecoveryRecord, "record_id")):
        for identity, committed in session.execute(
            text(
                f"SELECT s.id, pg_xact_commit_timestamp(s.xmin) FROM {table.__tablename__} s "
                f"LEFT JOIN recovery_publications p ON p.{column}=s.id AND "
                f"p.organization_id=s.organization_id "
                "WHERE p.id IS NULL ORDER BY s.id"
            )
        ):
            if committed is None:
                raise ValueError("restore_uncaptured_provenance_unavailable")
            provenance.append(
                {
                    "table": table.__tablename__,
                    "id": str(identity),
                    "actual_original_commit": committed.isoformat(),
                }
            )
    triggers = session.execute(
        text(
            "SELECT c.relname,t.tgname,t.tgenabled,pg_get_triggerdef(t.oid) FROM "
            "pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON "
            "n.oid=c.relnamespace WHERE NOT t.tgisinternal AND "
            "n.nspname=current_schema() ORDER BY 1,2"
        )
    ).all()
    if not triggers or any(row[2] != "O" for row in triggers):
        raise ValueError("restore_guards_unavailable")
    functions = session.execute(
        text(
            "SELECT p.proname,pg_get_functiondef(p.oid) FROM pg_proc p JOIN "
            "pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=current_schema() "
            "AND p.prokind='f' ORDER BY 1,2"
        )
    ).all()
    roles = session.execute(
        text(
            "SELECT "
            "rolname,rolsuper,rolinherit,rolcreaterole,rolcreatedb,rolcanlogin,rolr"
            "eplication,rolbypassrls FROM pg_roles ORDER BY rolname"
        )
    ).all()
    grants = session.execute(
        text(
            "SELECT grantee,table_name,privilege_type FROM "
            "information_schema.role_table_grants WHERE table_schema=current_schema() "
            "ORDER BY 1,2,3"
        )
    ).all()
    columns = session.execute(
        text(
            "SELECT grantee,table_name,column_name,privilege_type FROM "
            "information_schema.role_column_grants WHERE "
            "table_schema=current_schema() ORDER BY 1,2,3,4"
        )
    ).all()
    memberships = session.execute(
        text(
            "SELECT m.rolname,u.rolname,a.admin_option FROM pg_auth_members a JOIN "
            "pg_roles m ON m.oid=a.roleid JOIN pg_roles u ON u.oid=a.member ORDER BY 1,2"
        )
    ).all()
    originals = reconcile_originals(
        storage,
        session.scalars(select(Document).order_by(Document.id).limit(1001)).all(),
        max_documents=1000,
        work_seconds=work_seconds,
    )
    if originals["result"] != "PASS":
        raise ValueError("restore_originals_unverified")
    if monotonic() - started > work_seconds:
        raise ValueError("restore_work_bound")
    return {
        "profile": PROFILE,
        "schema": EXPECTED_SCHEMA_REVISION,
        "system_identifier": system,
        "tables": tables,
        "database_sha256": checksum(tables),
        "guards_sha256": checksum([list(r) for r in triggers]),
        "functions_sha256": checksum([list(r) for r in functions]),
        "privileges_sha256": checksum(
            [[list(r) for r in group] for group in (roles, grants, columns, memberships)]
        ),
        "original_inventory_sha256": originals["inventory_sha256"],
        "source_count": originals["document_count"],
        "source_bytes": originals["bytes_read"],
        "uncaptured_provenance": provenance,
        "proof_fingerprints_verified": len(proofs),
        "result": "SNAPSHOT ONLY; NO RELEASE AUTHORIZATION",
    }


def compare(expected, restored):
    if expected.get("profile") != PROFILE or restored.get("profile") != PROFILE:
        raise ValueError("restore_unqualified_profile")
    differences = [key for key in expected if expected[key] != restored.get(key)]
    extra = set(restored) - set(expected)
    if differences or extra:
        return {
            "result": "FAIL",
            "reason": "restore_native_identity_or_history_mismatch",
            "different_fields": sorted(set(differences) | extra),
        }
    return {
        "result": "PASS",
        "profile": PROFILE,
        "database_sha256": restored["database_sha256"],
        "source_count": restored["source_count"],
        "uncaptured_provenance_count": len(restored["uncaptured_provenance"]),
        "release_authorization": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected", type=Path, required=True)
    args = parser.parse_args()
    settings = Settings()
    engine = create_database_engine(settings)
    if engine is None:
        raise SystemExit("restore_database_required")
    try:
        with (
            engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection,
            connection.begin(),
            Session(connection) as session,
        ):
            result = compare(
                json.loads(args.expected.read_text()), snapshot(session, build_storage(settings))
            )
        print(json.dumps(result, sort_keys=True))
        if result["result"] != "PASS":
            raise SystemExit(1)
    except SystemExit:
        raise
    except Exception:
        raise SystemExit("restore_validation_unavailable") from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
