import hashlib
import io
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from app.db.models import Document, Organization
from app.domain.types import DocumentType, ProcessingStatus
from app.modules.s3_storage import StorageFailure
from app.modules.source_preservation import PreservedObjectStorage, lock_original
from app.modules.storage import LocalObjectStorage, document_storage_key
from app.operations.source_inventory import reconcile_originals


def original(raw, content=b"private synthetic evidence"):
    organization_id, document_id = uuid4(), uuid4()
    key = document_storage_key(organization_id, document_id)
    stored = raw.put(key, io.BytesIO(content), max_bytes=1024)
    return SimpleNamespace(
        id=document_id,
        organization_id=organization_id,
        storage_key=key,
        file_size=stored.file_size,
        sha256=stored.sha256,
    )


class DatabaseOutcome:
    def __init__(self, persisted=False, outage=False):
        self.persisted, self.outage = persisted, outage
        self.calls = []

    def __call__(self, engine):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def begin(self):
        return self

    def execute(self, statement, parameters):
        self.calls.append((str(statement), parameters))
        if self.outage:
            raise OSError("private credential/detail")

    def scalar(self, statement):
        self.calls.append(str(statement))
        return uuid4() if self.persisted else None


@pytest.mark.parametrize("persisted,outage", [(True, False), (False, True), (False, False)])
def test_compensation_checks_fresh_registration_under_database_fence(
    tmp_path, monkeypatch, persisted, outage
):
    outcome = DatabaseOutcome(persisted, outage)
    monkeypatch.setattr("app.modules.source_preservation.Session", outcome)
    raw = LocalObjectStorage(tmp_path)
    storage = PreservedObjectStorage(raw, object())
    key = document_storage_key(uuid4(), uuid4())
    storage.put(key, io.BytesIO(b"whole original"), max_bytes=100)
    if persisted or outage:
        with pytest.raises(StorageFailure) as failure:
            storage.delete(key)
        assert failure.value.code == (
            "source_registered_preserved" if persisted else "source_cleanup_pending"
        )
        assert "private" not in str(failure.value)
        assert raw.open(key).read() == b"whole original"
    else:
        storage.delete(key)
        with pytest.raises(FileNotFoundError):
            raw.open(key)
    assert "pg_advisory_xact_lock" in outcome.calls[0][0]
    with pytest.raises(StorageFailure, match="source_delete_forbidden"):
        storage.delete(key)


def test_ordinary_deletion_or_other_worker_cannot_compensate_original(tmp_path):
    raw = LocalObjectStorage(tmp_path)
    storage = PreservedObjectStorage(raw, None)
    document = original(raw)
    with pytest.raises(StorageFailure, match="source_delete_forbidden"):
        storage.delete(document.storage_key)
    assert raw.open(document.storage_key).read() == b"private synthetic evidence"


def test_successful_registration_destroys_compensation_capability(tmp_path):
    raw = LocalObjectStorage(tmp_path)
    storage = PreservedObjectStorage(raw, None)
    key = document_storage_key(uuid4(), uuid4())
    storage.put(key, io.BytesIO(b"original"), max_bytes=100)
    storage.registered(key)
    with pytest.raises(StorageFailure, match="source_delete_forbidden"):
        storage.delete(key)
    assert raw.open(key).read() == b"original"


def test_failed_new_upload_without_database_preserves_explicit_orphan(tmp_path):
    storage = PreservedObjectStorage(LocalObjectStorage(tmp_path), None)
    key = document_storage_key(uuid4(), uuid4())
    storage.put(key, io.BytesIO(b"original"), max_bytes=100)
    with pytest.raises(StorageFailure, match="source_cleanup_pending"):
        storage.delete(key)
    assert storage.open(key).read() == b"original"


