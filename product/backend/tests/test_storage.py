import hashlib
from io import BytesIO
from uuid import uuid4

import pytest

from app.modules.storage import LocalObjectStorage, document_storage_key


def test_store_read_delete_and_integrity(tmp_path):
    storage = LocalObjectStorage(tmp_path)
    key = document_storage_key(uuid4(), uuid4())
    content = b"%PDF-test-contract"
    stored = storage.put(key, BytesIO(content), max_bytes=100)
    assert stored.file_size == len(content)
    assert stored.sha256 == hashlib.sha256(content).hexdigest()
    with storage.open(key) as file:
        assert file.read() == content
    storage.delete(key)
    with pytest.raises(FileNotFoundError):
        storage.open(key)


@pytest.mark.parametrize(
    "key", ["../secret", "/tmp/secret", "a/../../secret", "a\\b", "", ".", "a//b"]
)
def test_rejects_invalid_keys(tmp_path, key):
    storage = LocalObjectStorage(tmp_path)
    with pytest.raises(ValueError):
        storage.put(key, BytesIO(b"content"), max_bytes=10)


def test_size_limit_cleans_temporary_files(tmp_path):
    storage = LocalObjectStorage(tmp_path)
    with pytest.raises(ValueError, match="size limit"):
        storage.put("org/doc/source", BytesIO(b"123456"), max_bytes=5)
    assert not list(tmp_path.rglob("source"))
    assert not list(tmp_path.rglob("tmp*"))


def test_cannot_overwrite_existing_document(tmp_path):
    storage = LocalObjectStorage(tmp_path)
    storage.put("org/doc/source", BytesIO(b"original"), max_bytes=100)
    with pytest.raises(FileExistsError):
        storage.put("org/doc/source", BytesIO(b"replacement"), max_bytes=100)
    with storage.open("org/doc/source") as file:
        assert file.read() == b"original"


def test_symlink_cannot_escape_root(tmp_path):
    storage = LocalObjectStorage(tmp_path / "root")
    (tmp_path / "root" / "escape").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="escapes"):
        storage.open("escape/secret")
