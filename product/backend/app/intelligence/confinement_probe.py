"""A harmless child exercises the installed confinement profile for readiness."""

import json
import socket
from pathlib import Path

from app.intelligence.confinement import ConfinementUnavailable, confine


def main():
    source = Path(__file__).resolve()
    try:
        confine(source)
        assert source.read_bytes()
        denied = 0
        try:
            socket.socket()
        except PermissionError:
            denied += 1
        try:
            Path("/etc/passwd").read_bytes()
        except PermissionError:
            denied += 1
        try:
            source.open("r+b")
        except PermissionError:
            denied += 1
        assert denied == 3
        print(json.dumps({"status": "protected", "denied": denied}))
    except (ConfinementUnavailable, AssertionError, OSError):
        print(json.dumps({"status": "unavailable"}))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
