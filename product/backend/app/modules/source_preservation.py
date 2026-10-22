"""Operational preservation of registered originals, independent of financial status."""

from threading import Lock

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import Document
from app.modules.s3_storage import StorageFailure, original_key


def lock_original(session, key):
    """Serialize registration and compensating removal across application workers."""
    session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 7001))"), {"key": key}
    )


class PreservedObjectStorage:
    """Only a successful new publication may be compensated by its issuing worker.

    A fresh database transaction fences compensation against registration. Uncertain
    database outcomes preserve the bytes. There is no ordinary source deletion API.
    Provider administrators and privileged restore tools remain separate IAM concerns.
    """

    def __init__(self, raw, engine):
        self._raw, self._engine = raw, engine
        self._pending = set()
        self._lock = Lock()

    @property
    def root(self):
        # Development fixtures may simulate privileged filesystem corruption.
        return self._raw.root

    def put(self, key, source, *, max_bytes):
        original_key(key)
        result = self._raw.put(key, source, max_bytes=max_bytes)
        with self._lock:
            self._pending.add(key)
        return result

    def open(self, key):
        return self._raw.open(key)

    def registered(self, key):
        with self._lock:
            self._pending.discard(key)

    def delete(self, key):
        original_key(key)
        with self._lock:
            if key not in self._pending:
                raise StorageFailure("source_delete_forbidden")
            # Consume this single compensation capability, including on failure.
            # Unknown outcomes require operator reconciliation, never blind retry.
            self._pending.remove(key)
        if self._engine is None:
            raise StorageFailure("source_cleanup_pending")
        try:
            with Session(self._engine) as session, session.begin():
                lock_original(session, key)
                if session.scalar(select(Document.id).where(Document.storage_key == key)):
                    raise StorageFailure("source_registered_preserved")
                self._raw.delete(key)
        except StorageFailure:
            raise
        except Exception:
            raise StorageFailure("source_cleanup_pending") from None

    def healthcheck(self):
        probe = getattr(self._raw, "healthcheck", None)
        if probe is not None:
            probe()
