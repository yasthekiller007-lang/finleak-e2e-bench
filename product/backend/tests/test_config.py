from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import REPOSITORY_ROOT, Settings


def test_relative_storage_root_is_anchored_to_repository():
    settings = Settings(_env_file=None, database_url=None, storage_root=Path(".local/documents"))
    assert settings.storage_root == REPOSITORY_ROOT / ".local" / "documents"


def test_driver_errors_do_not_disclose_connection_inputs():
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, database_url="postgresql://test@localhost/test")
    assert "Use the installed synchronous driver" in str(error.value)
    assert "test@localhost" not in str(error.value)
