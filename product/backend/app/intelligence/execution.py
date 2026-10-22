"""Simple synchronous execution adapter; a future queue can call the same service."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from pydantic import ValidationError

from app.intelligence.schema import ExtractionResult, Limits, ProcessingError


def execute(storage, document, limits: Limits, max_upload_bytes: int) -> ExtractionResult:
    try:
        with tempfile.TemporaryDirectory(prefix="fla-extraction-") as directory:
            path = Path(directory) / "source"
            checksum = hashlib.sha256()
            size = 0
            with storage.open(document.storage_key) as source, path.open("wb") as output:
                os.chmod(path, 0o600)
                while chunk := source.read(65536):
                    size += len(chunk)
                    if size > max_upload_bytes:
                        raise ProcessingError("processing_limit")
                    checksum.update(chunk)
                    output.write(chunk)
            if checksum.hexdigest() != document.sha256 or size != document.file_size:
                raise ProcessingError("content_integrity")
            payload = json.dumps(
                {
                    "path": str(path),
                    "mime_type": document.mime_type,
                    "document_type": document.document_type.value,
                    "limits": limits.model_dump(),
                }
            )
            # Output goes to private files: communicate() must not buffer unbounded output.
            with (Path(directory) / "result").open("w+b") as result_file:
                process = subprocess.Popen(
                    [sys.executable, "-m", "app.intelligence.worker"],
                    stdin=subprocess.PIPE,
                    stdout=result_file,
                    stderr=subprocess.DEVNULL,
                    cwd=Path(__file__).resolve().parents[2],
                    env={"PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"},
                )
                try:
                    process.communicate(payload.encode(), timeout=limits.timeout_seconds + 2)
                except subprocess.TimeoutExpired as exc:
                    process.kill()
                    process.wait()
                    raise ProcessingError("processing_timeout") from exc
                if process.returncode:
                    raise ProcessingError(
                        "processing_limit" if process.returncode < 0 else "schema_validation"
                    )
                # Provenance duplicates selected raw text, so permit bounded expansion.
                bound = limits.max_characters * 8 + limits.max_fields * 2048
                if result_file.tell() > bound:
                    raise ProcessingError("processing_limit")
                result_file.seek(0)
                result = json.loads(result_file.read(bound + 1))
                if "error" in result:
                    raise ProcessingError(result["error"])
                return ExtractionResult.model_validate(result)
    except FileNotFoundError as exc:
        raise ProcessingError("content_unavailable") from exc
    except (ValidationError, json.JSONDecodeError) as exc:
        raise ProcessingError("schema_validation") from exc
