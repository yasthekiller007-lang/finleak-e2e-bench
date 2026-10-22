"""Pin fault coverage to actual passing tests; fixtures do not graduate staging."""

import json
import os
import platform
from datetime import UTC, datetime
from pathlib import Path
from xml.etree import ElementTree

CASES = {
    "FAIL-01": [
        "test_missing_auth_and_cross_tenant_reads",
        "test_role_final_authority_and_viewer_read",
    ],
    "FAIL-02": [
        "test_nonclean_scan_blocks_process_download_and_release_without_source_transform"
    ],
    "FAIL-03": ["test_source_tamper_rollback_and_cross_tenant_no_metadata_leak"],
    "FAIL-04": [
        "test_private_scanner_outage_timeout_and_expired_budget_are_distinct_closed_results"
    ],
    "FAIL-05": [
        "test_worker_timeout_kills_process_and_does_not_forward_secrets",
        "test_active_attempts_are_serialized_and_stale_lease_is_audited",
    ],
    "FAIL-06": [
        "test_retry_semantic_deduplication_request_conflict_and_one_issuance_audit",
        "test_simultaneous_approval_idempotency_one_money_one_audit",
    ],
    "FAIL-07": [
        "test_untrusted_journal_insert_and_financial_audit_failure_rollback",
        "test_disabled_guards_fail_closed",
    ],
    "FAIL-09": ["test_approval_serializes_every_calculation_and_recovery_authority"],
    "FAIL-10": ["test_RW28_foreign_currency_no_fx", "test_RW13_stale_basis"],
    "FAIL-11": [
        "test_tenant_capacity_is_shared_between_independent_worker_pools",
        "test_actor_quota_is_atomic_across_simultaneous_workers_and_operations",
    ],
    "FAIL-12": [
        "test_real_postgresql_readiness_fences_old_schema_disabled_guard_and_tracking",
        "test_logical_cluster_changed_financial_history_guards_grants_or_sources_cannot_qualify",
    ],
}


def main():
    root = Path(__file__).resolve().parents[1] / ".local/phase7"
    tests = ElementTree.parse(root / "backend.xml").findall(".//testcase")
    assert tests and all(
        not any(t.find(tag) is not None for tag in ("skipped", "failure", "error"))
        for t in tests
    )
    rows = {}
    for name, required in CASES.items():
        matched = [t for t in tests if t.attrib["name"].split("[")[0] in required]
        present = {t.attrib["name"].split("[")[0] for t in matched}
        assert present == set(required), (name, "missing test evidence")
        assert all(
            not any(t.find(tag) is not None for tag in ("skipped", "failure", "error"))
            for t in matched
        ), (name, "failed or skipped")
        rows[name] = {
            "fixture_coverage": "PASS FOR NAMED ASSERTIONS / PARTIAL PLAN COVERAGE",
            "assertions": len(matched),
            "tests": required,
            "staging_fault_drill": "EXTERNAL EVIDENCE PENDING",
        }
    # Post-commit publication/native restart is separately exercised by restore-conformance;
    # never infer that run from this component-suite artifact.
    rows["FAIL-08"] = {
        "fixture_coverage": "SEPARATE RESTORE-CONFORMANCE REQUIRED",
        "staging_fault_drill": "EXTERNAL EVIDENCE PENDING",
    }
    (root / "faults.json").write_text(
        json.dumps(
            {
                "release_sha": os.environ["RELEASE_SHA"],
                "scope": "Component/API/PostgreSQL suite; not a deployed fault drill",
                "date": datetime.now(UTC).isoformat(),
                "tester": "GitHub Actions / pytest",
                "python": platform.python_version(),
                "schema": "0009",
                "summary": {"passed": len(tests), "skipped": 0, "failed": 0},
                "rows": rows,
            },
            indent=2,
        )
    )
    print(
        json.dumps(
            {"fault_fixture_coverage": "PASS", "rows": len(rows), "pilot": "NO-GO"}
        )
    )


if __name__ == "__main__":
    main()
