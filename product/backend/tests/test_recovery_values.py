from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.proof.budget import ProofError
from app.recovery.schema import Components, Limits, Moment
from app.recovery.values import aligned, exact, in_period, instant, percentage, subtract, total


def day(value):
    return Moment(precision="DATE", day=value)


def at(value):
    return Moment(precision="INSTANT", timestamp=value)


@pytest.mark.parametrize("value", [0.01, True, "NaN", "Infinity", "0.0000001", "100000000000000"])
def test_invalid_precision_has_no_financial_rounding_fallback(value):
    with pytest.raises(ProofError, match="recovery_precision"):
        exact(value)


def test_exact_cent_quantum_overflow_and_ratio_display_separation():
    assert subtract(exact("0.01"), exact("0.01")) == Decimal("0")
    assert total([exact("20000"), exact("15000")]) == Decimal("35000")
    assert percentage(exact("30000"), exact("50000")) == "60.00"
    assert percentage(exact("1"), exact("3")) == "33.33"
    assert percentage(exact("1"), None) is None
    aligned(exact("0.01"), exact("0.01"))
    with pytest.raises(ProofError, match="recovery_quantum"):
        aligned(exact("0.001"), exact("0.01"))
    with pytest.raises(ProofError, match="recovery_precision"):
        total([exact("99999999999999.999999"), exact("0.000001")])


@pytest.mark.parametrize(
    "data",
    [
        dict(
            principal="90000",
            gross="108000",
            tax="18000",
            other="0",
            tax_basis="INCLUSIVE",
            reconciliation="COMPLETE",
        ),
        dict(
            principal="50000",
            gross="50000",
            tax="0",
            other="0",
            fees="500",
            withholding="0",
            net_cash="49500",
            tax_basis="EXCLUSIVE",
            reconciliation="COMPLETE",
        ),
        dict(
            principal="49500",
            gross="50000",
            withholding="500",
            net_cash="49500",
            tax_basis="EXCLUSIVE",
            reconciliation="UNRESOLVED",
        ),
    ],
)
def test_evidenced_tax_and_cash_bridges_preserve_distinct_components(data):
    c = Components.model_validate(data)
    assert c.principal == Decimal(data["principal"])
    assert c.tax_recoverability == "NOT_ASSESSED"


@pytest.mark.parametrize(
    "changes", [dict(tax_basis="UNKNOWN"), dict(tax=None), dict(gross="108001")]
)
def test_tax_unknown_or_inconsistent_bridge_cannot_be_complete(changes):
    data = dict(
        principal="90000",
        gross="108000",
        tax="18000",
        other="0",
        tax_basis="INCLUSIVE",
        reconciliation="COMPLETE",
    )
    with pytest.raises(ValidationError):
        Components.model_validate(data | changes)


def test_date_only_and_half_open_boundaries_are_not_midnight_utc_guesses():
    assert in_period(day("2026-12-31"), day("2026-12-01"), day("2027-01-01"))
    assert not in_period(day("2027-01-01"), day("2026-12-01"), day("2027-01-01"))
    assert in_period(
        at("2027-01-01T00:00:00Z"), at("2027-01-01T00:00:00Z"), at("2027-02-01T00:00:00Z")
    )
    assert not in_period(
        at("2027-02-01T00:00:00Z"), at("2027-01-01T00:00:00Z"), at("2027-02-01T00:00:00Z")
    )
    assert in_period(
        day("2027-01-01"), at("2027-01-01T00:00:00Z"), at("2027-01-02T00:00:00Z"), "Etc/UTC"
    )
    with pytest.raises(ProofError, match="recovery_temporal_unresolved"):
        in_period(
            day("2027-01-01"), at("2027-01-01T12:00:00Z"), at("2027-01-02T00:00:00Z"), "Etc/UTC"
        )
    with pytest.raises(ProofError, match="recovery_temporal_unresolved"):
        in_period(day("2027-01-01"), at("2027-01-01T00:00:00Z"), at("2027-01-02T00:00:00Z"))


@pytest.mark.parametrize("timestamp", ["2026-03-08T02:30:00", "2026-11-01T01:30:00"])
def test_nonexistent_and_ambiguous_dst_local_sources_are_unresolved(timestamp):
    with pytest.raises(ProofError, match="recovery_temporal_unresolved"):
        instant(Moment(precision="LOCAL", timestamp=timestamp, timezone="America/New_York"))


def test_approved_operational_profile_defaults_are_exact():
    assert Limits().model_dump() == {
        "profile": "recovery-operations/1",
        "request_bytes": 1048576,
        "text_chars": 4000,
        "documents": 50,
        "bindings": 500,
        "source_bytes": 104857600,
        "work_seconds": 25,
        "response_bytes": 10485760,
        "history_page": 100,
        "projection_records": 10000,
        "tenant_concurrency": 2,
        "actor_operations_per_minute": 10,
    }


def test_temporal_extremes_return_unresolved_instead_of_guessed_date():
    from app.recovery.values import instant

    with pytest.raises(ProofError, match="recovery_temporal_unresolved"):
        instant({"precision": "INSTANT", "timestamp": "0001-01-01T00:00:00+14:00"})
    with pytest.raises(ProofError, match="recovery_temporal_unresolved"):
        in_period(
            {"precision": "DATE", "day": "9999-12-31"},
            {"precision": "INSTANT", "timestamp": "9999-12-30T00:00:00Z"},
            {"precision": "INSTANT", "timestamp": "9999-12-31T23:59:59Z"},
            "UTC",
        )
