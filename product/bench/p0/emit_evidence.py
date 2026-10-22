"""Small, finite, secret-free execution receipts in Actions logs; no billed artifacts."""

import base64
import hashlib
import json
from pathlib import Path

from runtime import validate_result_diagnostic


def emit(directory):
    directory.mkdir(parents=True, exist_ok=True)
    if not (directory / "result.json").is_file():
        (directory / "result.json").write_text(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "e2e_executed": False,
                    "reason": "Bootstrap or preconditions did not reach the scenario",
                    "migration_0010": "NOT VERIFIED",
                    "phase7_qualified": False,
                }
            )
            + "\n"
        )
    manifest = []
    for name in ("result.json", "browser.json", "witness.json", "checks.json"):
        path = directory / name
        if not path.is_file():
            continue
        raw = path.read_bytes()
        if len(raw) > 32768:
            raise SystemExit("Evidence exceeds its safe size bound")
        value = json.loads(raw)
        if name == "result.json":
            try:
                validate_result_diagnostic(value)
            except (ValueError, TypeError):
                raise SystemExit(
                    "Evidence blocked by diagnostic schema guard"
                ) from None
        # Receipts contain only fixed check names, statuses, synthetic IDs and metrics.
        if any(
            word in raw.lower()
            for word in (
                b"access_token",
                b"id_token",
                b"client_secret",
                b"password" + b"=",
                b"authorization:",
            )
        ):
            raise SystemExit("Evidence blocked by secret-name guard")
        digest = hashlib.sha256(raw).hexdigest()
        manifest.append({"file": name, "sha256": digest})
        print(
            "FINLEAK_P0_EVIDENCE "
            + json.dumps(
                {
                    "file": name,
                    "sha256": digest,
                    "base64": base64.b64encode(raw).decode(),
                }
            )
        )
    print("FINLEAK_P0_MANIFEST " + json.dumps(manifest))


if __name__ == "__main__":
    emit(Path(__file__).resolve().parents[2] / ".local/p0-evidence")
