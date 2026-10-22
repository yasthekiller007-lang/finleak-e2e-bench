"""Fail-closed pre-dispatch document validation; not a billing API or cost guarantee."""

import hashlib
import json
import os
import platform
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path


class Blocked(Exception):
    pass


# One explicit D1 diagnostic-only overlay. The historical manifest stays frozen.
# Both the original manifest entry and the reviewed replacement must match.
DIAGNOSTIC_SOURCE_OVERLAY = {
    "backend/acceptance/product_v11.py": (
        "6bffe94465331275a46bc43c403dcef7fc486d63b243c14b7d524cdc598a544d",
        "377dee5a42b75223f5da91e76937ec96ad7371b6ea5e949bb8aae6dbfd426072",
    ),
}


def validate_billing(value, repository, now):
    try:
        checked = datetime.fromisoformat(value["verified_at_utc"])
        checks = [
            value["repository"] == repository,
            value["owner"] == repository.split("/")[0],
            value["visibility"] == "private",
            value["standard_runner_allowed"] is True,
            value["usage_blocked"] is False,
            value["extra_charge_prevention_verified"] is True,
            value["all_applicable_budgets_reviewed"] is True,
            value["first_cycle_and_update_delay_caveats_resolved"] is True,
            value["minutes_remaining"] >= 10,
            value["storage_remaining_mb"] >= 10,
            value["concurrent_usage_reviewed"] is True,
            value["actions_spending_limit_usd"] == 0,
            re.fullmatch(r"[0-9a-f]{64}", value["redacted_authenticated_export_sha256"])
            is not None,
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", value["authorized_actor"])
            is not None,
            checked.tzinfo is not None,
            0 <= (now - checked).total_seconds() <= 86400,
        ]
        if not all(checks):
            raise ValueError("Incomplete review")
    except (KeyError, ValueError, TypeError):
        raise Blocked(
            "Fresh, scoped, authenticated cost and permission review missing"
        ) from None


def execution_gate(root):
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or os.environ.get("P0_AUTHORIZATION") != "FINLEAK-P0-ONE-RUN"
        or os.environ.get("P0_RUNNER_KIND") != "github-hosted"
        or os.environ.get("GITHUB_RUN_ATTEMPT") != "1"
    ):
        raise Blocked(
            "Separately authorized manual standard GitHub-hosted job required"
        )
    sha = os.environ.get("GITHUB_SHA", "")
    if (
        not re.fullmatch(r"[0-9a-f]{40}", sha)
        or os.environ.get("P0_EXPECTED_COMMIT") != sha
    ):
        raise Blocked("Reviewed immutable payload commit does not match")
    path = root.parent / "billing-evidence.json"
    if not path.is_file():
        raise Blocked(
            "Billing review file missing; remaining minutes do not override Usage blocked"
        )
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != os.environ.get("P0_BILLING_SHA256"):
        raise Blocked("Reviewed billing evidence hash does not match")
    evidence = json.loads(raw)
    if evidence.get("authorized_actor") != os.environ.get("GITHUB_ACTOR"):
        raise Blocked("Actor is outside the separately reviewed one-run authorization")
    validate_billing(
        evidence,
        os.environ.get("GITHUB_REPOSITORY", ""),
        datetime.now(UTC),
    )
    verify_source(root)


def verify_source(root):
    for line in (root / "bench/p0/v23-source.sha256").read_text().splitlines():
        digest, name = line.split("  ", 1)
        if name in DIAGNOSTIC_SOURCE_OVERLAY:
            original, replacement = DIAGNOSTIC_SOURCE_OVERLAY[name]
            if digest != original:
                raise Blocked("Diagnostic overlay base source integrity check failed")
            digest = replacement
        path = root / name
        if (
            path.is_symlink()
            or not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest
        ):
            raise Blocked("Frozen V2.3 source integrity check failed")


def resources(root):
    mem = dict(
        line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines()
    )
    available = int(mem["MemAvailable"].split()[0]) * 1024
    free = shutil.disk_usage(root).free
    if platform.machine() != "x86_64" or (os.cpu_count() or 0) < 2:
        raise Blocked("Standard x64 runner with at least two CPUs required")
    if available < 5 * 1024**3 or free < 7 * 1024**3:
        raise Blocked(
            "Insufficient standard-runner memory or disk; no machine escalation allowed"
        )
    return {
        "architecture": platform.machine(),
        "cpus": os.cpu_count(),
        "available_memory_bytes": available,
        "free_disk_bytes": free,
    }


if __name__ == "__main__":
    try:
        root = Path(__file__).resolve().parents[2]
        execution_gate(root)
        print(
            json.dumps(
                {
                    "status": "PREFLIGHT_ONLY",
                    "resources": resources(root),
                    "billing": "EXTERNAL_REVIEW_DOCUMENT_MATCHED_NOT_AN_API_GUARANTEE",
                }
            )
        )
    except (Blocked, OSError, ValueError) as error:
        print(json.dumps({"status": "BLOCKED", "reason_type": type(error).__name__}))
        raise SystemExit(2) from None
