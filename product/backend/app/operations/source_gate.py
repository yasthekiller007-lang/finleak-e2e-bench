"""Operational availability overlay. Historical financial/proof/recovery truth is untouched."""

from contextlib import contextmanager

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import Document
from app.operations.source_models import PilotSourceRelease, PilotSourceScan


class SourceGateError(OSError):
    def __init__(self, code="source_quarantined", status=409):
        self.code, self.status = code, status
        super().__init__(code)


def latest_scan(session, document):
    return session.scalar(
        select(PilotSourceScan)
        .where(
            PilotSourceScan.organization_id == document.organization_id,
            PilotSourceScan.document_id == document.id,
        )
        .order_by(PilotSourceScan.sequence.desc())
        .limit(1)
    )


def gate(session, document):
    scan = latest_scan(session, document)
    if scan is None:
        return {"state": "UNSCANNED", "scan_id": None}
    if scan.sha256 != document.sha256 or scan.file_size != document.file_size:
        return {"state": "MISMATCH", "scan_id": str(scan.id)}
    if scan.verdict != "CLEAN":
        return {"state": scan.verdict, "scan_id": str(scan.id)}
    released = session.scalar(
        select(PilotSourceRelease.id).where(
            PilotSourceRelease.organization_id == document.organization_id,
            PilotSourceRelease.document_id == document.id,
            PilotSourceRelease.scan_id == scan.id,
        )
    )
    return {"state": "RELEASED" if released else "CLEAN_AWAITING_RELEASE", "scan_id": str(scan.id)}


def require_released(session, document):
    if gate(session, document)["state"] != "RELEASED":
        raise SourceGateError()


class ReleasedObjectStorage:
    def __init__(self, preserved, engine):
        self._preserved, self._engine = preserved, engine

    @property
    def root(self):
        return self._preserved.root

    def put(self, *args, **kwargs):
        return self._preserved.put(*args, **kwargs)

    def registered(self, key):
        return self._preserved.registered(key)

    def delete(self, key):
        return self._preserved.delete(key)

    def healthcheck(self):
        return self._preserved.healthcheck()

    @contextmanager
    def open(self, key):
        if self._engine is None:
            raise SourceGateError("source_gate_unavailable", 503)
        with Session(self._engine, join_transaction_mode="create_savepoint") as session:
            # The read fence is held through the stream. Scan/release writers take this
            # same Document fence, so a concurrent new verdict cannot revoke mid-read.
            try:
                document = session.scalar(
                    select(Document).where(Document.storage_key == key).with_for_update(read=True)
                )
                if document is None:
                    raise SourceGateError()
                require_released(session, document)
            except SQLAlchemyError:
                raise SourceGateError("source_gate_unavailable", 503) from None
            with self._preserved.open(key) as original:
                yield original
