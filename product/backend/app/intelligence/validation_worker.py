"""Bounded child for untrusted upload structure. No extraction/financial workflow."""

import json
import logging
import resource
import sys

from fastapi import HTTPException

from app.intelligence.confinement import ConfinementUnavailable, confine
from app.intelligence.schema import Limits
from app.modules.upload_validation import validate_file


def main():
    request = json.loads(sys.stdin.read(4096))
    limits = Limits.model_validate(request["limits"])
    resource.setrlimit(resource.RLIMIT_AS, (limits.memory_mb * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (limits.timeout_seconds, limits.timeout_seconds + 1))
    resource.setrlimit(resource.RLIMIT_FSIZE, (4096,) * 2)
    logging.disable(logging.CRITICAL)
    try:
        confine(request["path"])
        with open(request["path"], "rb") as source:
            mime = validate_file(
                source, request["filename"], request["mime"], request["max_bytes"], limits
            )
        print(json.dumps({"status": 200, "mime": mime}))
    except ConfinementUnavailable:
        print(json.dumps({"error": "parser_confinement_unavailable"}))
    except HTTPException as error:
        print(json.dumps({"status": error.status_code}))
    except Exception:
        print(json.dumps({"status": 415}))


if __name__ == "__main__":
    main()
