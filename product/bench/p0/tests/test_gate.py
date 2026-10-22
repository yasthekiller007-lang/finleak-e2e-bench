import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from gate import Blocked, execution_gate, validate_billing, verify_source

NOW = datetime(2026, 10, 22, tzinfo=timezone.utc)


def complete():
    return {
        "repository": "synthetic-owner/private-bench",
        "owner": "synthetic-owner",
        "authorized_actor": "synthetic-owner",
        "visibility": "private",
        "verified_at_utc": NOW.isoformat(),
        "standard_runner_allowed": True,
        "usage_blocked": False,
        "extra_charge_prevention_verified": True,
        "all_applicable_budgets_reviewed": True,
        "first_cycle_and_update_delay_caveats_resolved": True,
        "minutes_remaining": 10,
        "storage_remaining_mb": 10,
        "concurrent_usage_reviewed": True,
        "actions_spending_limit_usd": 0,
        "redacted_authenticated_export_sha256": "a" * 64,
    }


def test_fresh_scoped_review_document_is_accepted_as_document_only():
    validate_billing(complete(), "synthetic-owner/private-bench", NOW)


@pytest.mark.parametrize(
    "field,value",
    [
        ("usage_blocked", True),
        ("minutes_remaining", 9),
        ("storage_remaining_mb", 0),
        ("owner", "other-owner"),
        ("repository", "synthetic-owner/another"),
        ("visibility", "public"),
        ("standard_runner_allowed", False),
        ("extra_charge_prevention_verified", False),
        ("all_applicable_budgets_reviewed", False),
        ("first_cycle_and_update_delay_caveats_resolved", False),
        ("actions_spending_limit_usd", 1),
        ("concurrent_usage_reviewed", False),
        ("redacted_authenticated_export_sha256", None),
        ("verified_at_utc", None),
    ],
)
def test_incomplete_or_unsafe_billing_review_is_blocked(field, value):
    document = complete()
    document[field] = value
    with pytest.raises(Blocked):
        validate_billing(document, "synthetic-owner/private-bench", NOW)


@pytest.mark.parametrize("age", [-1, 86401])
def test_future_and_stale_reviews_are_blocked(age):
    document = complete()
    document["verified_at_utc"] = (NOW - timedelta(seconds=age)).isoformat()
    with pytest.raises(Blocked):
        validate_billing(document, "synthetic-owner/private-bench", NOW)


def test_1000_remaining_minutes_do_not_override_usage_blocked():
    document = complete()
    document.update(minutes_remaining=1000, usage_blocked=True)
    with pytest.raises(Blocked):
        validate_billing(document, "synthetic-owner/private-bench", NOW)


def test_published_example_is_explicitly_blocked():
    example = json.loads(
        (
            Path(__file__).resolve().parents[1] / "billing-evidence.example.json"
        ).read_text()
    )
    with pytest.raises(Blocked):
        validate_billing(example, example["repository"], NOW)


@pytest.mark.parametrize(
    "key,value",
    [
        ("GITHUB_ACTIONS", "false"),
        ("GITHUB_EVENT_NAME", "push"),
        ("P0_AUTHORIZATION", ""),
        ("P0_RUNNER_KIND", "self-hosted"),
        ("GITHUB_RUN_ATTEMPT", "2"),
    ],
)
def test_execution_rejects_non_manual_or_non_hosted_surfaces(
    monkeypatch, tmp_path, key, value
):
    for name, expected in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "P0_AUTHORIZATION": "FINLEAK-P0-ONE-RUN",
        "P0_RUNNER_KIND": "github-hosted",
        "GITHUB_RUN_ATTEMPT": "1",
    }.items():
        monkeypatch.setenv(name, expected)
    monkeypatch.setenv(key, value)
    with pytest.raises(Blocked):
        execution_gate(tmp_path)


def reviewed_environment(monkeypatch, tmp_path):
    root = tmp_path / "product"
    (root / "bench/p0").mkdir(parents=True)
    (root / "frozen-source.txt").write_text("verified test source")
    digest = hashlib.sha256((root / "frozen-source.txt").read_bytes()).hexdigest()
    (root / "bench/p0/v23-source.sha256").write_text(digest + "  frozen-source.txt\n")
    document = complete()
    document["verified_at_utc"] = datetime.now(timezone.utc).isoformat()
    path = tmp_path / "billing-evidence.json"
    path.write_text(json.dumps(document))
    for name, value in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "P0_AUTHORIZATION": "FINLEAK-P0-ONE-RUN",
        "P0_RUNNER_KIND": "github-hosted",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_ACTOR": "synthetic-owner",
        "GITHUB_REPOSITORY": "synthetic-owner/private-bench",
        "GITHUB_SHA": "b" * 40,
        "P0_EXPECTED_COMMIT": "b" * 40,
        "P0_BILLING_SHA256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }.items():
        monkeypatch.setenv(name, value)
    return root


def test_complete_execution_document_guard_without_starting_any_service(
    monkeypatch, tmp_path
):
    root = reviewed_environment(monkeypatch, tmp_path)
    execution_gate(root)


@pytest.mark.parametrize(
    "key,value",
    [
        ("GITHUB_ACTOR", "another-writer"),
        ("P0_EXPECTED_COMMIT", "c" * 40),
        ("P0_BILLING_SHA256", "c" * 64),
    ],
)
def test_wrong_actor_payload_or_billing_hash_blocked(monkeypatch, tmp_path, key, value):
    root = reviewed_environment(monkeypatch, tmp_path)
    monkeypatch.setenv(key, value)
    with pytest.raises(Blocked):
        execution_gate(root)


def test_changed_original_source_blocks_execution(monkeypatch, tmp_path):
    root = reviewed_environment(monkeypatch, tmp_path)
    (root / "frozen-source.txt").write_text("changed")
    with pytest.raises(Blocked):
        execution_gate(root)


def test_actual_425_original_v23_sources_are_unchanged():
    root = Path(__file__).resolve().parents[3]
    verify_source(root)
    assert len((root / "bench/p0/v23-source.sha256").read_text().splitlines()) == 425
