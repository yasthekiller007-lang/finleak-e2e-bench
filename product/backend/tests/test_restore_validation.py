from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.operations.restore_validation import PROFILE, checksum, compare


def reference():
    return {
        "profile": PROFILE,
        "system_identifier": "12345",
        "schema": "0009",
        "database_sha256": "a" * 64,
        "guards_sha256": "b" * 64,
        "functions_sha256": "c" * 64,
        "privileges_sha256": "d" * 64,
        "source_count": 3,
        "original_inventory_sha256": "e" * 64,
        "uncaptured_provenance": [
            {"id": "opaque", "actual_original_commit": "2026-10-03T23:59:59+00:00"}
        ],
    }


def test_native_restore_retains_original_commit_boundary_and_does_not_authorize_release():
    original = reference()
    assert compare(original, deepcopy(original))["result"] == "PASS"
    assert compare(original, deepcopy(original))["release_authorization"] is False
    changed = deepcopy(original)
    changed["uncaptured_provenance"][0]["actual_original_commit"] = "2026-10-04T00:01:00+00:00"
    assert compare(original, changed)["result"] == "FAIL"
    assert original == reference()


@pytest.mark.parametrize(
    "field",
    [
        "system_identifier",
        "database_sha256",
        "guards_sha256",
        "privileges_sha256",
        "original_inventory_sha256",
        "functions_sha256",
    ],
)
def test_logical_cluster_changed_financial_history_guards_grants_or_sources_cannot_qualify(field):
    changed = reference() | {field: "changed"}
    result = compare(reference(), changed)
    assert result["result"] == "FAIL" and field in result["different_fields"]
    assert "changed" not in str(result)


def test_unknown_profile_and_missing_snapshot_are_not_success():
    with pytest.raises(ValueError):
        compare({}, reference())
    assert compare(reference(), {"profile": PROFILE})["result"] == "FAIL"


def test_operational_digests_preserve_decimal_scale_precision_null_and_temporal_boundary():
    exact = Decimal("123456789012345678.123456")
    assert checksum(exact) != checksum(Decimal("123456789012345678.123457"))
    assert checksum(Decimal("1.00")) != checksum(Decimal("1.0"))
    assert checksum(None) != checksum(Decimal("0"))
    assert checksum(datetime(2026, 10, 3, 23, 59, 59, tzinfo=UTC)) != checksum(
        datetime(2026, 10, 4, tzinfo=UTC)
    )
