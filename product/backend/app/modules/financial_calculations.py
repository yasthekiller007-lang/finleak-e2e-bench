from collections.abc import Iterable
from decimal import Decimal, localcontext

from app.domain.money import Currency, Money


def sum_money(values: Iterable[Money], *, currency: Currency) -> Money:
    """Exact aggregation only; no conversion, tax policy, or implicit rounding."""
    with localcontext() as context:
        context.prec = 38
        total = Decimal("0")
        for value in values:
            if value.currency != currency:
                raise ValueError("Cannot combine different currencies")
            total += value.amount
        return Money(amount=total, currency=currency)
