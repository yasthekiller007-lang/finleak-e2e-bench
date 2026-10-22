"""Generate an exact-head engineering CI receipt; never grants pilot approval."""

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from phase7_policy_gate import main as policy_gate


def main():
    root = Path(__file__).resolve().parents[1]
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    assert sha == os.environ["RELEASE_SHA"]
    jobs = json.loads(os.environ["PHASE7_JOB_RESULTS"])
    assert set(jobs) == {
        "backend",
        "frontend",
        "runtime-images",
        "storage-conformance",
        "scanner-conformance",
        "supply-chain",
        "restore-conformance",
        "browser-acceptance",
    }
    assert all(v["result"] == "success" for v in jobs.values())
    directory = root / ".local/phase7"
    artifacts = {
        name: json.loads((directory / f"{name}.json").read_text())
        for name in ("faults", "frontend", "browser", "resources", "capacity")
    }
    assert all(v["release_sha"] == sha for v in artifacts.values())
    assert artifacts["faults"]["summary"]["skipped"] == 0
    assert artifacts["frontend"]["summary"]["skipped"] == 0
    assert artifacts["browser"]["status"] == "passed"
    assert len(artifacts["browser"]["tests"]) == 8
    assert all(t["status"] == "passed" for t in artifacts["browser"]["tests"])
    assert artifacts["capacity"]["verdict"] == "OBSERVED_SYNTHETIC_ENVELOPE_ONLY"
    policy_gate()
    samples = artifacts["resources"]["samples"]
    assert len(samples) >= 2
    peaks = {
        name: max(sample[name] for sample in samples)
        for name in (
            "backend_processes",
            "backend_rss_bytes",
            "backend_cpu_seconds",
            "original_and_temp_bytes",
            "original_bytes",
            "parser_temp_bytes",
            "db_connections",
            "db_lock_waiters",
        )
    }
    report = {
        "release_sha": sha,
        "event": os.environ["GITHUB_EVENT_NAME"],
        "run_id": os.environ["GITHUB_RUN_ID"],
        "date": datetime.now(UTC).isoformat(),
        "tester": "GitHub Actions qualification aggregator",
        "schema": artifacts["resources"]["metadata"]["schema"],
        "jobs": {name: value["result"] for name, value in jobs.items()},
        "backend": artifacts["faults"]["summary"],
        "frontend": artifacts["frontend"]["summary"],
        "browsers": artifacts["browser"]["tests"],
        "runtime": artifacts["browser"]["runtime"],
        "capacity": artifacts["capacity"],
        "resources": {
            "metadata": artifacts["resources"]["metadata"],
            "sample_count": len(samples),
            "observed_seconds": samples[-1]["elapsed_seconds"]
            - samples[0]["elapsed_seconds"],
            "sampled_peaks": peaks,
            "limits": artifacts["resources"]["limits"],
        },
        "p0_ac7": {
            f"P0-{i:02}/AC7-{i:02}": "IMPLEMENTED / EXTERNAL EVIDENCE PENDING"
            for i in range(1, 36)
        },
        "cross_cutting": {
            "AC7-36": "PASS",
            "AC7-37": "PASS",
            "AC7-38": "THIS EVENT PASS; MATCHING PUSH AND PR RECEIPTS BOTH REQUIRED",
            "AC7-39": "PASS",
            "AC7-40": "NOT IMPLEMENTED / BLOCKED",
        },
        "pilot": "NO-GO",
        "deployment": "NOT AUTHORIZED / NOT PERFORMED",
        "limitations": "Synthetic engineering qualification; actual staging/provider/managed restore/customer enrollment and sign-offs remain external obligations",
    }
    (directory / "qualification.json").write_text(json.dumps(report, indent=2))
    print(
        json.dumps(
            {
                "exact_head_ci": "PASS",
                "event": report["event"],
                "sha": sha,
                "pilot": "NO-GO",
            }
        )
    )


if __name__ == "__main__":
    main()
