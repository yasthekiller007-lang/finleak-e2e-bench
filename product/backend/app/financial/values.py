"""Nominal financial values used by the pure arithmetic layer."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Quantity:
    value: Decimal
    unit: str


@dataclass(frozen=True)
class MonetaryAmount:
    value: Decimal
    currency: str


@dataclass(frozen=True)
class UnitPrice:
    amount: MonetaryAmount
    unit: str

    def extend(self, quantity: Quantity) -> MonetaryAmount:
        if quantity.unit != self.unit:
            raise ValueError("Unit price requires a compatible quantity")
        return MonetaryAmount(self.amount.value * quantity.value, self.amount.currency)


@dataclass(frozen=True)
class Percentage:
    value: Decimal

    def reduce(self, base: MonetaryAmount) -> MonetaryAmount:
        if not Decimal("0") <= self.value <= Decimal("100"):
            raise ValueError("Percentage must be between zero and one hundred")
        return MonetaryAmount(
            base.value * (Decimal("100") - self.value) / Decimal("100"), base.currency
        )
