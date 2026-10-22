import hashlib
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Protocol
from uuid import UUID


@dataclass(frozen=True)
class StoredObject:
    key: str
    file_size: int
    sha256: str


def document_storage_key(organization_id: UUID, document_id: UUID) -> str:
    return f"{organization_id}/{document_id}/source"


class ObjectStorage(Protocol):
    """An S3 adapter can implement this without changing document metadata."""

    def put(self, key: str, source: BinaryIO, *, max_bytes: int) -> StoredObject: ...

    def open(self, key: str) -> BinaryIO: ...

    def delete(self, key: str) -> None: ...


class LocalObjectStorage:
    """Private development storage. Keys are internal, never original filenames.

    Authorization belongs to the application service that supplies the key.
    This directory must not be shared with untrusted writers or served by HTTP.
    """

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _path(self, key: str) -> Path:
        key_path = PurePosixPath(key)
        if (
            not key
            or key_path.is_absolute()
            or ".." in key_path.parts
            or "\\" in key
            or str(key_path) != key
        ):
            raise ValueError("Invalid storage key")
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root) or path == self.root:
            raise ValueError("Storage key escapes storage root")
        return path

    def put(self, key: str, source: BinaryIO, *, max_bytes: int) -> StoredObject:
        if max_bytes < 1:
            raise ValueError("max_bytes must be positive")
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        checksum = hashlib.sha256()
        size = 0
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as output:
                temp_path = Path(output.name)
                while chunk := source.read(1024 * 1024):
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError("Document exceeds size limit")
                    checksum.update(chunk)
                    output.write(chunk)
            # Hard link publishes atomically and refuses to overwrite an existing object.
            os.link(temp_path, target)
            return StoredObject(key=key, file_size=size, sha256=checksum.hexdigest())
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    def open(self, key: str) -> BinaryIO:
        # Reject special files without blocking on a FIFO. Originals are regular private files.
        descriptor = os.open(self._path(key), os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ValueError("Stored object must be a regular file")
            return os.fdopen(descriptor, "rb")
        except BaseException:
            os.close(descriptor)
            raise

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


def build_storage(settings):
    if settings.storage_backend == "local":
        return LocalObjectStorage(settings.storage_root)
    from app.modules.s3_storage import S3ObjectStorage

    return S3ObjectStorage(settings)
