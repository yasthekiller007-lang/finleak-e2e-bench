"""Synthetic native PostgreSQL backup/restore drill; never a deployment command."""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from time import monotonic, sleep
from uuid import UUID, uuid4

from alembic import command as alembic
from alembic.config import Config
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.db.models import Document
from app.modules.storage import LocalObjectStorage
from app.operations.restore_validation import compare, snapshot
from app.operations.roles import Roles, bootstrap, grant_runtime
from app.recovery.models import RecoveryPublication

IMAGE = "postgres:17.11-bookworm"


def docker(*args, timeout=60, input=None):
    return (
        subprocess.check_output(
            ["docker", *args], input=input, stderr=subprocess.DEVNULL, timeout=timeout
        )
        .decode()
        .strip()
    )


def url(name):
    port = docker("port", name, "5432/tcp").splitlines()[0].rsplit(":", 1)[1]
    return "postgresql+psycopg://postgres@127.0.0.1:" + port + "/postgres"


def wait(name):
    deadline = monotonic() + 60
    while True:
        try:
            engine = create_engine(url(name), hide_parameters=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            engine.dispose()
            return
        except Exception:
            if monotonic() > deadline:
                raise RuntimeError("Synthetic restore startup unavailable") from None
            sleep(0.2)


def read(engine, store):
    with (
        engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn,
        conn.begin(),
        Session(conn) as session,
    ):
        return snapshot(session, store)


def seed(engine, directory):
    # Reuse explicit domain API fixtures, not hand-written monetary SQL or new authority.
    # Fixtures/identity injection are outside production images and restricted to test.
    from tests.recovery_fixtures import act, instrument, ready, realization, setup
    from tests.test_documents import api as fixture

    with Session(engine) as session:
        manager = fixture.__wrapped__(session, directory)
        api = next(manager)
        try:
            f = setup(api)
            p, r = ready(api, f)
            i, v = instrument(api, f, "12000")
            receipt = act(api, f, realization(api, f, p, r, i, v, "11000"))
            session.commit()
            # Deterministic crash window: real financial commit succeeds, publication
            # capture fails afterward. Never delete an immutable publication to simulate it.
            from unittest.mock import patch

            from app.proof.budget import ProofError
            from tests.recovery_fixtures import current, ok, post, prepare

            # The interrupted recovery is a distinct settled receipt. A second
            # allocation of the first receipt cannot invent a different raw cash fact.
            crash_instrument, crash_review = instrument(api, f, "1000")
            proposal = prepare(
                api,
                f,
                realization(api, f, p, r, crash_instrument, crash_review, "1000"),
            )
            head = current(api, f["case"])["head_id"]
            with patch(
                "app.recovery.publication.capture",
                side_effect=ProofError(
                    "recovery_known_at_unavailable",
                    "Synthetic post-commit interruption",
                    503,
                ),
            ):
                result = ok(
                    post(
                        api,
                        f"/proposals/{proposal['id']}/decision",
                        {
                            "expected_head": head,
                            "decision": "APPROVE",
                            "reason": "Synthetic exact reviewed economic recovery",
                        },
                    )
                )
                assert result["known_at_status"] == "UNRESOLVED_COMMIT_PROVENANCE"
            session.commit()
            assert result["id"] != receipt["id"]
            assert (
                session.scalar(
                    select(RecoveryPublication).where(
                        RecoveryPublication.record_id == UUID(result["id"])
                    )
                )
                is None
            )
            assert session.scalar(
                select(RecoveryPublication).where(
                    RecoveryPublication.record_id == UUID(receipt["id"])
                )
            )
        finally:
            session.rollback()
            manager.close()


def main():
    if os.environ.get("FLA_ENVIRONMENT") != "test" or not os.environ.get("CI"):
        raise SystemExit("Synthetic restore drill is CI-only")
    started = monotonic()
    names = ["phase7-restore-" + uuid4().hex[:16] for _ in range(3)]
    donor, restored, logical = names
    volume = "phase7-backup-" + uuid4().hex[:16]
    try:
        docker("volume", "create", volume)
        docker(
            "run",
            "-d",
            "--name",
            donor,
            "-e",
            "POSTGRES_HOST_AUTH_METHOD=trust",
            "-p",
            "127.0.0.1::5432",
            "-v",
            volume + ":/backup",
            IMAGE,
            "-c",
            "track_commit_timestamp=on",
        )
        wait(donor)
        os.environ["TEST_DATABASE_URL"] = os.environ["FLA_DATABASE_URL"] = url(donor)
        from app.core.config import get_settings

        get_settings.cache_clear()
        alembic.upgrade(Config("alembic.ini"), "head")
        engine = create_engine(url(donor), hide_parameters=True)
        with engine.begin() as conn:
            bootstrap(conn, Roles())
            grant_runtime(conn, Roles())
        with tempfile.TemporaryDirectory(prefix="fla-restore-") as temp:
            originals = Path(temp) / "originals"
            originals.mkdir()
            seed(engine, originals)
            before = read(engine, LocalObjectStorage(originals))
            assert before["uncaptured_provenance"] and before["proof_fingerprints_verified"]
            assert before["tables"]["financial_audit"]["count"] > 0
            assert before["tables"]["pilot_source_scans"]["count"] > 0
            docker(
                "exec",
                donor,
                "sh",
                "-c",
                "mkdir -p /backup/native && chown postgres:postgres /backup/native",
            )
            docker(
                "exec",
                "--user",
                "postgres",
                donor,
                "pg_basebackup",
                "-D",
                "/backup/native",
                "-X",
                "stream",
                "--checkpoint=fast",
                "--manifest-checksums=SHA256",
                timeout=120,
            )
            docker(
                "exec",
                "--user",
                "postgres",
                donor,
                "pg_verifybackup",
                "/backup/native",
                timeout=120,
            )
            # Boot a separate cluster from the verified physical copy; original untouched.
            docker(
                "run",
                "-d",
                "--name",
                restored,
                "-e",
                "PGDATA=/backup/native",
                "-p",
                "127.0.0.1::5432",
                "-v",
                volume + ":/backup",
                IMAGE,
                "-c",
                "track_commit_timestamp=on",
            )
            wait(restored)
            copied = Path(temp) / "restored-originals"
            shutil.copytree(originals, copied)
            restored_engine = create_engine(url(restored), hide_parameters=True)
            after = read(restored_engine, LocalObjectStorage(copied))
            assert compare(before, after)["result"] == "PASS"
            # Byte faults stay blocked. Do not recalculate proof/evaluation/recovery.
            with Session(restored_engine) as session:
                doc = session.scalar(select(Document))
                path = copied / doc.storage_key
            original = path.read_bytes()
            path.write_bytes(original + b"tampered")
            try:
                read(restored_engine, LocalObjectStorage(copied))
                raise AssertionError("Corrupt original incorrectly qualified")
            except ValueError as exc:
                assert str(exc) == "restore_originals_unverified"
            path.write_bytes(original)
            # A logical restore really creates a new cluster/XID history. Its new
            # transaction timestamps never count as historical financial knowledge.
            dump = docker(
                "exec",
                donor,
                "pg_dump",
                "-U",
                "postgres",
                "--clean",
                "--if-exists",
                "--no-owner",
                "--no-privileges",
            )
            docker(
                "run",
                "-d",
                "--name",
                logical,
                "-e",
                "POSTGRES_HOST_AUTH_METHOD=trust",
                "-p",
                "127.0.0.1::5432",
                IMAGE,
                "-c",
                "track_commit_timestamp=on",
            )
            wait(logical)
            docker(
                "exec",
                "-i",
                logical,
                "psql",
                "-U",
                "postgres",
                "-v",
                "ON_ERROR_STOP=1",
                input=dump.encode(),
                timeout=120,
            )
            logical_engine = create_engine(url(logical), hide_parameters=True)
            logical_snapshot = read(logical_engine, LocalObjectStorage(copied))
            assert compare(before, logical_snapshot)["result"] == "FAIL"
            assert before["system_identifier"] != logical_snapshot["system_identifier"]
            assert before["uncaptured_provenance"] != logical_snapshot["uncaptured_provenance"]
            for item in (engine, restored_engine, logical_engine):
                item.dispose()
            print(
                json.dumps(
                    {
                        "kind": "synthetic-native-postgresql-restore",
                        "release_sha": os.environ.get("RELEASE_SHA"),
                        "postgres": "17.11",
                        "result": "PASS",
                        "native_manifest_verified": True,
                        "comparison": compare(before, after),
                        "source_bytes": before["source_bytes"],
                        "snapshot_sha256": hashlib.sha256(
                            json.dumps(before, sort_keys=True).encode()
                        ).hexdigest(),
                        "duration_ms": round((monotonic() - started) * 1000),
                        "cases": [
                            "native-schema-roles-guards-audit-history",
                            "exact-financial-proof-recovery-digests",
                            "captured-and-uncaptured-original-K",
                            "restored-original-byte-verification",
                            "source-tamper-blocked",
                            "actual-logical-cluster-new-XID-rejected",
                        ],
                        "managed_PITR_qualified": False,
                        "RPO_RTO_qualified": False,
                        "deployment_authorization": False,
                    },
                    sort_keys=True,
                )
            )
    finally:
        for name in names:
            subprocess.run(
                ["docker", "rm", "-f", name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=20,
                check=False,
            )
        subprocess.run(
            ["docker", "volume", "rm", volume],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
            check=False,
        )


if __name__ == "__main__":
    main()
