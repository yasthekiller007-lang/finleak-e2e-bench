import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.intelligence.confinement import available, healthcheck
from app.modules.protected_validation import validate_file_isolated
from tests.parser_environment import require_confinement
from tests.test_documents import CSV, PDF, xlsx


@pytest.mark.parametrize(
    "action",
    [
        "Path(secret).read_bytes()",
        "Path(sibling).read_bytes()",
        "Path(source).open('r+b')",
        "os.truncate(source, 0)",
        "Path(sibling).write_text('changed')",
        "socket.socket()",
        "socket.socket(socket.AF_UNIX)",
        "os.execv('/bin/true', ['true'])",
        "os.fork()",
        "os.chmod(source, 0o777)",
        "Path('/proc/self/environ').read_bytes()",
        "os.symlink(source, sibling + '.link')",
    ],
)
def test_actual_child_denies_source_mutation_other_data_network_execution_and_processes(
    tmp_path, action
):
    require_confinement()
    source, sibling, secret = (tmp_path / name for name in ("source", "sibling", "secret"))
    source.write_bytes(b"field,value\nsupplier,Synthetic")
    sibling.write_bytes(b"other source")
    secret.write_bytes(b"synthetic confidential canary")
    code = """
import json, os, socket, sys
from pathlib import Path
from app.intelligence.confinement import confine
source, sibling, secret, action = sys.argv[1:]
confine(source)
assert Path(source).read_bytes() == b"field,value\\nsupplier,Synthetic"
try:
    eval(action)
except PermissionError:
    print(json.dumps({"denied": True}))
else:
    raise SystemExit(42)
"""
    process = subprocess.run(
        [sys.executable, "-c", code, str(source), str(sibling), str(secret), action],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        env={"PATH": os.defpath, "LANG": "C.UTF-8"},
        timeout=5,
    )
    assert process.returncode == 0, process.stderr.decode()
    assert json.loads(process.stdout) == {"denied": True}
    assert source.read_bytes() == b"field,value\nsupplier,Synthetic"
    assert sibling.read_bytes() == b"other source"
    assert secret.read_bytes() == b"synthetic confidential canary"
    assert not Path(str(sibling) + ".link").exists()


def test_real_readiness_child_installs_both_profiles():
    require_confinement()
    healthcheck()


@pytest.mark.parametrize(
    "filename,mime,data",
    [
        ("original.csv", "text/csv", CSV),
        ("original.pdf", "application/pdf", PDF),
        (
            "original.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            xlsx(),
        ),
    ],
)
def test_actual_upload_child_accepts_safe_formats_and_preserves_exact_bytes(filename, mime, data):
    require_confinement()
    source = io.BytesIO(data)
    assert validate_file_isolated(source, filename, mime, 1024 * 1024) == mime
    assert source.tell() == 0 and source.read() == data


def test_unavailable_kernel_blocks_actual_upload_without_unprotected_fallback():
    if available():
        # The available-kernel path is exercised by the mandatory child tests above.
        return
    source = io.BytesIO(CSV)
    with pytest.raises(HTTPException) as error:
        validate_file_isolated(source, "original.csv", "text/csv", 1024)
    assert error.value.status_code == 503
    assert source.read() == CSV
