from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import OrganizationAccess
from app.db.models import Document
from app.domain.types import DocumentType, MembershipRole
from app.modules.scanner import ScanVerdict
from app.modules.source_preservation import PreservedObjectStorage
from app.modules.storage import LocalObjectStorage, document_storage_key
from app.operations import source_service
from app.operations.source_gate import ReleasedObjectStorage, SourceGateError, gate
from app.operations.source_models import PilotSourceRelease, PilotSourceRequest, PilotSourceScan
from app.proof.schema import OperationalLimits
from tests.recovery_fixtures import recovery_engine as recovery_engine
from tests.test_pilot_access import roster

pytestmark = pytest.mark.integration


@pytest.fixture
def source_fixture(recovery_engine, tmp_path):
    import io

    raw = LocalObjectStorage(tmp_path)
    with Session(recovery_engine) as session:
        org, users = roster(session)
        access = OrganizationAccess(org.id, users[0].id, MembershipRole.OWNER)
        docid = uuid4()
        stored = raw.put(
            document_storage_key(org.id, docid),
            io.BytesIO(b"field,value\nreference,SYNTHETIC\n"),
            max_bytes=100,
        )
        doc = Document(
            id=docid,
            organization_id=org.id,
            original_filename="synthetic.csv",
            mime_type="text/csv",
            file_size=stored.file_size,
            sha256=stored.sha256,
            storage_key=stored.key,
            document_type=DocumentType.INVOICE,
            processing_status="pending",
        )
        session.add(doc)
        session.commit()

        class CleanScanner:
            def scan(self, *args, **kwargs):
                return ScanVerdict("CLEAN", version="clamav/1.4.6;database/28000")

        scanned = source_service.scan(
            session,
            raw,
            CleanScanner(),
            access,
            docid,
            uuid4(),
            "Explicit synthetic scan",
            OperationalLimits(),
        )
        scan_id = scanned.id
        session.commit()
    return recovery_engine, raw, access, docid, scan_id, stored.key


@pytest.mark.parametrize("same_key", [True, False])
def test_simultaneous_releases_have_one_semantic_identity_and_pinned_requests(
    source_fixture, same_key
):
    engine, raw, access, doc, scan_id, _ = source_fixture
    barrier = Barrier(2)
    keys = [uuid4(), uuid4()]
    if same_key:
        keys[1] = keys[0]

    def act(key):
        with Session(engine) as session:
            barrier.wait(5)
            result = source_service.release(
                session,
                raw,
                access,
                doc,
                scan_id,
                key,
                "Controlled concurrent release",
                OperationalLimits(),
            )
            identity = result.id
            session.commit()
            return identity

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(act, keys))
    assert results[0] == results[1]
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(PilotSourceRelease)) == 1
        assert session.scalar(select(func.count()).select_from(PilotSourceRequest)) == (
            2 if same_key else 3
        )


def test_concurrent_failed_rescan_cannot_revoke_a_read_midstream(source_fixture):
    engine, raw, access, doc, scan_id, key = source_fixture
    with Session(engine) as session:
        source_service.release(
            session,
            raw,
            access,
            doc,
            scan_id,
            uuid4(),
            "Initial controlled release",
            OperationalLimits(),
        )
        session.commit()
    storage = ReleasedObjectStorage(PreservedObjectStorage(raw, engine), engine)
    reading, attempting, finish, scanned = Event(), Event(), Event(), Event()

    def read():
        with storage.open(key) as source:
            reading.set()
            assert finish.wait(5)
            assert source.read() == b"field,value\nreference,SYNTHETIC\n"

    def rescan():
        assert reading.wait(5)

        class UnavailableScanner:
            def scan(self, *args, **kwargs):
                return ScanVerdict("UNAVAILABLE")

        with Session(engine) as session:
            attempting.set()
            source_service.scan(
                session,
                raw,
                UnavailableScanner(),
                access,
                doc,
                uuid4(),
                "Explicit failed rescan",
                OperationalLimits(),
            )
            session.commit()
        scanned.set()

    with ThreadPoolExecutor(max_workers=2) as pool:
        current = pool.submit(read)
        revision = pool.submit(rescan)
        try:
            assert attempting.wait(5)
            assert not scanned.wait(0.1)
        finally:
            finish.set()
        current.result(10)
        revision.result(10)
    with pytest.raises(SourceGateError):
        with storage.open(key):
            pytest.fail("A failed later scan silently retained normal availability")
    with Session(engine) as session:
        assert gate(session, session.get(Document, doc))["state"] == "UNAVAILABLE"
        assert session.scalar(select(func.count()).select_from(PilotSourceRelease)) == 1
        assert session.scalar(select(func.count()).select_from(PilotSourceScan)) == 2