def test_read_only_inventory_hashes_actual_bytes_and_detects_restore_damage(tmp_path):
    raw = LocalObjectStorage(tmp_path)
    documents = [original(raw, bytes([i]) * 10) for i in range(3)]
    before = reconcile_originals(raw, documents)
    assert before["result"] == "PASS" and before["bytes_read"] == 30
    assert len(before["inventory_sha256"]) == 64
    assert before == reconcile_originals(raw, documents)
    raw._path(documents[1].storage_key).write_bytes(b"corrupt")
    raw.delete(documents[2].storage_key)  # privileged synthetic restore failure
    after = reconcile_originals(raw, documents)
    assert after["result"] == "FAIL"
    assert [r["status"] for r in after["items"]] == [
        "AVAILABLE_VERIFIED",
        "MISMATCH",
        "UNAVAILABLE",
    ]
    assert after["inventory_sha256"] != before["inventory_sha256"]
    assert documents[1].sha256 == hashlib.sha256(bytes([1]) * 10).hexdigest()


def test_bounded_inventory_never_labels_a_partial_inventory_successful(tmp_path):
    raw = LocalObjectStorage(tmp_path)
    documents = [original(raw), original(raw, b"second")]
    result = reconcile_originals(raw, documents, max_documents=1)
    assert result == {"result": "INCOMPLETE", "reason": "inventory_document_limit", "items": []}
    result = reconcile_originals(raw, documents, source_bytes=2)
    assert result["result"] == "INCOMPLETE" and result["reason"] == "proof_resource_limit"
    assert result["items"] == []


@pytest.mark.parametrize(
    "bounds", [{"max_documents": 0}, {"source_bytes": 0}, {"work_seconds": 26}]
)
def test_inventory_cannot_remove_operation_bounds(tmp_path, bounds):
    with pytest.raises(ValueError):
        reconcile_originals(LocalObjectStorage(tmp_path), [], **bounds)


@pytest.mark.integration
@pytest.mark.parametrize("commit_registration", [True, False])
def test_real_postgresql_compensation_waits_for_registration_outcome(tmp_path, commit_registration):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set isolated TEST_DATABASE_URL")
    engine = create_engine(url, connect_args={"options": "-c statement_timeout=5000"})
    organization_id, document_id = uuid4(), uuid4()
    raw = LocalObjectStorage(tmp_path)
    storage = PreservedObjectStorage(raw, engine)
    key = document_storage_key(organization_id, document_id)
    receipt = storage.put(key, io.BytesIO(b"unmodified original"), max_bytes=100)
    locked, attempting = Event(), Event()
    with Session(engine) as session, session.begin():
        session.add(Organization(id=organization_id, name="Synthetic preservation test"))

    def register():
        with Session(engine) as session:
            lock_original(session, key)
            session.add(
                Document(
                    id=document_id,
                    organization_id=organization_id,
                    original_filename="synthetic.csv",
                    mime_type="text/csv",
                    file_size=receipt.file_size,
                    storage_key=key,
                    sha256=receipt.sha256,
                    document_type=DocumentType.OTHER,
                    processing_status=ProcessingStatus.PENDING,
                )
            )
            session.flush()
            locked.set()
            assert attempting.wait(5)
            session.commit() if commit_registration else session.rollback()

    def compensate():
        assert locked.wait(5)
        attempting.set()
        try:
            storage.delete(key)
            return "removed"
        except StorageFailure as error:
            return error.code

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            registration = pool.submit(register)
            removal = pool.submit(compensate)
            registration.result(timeout=10)
            result = removal.result(timeout=10)
        assert result == ("source_registered_preserved" if commit_registration else "removed")
        assert raw._path(key).exists() is commit_registration
        if commit_registration:
            assert raw.open(key).read() == b"unmodified original"
        with Session(engine) as session:
            assert (session.get(Document, document_id) is not None) is commit_registration
    finally:
        with Session(engine) as session, session.begin():
            session.execute(delete(Document).where(Document.id == document_id))
            session.execute(delete(Organization).where(Organization.id == organization_id))
        engine.dispose()
