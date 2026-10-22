"""Private exact-byte upload validation outside the credentialed API process."""

import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import BinaryIO

from fastapi import HTTPException

from app.intelligence.schema import Limits
from app.modules.upload_validation import MIME_TYPES


def validate_file_isolated(
    source: BinaryIO, filename: str, mime: str | None, max_bytes: int, limits: Limits | None = None
):
    canonical = MIME_TYPES.get(Path(filename).suffix.lower())
    if canonical is None or mime != canonical:
        raise HTTPException(415, "Use a PDF, UTF-8 CSV, or XLSX with its matching MIME type")
    source.seek(0, io.SEEK_END)
    size = source.tell()
    if size < 1:
        raise HTTPException(422, "Empty files cannot be uploaded")
    if size > max_bytes:
        raise HTTPException(413, "File exceeds the maximum upload size")
    source.seek(0)
    limits = limits or Limits()
    try:
        with tempfile.TemporaryDirectory(prefix="fla-upload-validation-") as directory:
            path = Path(directory) / "source"
            with path.open("xb") as target:
                os.chmod(path, 0o600)
                total = 0
                while chunk := source.read(65536):
                    total += len(chunk)
                    if total > max_bytes:
                        raise HTTPException(413, "File exceeds the maximum upload size")
                    target.write(chunk)
            if total != size:
                raise HTTPException(415, "Source changed during protected validation")
            payload = json.dumps(
                {
                    "path": str(path),
                    "filename": filename,
                    "mime": mime,
                    "max_bytes": max_bytes,
                    "limits": limits.model_dump(),
                }
            )
            with (Path(directory) / "result").open("w+b") as output:
                process = subprocess.Popen(
                    [sys.executable, "-m", "app.intelligence.validation_worker"],
                    stdin=subprocess.PIPE,
                    stdout=output,
                    stderr=subprocess.DEVNULL,
                    cwd=Path(__file__).resolve().parents[2],
                    env={"PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"},
                )
                try:
                    process.communicate(payload.encode(), timeout=limits.timeout_seconds + 2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    raise HTTPException(408, "Protected validation work budget exceeded") from None
                if process.returncode or output.tell() > 4096:
                    raise HTTPException(415, "File could not be validated within safety limits")
                output.seek(0)
                result = json.loads(output.read(4097))
                if result.get("error") == "parser_confinement_unavailable":
                    raise HTTPException(503, "Protected parsing is unavailable; upload blocked")
                if result.get("status") != 200 or result.get("mime") != canonical:
                    raise HTTPException(415, "File content does not match a safe supported format")
    except (OSError, json.JSONDecodeError):
        raise HTTPException(503, "Protected validation is unavailable; upload blocked") from None
    finally:
        source.seek(0)
    return canonical
