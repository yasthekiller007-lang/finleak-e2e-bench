"""Disposable parser process with CPU/address-space limits and no app credentials."""

import json
import logging
import resource
import sys
from pathlib import Path

from app.intelligence.confinement import ConfinementUnavailable, confine
from app.intelligence.extraction import extract
from app.intelligence.parsing import parse
from app.intelligence.schema import Limits, ProcessingError


def main():
    request = json.loads(sys.stdin.read(4096))
    limits = Limits.model_validate(request["limits"])
    resource.setrlimit(resource.RLIMIT_AS, (limits.memory_mb * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (limits.timeout_seconds, limits.timeout_seconds + 1))
    output_bound = limits.max_characters * 8 + limits.max_fields * 2048
    resource.setrlimit(resource.RLIMIT_FSIZE, (output_bound,) * 2)
    logging.disable(logging.CRITICAL)
    try:
        confine(request["path"])
        result = extract(
            parse(Path(request["path"]), request["mime_type"], limits),
            request["document_type"],
            limits,
        )
        print(result.model_dump_json())
    except ConfinementUnavailable:
        print(json.dumps({"error": "parser_confinement_unavailable"}))
    except ProcessingError as exc:
        print(json.dumps({"error": exc.code}))
    except MemoryError:
        print(json.dumps({"error": "processing_limit"}))
    except Exception:
        print(json.dumps({"error": "schema_validation"}))


if __name__ == "__main__":
    main()
