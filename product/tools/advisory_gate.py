"""Fail closed on invalid scans; high/critical findings cannot disappear silently."""

import hashlib
import json
import os
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


def review(report, *, scoped_review=None, patched_zlib=False):
    if not isinstance(report, dict) or not isinstance(report.get("matches"), list):
        raise TypeError("Missing advisory scan results")
    if report.get("descriptor", {}).get("name") != "grype":
        raise ValueError("Unqualified advisory scanner")
    if report.get("ignoredMatches"):
        raise ValueError("Suppressed advisory matches require explicit review")
    counts, blockers, reviewed, findings = Counter(), [], [], []
    for match in report["matches"]:
        artifact, vulnerability = match["artifact"], match["vulnerability"]
        severity = vulnerability["severity"].lower()
        if severity not in {
            "negligible",
            "low",
            "medium",
            "high",
            "critical",
            "unknown",
        }:
            raise ValueError("Unrecognized advisory severity")
        counts[severity] += 1
        findings.append(
            {
                "package": artifact["name"],
                "version": artifact["version"],
                "id": vulnerability["id"],
                "severity": severity,
                "fixed_versions": vulnerability.get("fix", {}).get("versions", []),
            }
        )
        if severity in {"high", "critical"}:
            if (
                patched_zlib
                and severity == "high"
                and artifact["name"] == "zlib"
                and artifact["version"] == "1.3.2-r0"
                and vulnerability["id"] == "CVE-2026-85091"
            ):
                reviewed.append(
                    {
                        "id": vulnerability["id"],
                        "package": "zlib",
                        "version": "1.3.2-r0",
                        "scope": "actual-runtime-upstream-patched-library",
                    }
                )
                continue
            if scoped_review and all(
                (
                    artifact["name"] == scoped_review["package"],
                    artifact["version"] == scoped_review["version"],
                    vulnerability["id"] == scoped_review["id"],
                    severity == "high",
                    not vulnerability.get("fix", {}).get("versions"),
                    datetime.now(UTC)
                    < datetime.fromisoformat(scoped_review["expires"].replace("Z", "+00:00")),
                )
            ):
                reviewed.append(
                    {
                        "id": vulnerability["id"],
                        "package": artifact["name"],
                        "version": artifact["version"],
                        "scope": scoped_review["scope"],
                    }
                )
                continue
            blockers.append(
                {
                    "package": artifact["name"],
                    "version": artifact["version"],
                    "id": vulnerability["id"],
                    "severity": severity,
                    "fixed_versions": vulnerability.get("fix", {}).get("versions", []),
                }
            )
    # No blanket ignored/unfixed/dev filter; any exception requires separately
    # evidenced version/advisory/reachability review, not changing this gate.
    return {
        "counts": dict(sorted(counts.items())),
        "blockers": blockers,
        "result": "BLOCKED"
        if blockers
        else "VERIFIED UPSTREAM PATCH"
        if reviewed
        and all(item["scope"] == "actual-runtime-upstream-patched-library" for item in reviewed)
        else "REVIEWED NON-RUNTIME FINDING"
        if reviewed
        else "NO HIGH/CRITICAL MATCHES",
        "reviewed": reviewed,
        "findings": findings,
        "remaining_findings_require_review": bool(counts),
    }


def qualify_review(root, evidence, release_sha):
    if (
        evidence.get("result") != "PASS"
        or evidence.get("kind") != "frontend-dev-glob-absence"
        or not release_sha
        or len(release_sha) != 40
        or any(char not in "0123456789abcdef" for char in release_sha)
        or evidence.get("release_sha") != release_sha
        or set(evidence.get("forbidden", [])) != {"braces", "micromatch", "fast-glob"}
        or not 0 < evidence.get("files", 0) <= 25000
        or not 0 < evidence.get("bytes", 0) <= 200 * 1024 * 1024
    ):
        raise ValueError("Missing exact-image non-runtime evidence")
    lock = json.loads((root / "frontend/package-lock.json").read_text())
    brace = lock["packages"]["node_modules/braces"]
    if brace.get("dev") is not True or brace["version"] != "3.0.3":
        raise ValueError("Reviewed development scope changed")
    eslint = (root / "frontend/eslint.config.mjs").read_text()
    if any(value in eslint for value in ("rootDir", "micromatch", "braces")):
        raise ValueError("Reviewed trusted ESLint input scope changed")
    policy = json.loads((root / "tools/advisory_reviews.json").read_text())
    if policy.get("profile") != "pilot-advisory-review/1" or len(policy["reviews"]) != 1:
        raise ValueError("Unqualified advisory review profile")
    selected = policy["reviews"][0]
    if (selected["scope"], selected["package"], selected["version"], selected["id"]) != (
        "npm-lock-dev-only",
        "braces",
        "3.0.3",
        "GHSA-vfj7-8cjw-p6xm",
    ):
        raise ValueError("Unqualified advisory review scope")
    if not (root / selected["evidence"]).is_file():
        raise ValueError("Missing written reachability review")
    return selected


def qualify_zlib(evidence, release_sha):
    if (
        evidence.get("result") != "PASS"
        or evidence.get("kind") != "patched-zlib-runtime"
        or not re.fullmatch("[a-f0-9]{40}", release_sha or "")
        or evidence.get("release_sha") != release_sha
        or len(evidence.get("images", [])) != 3
        or datetime.now(UTC) >= datetime(2026, 10, 9, tzinfo=UTC)
    ):
        raise ValueError("Missing exact-image patched-library evidence")
    if {item["image"] for item in evidence["images"]} != {
        "phase7-backend:advisory",
        "phase7-frontend:advisory",
        "phase7-scanner:advisory",
    }:
        raise ValueError("Incomplete runtime library inventories")
    for item in evidence["images"]:
        if (
            item["source_commit"] != "df84af25dc1942490e1d1c899a07619152a46148"
            or item["profile"] != "pilot-zlib-patch/1"
            or item["path"] != "/usr/lib/libz.so.1"
            or not re.fullmatch("[a-f0-9]{64}", item["library_sha256"])
            or not re.fullmatch("sha256:[a-f0-9]{64}", item["image_id"])
        ):
            raise ValueError("Unqualified runtime library patch")


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--non-runtime-evidence", type=Path)
    parser.add_argument("--patched-zlib-evidence", type=Path)
    parser.add_argument("reports", nargs="+")
    args = parser.parse_args()
    selected = None
    patched = False
    if args.patched_zlib_evidence:
        qualify_zlib(
            json.loads(args.patched_zlib_evidence.read_text()), os.environ.get("RELEASE_SHA")
        )
        patched = True
    if args.non_runtime_evidence:
        evidence = json.loads(args.non_runtime_evidence.read_text())
        root = Path(__file__).resolve().parents[1]
        selected = qualify_review(root, evidence, os.environ.get("RELEASE_SHA"))
    failures = False
    for name in args.reports:
        file = Path(name)
        result = review(
            json.loads(file.read_text()),
            scoped_review=selected if file.name == "npm.json" else None,
            patched_zlib=patched
            and file.name in {"backend-image.json", "frontend-image.json", "scanner-image.json"},
        )
        failures |= bool(result["blockers"])
        print(
            json.dumps(
                {
                    "scan": file.name,
                    "report_sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                    **result,
                },
                sort_keys=True,
            )
        )
    if not sys.argv[1:]:
        raise ValueError("No scans supplied")
    raise SystemExit(failures)


if __name__ == "__main__":
    main()
