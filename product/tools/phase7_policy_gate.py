"""Phase 7 preserves the approved policy and checkpoint financial domain exactly."""

import hashlib
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    pins = json.loads((root / "tools/phase7-preserved-files.json").read_text())
    failures = [
        name
        for name, expected in pins["sha256"].items()
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected
    ]
    if failures:
        raise SystemExit("Protected Phase 7 inputs changed: " + ", ".join(failures))
    print(json.dumps({"policy_preservation": "PASS", "files": len(pins["sha256"])}))


if __name__ == "__main__":
    main()
