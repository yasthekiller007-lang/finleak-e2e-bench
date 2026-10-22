"""Actual offline ClamAV over a private Unix socket; synthetic originals only.

The image includes its fixed signature snapshot. No FreshClam/network scanner
or public byte transmission occurs. CI proves the actual engine, not deployed
signature freshness. This harness is excluded from application images.
"""

import hashlib
import io
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from time import monotonic, sleep
from uuid import uuid4

from app.core.config import REPOSITORY_ROOT
from app.modules.scanner import ClamAVScanner, ScannerFailure


def command(*args):
    return (
        subprocess.check_output(["docker", *args], stderr=subprocess.DEVNULL, timeout=30)
        .decode()
        .strip()
    )


def main():
    image = os.environ.get("PHASE7_CLAMAV_IMAGE", "")
    if not re.fullmatch(r"sha256:[a-f0-9]{64}", image):
        raise RuntimeError("A qualified immutable locally built ClamAV image ID is required")
    # Standard harmless EICAR test signature, not executable malware.
    eicar = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
    clean = b"field,value\nsupplier,Synthetic private engine case\n"
    signature_hash = hashlib.sha256(eicar).hexdigest()
    config = (REPOSITORY_ROOT / "deploy/phase7/scanner/clamd.conf").read_text()
    name = "phase7-scanner-" + uuid4().hex[:16]
    with tempfile.TemporaryDirectory(prefix="fla-engine-") as directory:
        root = Path(directory)
        # Same unprivileged caller UID in isolated CI, socket 0600, directory 0700.
        # Deployment uses a distinct daemon UID, shared group, nonwritable parent.
        private_config = root / "clamd.conf"
        private_config.write_text(
            config.replace("LocalSocketMode 660", "LocalSocketMode 600").replace(
                "SelfCheck 600", "SelfCheck 0"
            )
        )
        command(
            "run",
            "-d",
            "--name",
            name,
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "64",
            "--memory",
            "3g",
            "--cpus",
            "2",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--tmpfs",
            "/tmp:size=64m,mode=1777",
            "-v",
            f"{root}:/scanner",
            "--entrypoint",
            "clamd",
            image,
            "--config-file=/scanner/clamd.conf",
        )
        try:
            scanner = ClamAVScanner(socket_path=str(root / "clamd.sock"), timeout_seconds=2)
            deadline = monotonic() + 120
            while True:
                try:
                    version = scanner.healthcheck()
                    break
                except (ScannerFailure, OSError):
                    if command("inspect", "--format", "{{.State.Running}}", name) != "true":
                        raise RuntimeError("Private synthetic scanner did not start") from None
                    if monotonic() >= deadline:
                        raise RuntimeError(
                            "Private synthetic scanner startup budget exceeded"
                        ) from None
                    sleep(0.2)
            versions = {version}
            for original, expected in ((clean, "CLEAN"), (eicar, "INFECTED")):
                before = hashlib.sha256(original).hexdigest()
                verdict = scanner.scan(
                    io.BytesIO(original), max_bytes=len(original), deadline=monotonic() + 20
                )
                assert verdict.status == expected, verdict.status
                assert hashlib.sha256(original).hexdigest() == before
                versions.add(verdict.version)
            # No bytes are sent once the work budget is expired.
            assert (
                scanner.scan(
                    io.BytesIO(clean), max_bytes=len(clean), deadline=monotonic() - 1
                ).status
                == "TIMEOUT"
            )
            command("stop", "--time", "5", name)
            assert (
                scanner.scan(
                    io.BytesIO(clean), max_bytes=len(clean), deadline=monotonic() + 2
                ).status
                == "UNAVAILABLE"
            )
            print(
                json.dumps(
                    {
                        "kind": "synthetic-private-ClamAV-engine",
                        "release_sha": os.environ.get("RELEASE_SHA"),
                        "image": image,
                        "config_sha256": hashlib.sha256(config.encode()).hexdigest(),
                        "engine_database_versions": sorted(versions),
                        "eicar_sha256": signature_hash,
                        "cases": [
                            "actual-clean",
                            "actual-harmless-signature-infected",
                            "expired-budget",
                            "actual-daemon-down",
                        ],
                        "network": "none",
                        "byte_transformation": False,
                        "result": "PASS",
                        "production_signature_freshness_qualified": False,
                        "real_deployment_evidence": False,
                    },
                    sort_keys=True,
                )
            )
        finally:
            subprocess.run(
                ["docker", "rm", "-f", name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )


if __name__ == "__main__":
    main()
