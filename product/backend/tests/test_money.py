from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domain.money import Money
from app.modules.financial_calculations import sum_money


def test_exact_decimal_aggregation_and_json_strings():
    total = sum_money(
        [Money(amount="0.1", currency="USD"), Money(amount="0.2", currency="USD")], currency="USD"
    )
    assert total.amount == Decimal("0.3")
    assert total.model_dump(mode="json") == {"amount": "0.3", "currency": "USD"}


@pytest.mark.parametrize("amount", [0.1, True, "NaN", "Infinity", "0.0000001", "100000000000000"])
def test_rejects_unsafe_or_out_of_range_amounts(amount):
    with pytest.raises(ValidationError):
        Money(amount=amount, currency="USD")


@pytest.mark.parametrize("currency", ["usd", "US", "USDD", "123", " EUR"])
def test_currency_format(currency):
    with pytest.raises(ValidationError):
        Money(amount="1", currency=currency)


def test_mixed_currencies_cannot_be_aggregated():
    with pytest.raises(ValueError, match="different currencies"):
        sum_money([Money(amount="10", currency="EUR")], currency="USD")


def test_preserves_six_decimal_places_and_negative_adjustments():
    result = sum_money(
        [
            Money(amount="10000000000000.123456", currency="GBP"),
            Money(amount="-0.000001", currency="GBP"),
        ],
        currency="GBP",
    )
    assert result.amount == Decimal("10000000000000.123455")


def test_aggregation_overflow_is_rejected():
    with pytest.raises(ValidationError):
        sum_money([Money(amount="99999999999999", currency="USD")] * 2, currency="USD")
