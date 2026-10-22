from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, StringConstraints


def reject_float(value: object) -> object:
    if isinstance(value, (float, bool)):
        raise ValueError("Financial values must be Decimal, integer, or decimal strings")
    return value


Amount = Annotated[
    Decimal,
    BeforeValidator(reject_float),
    Field(
        max_digits=20,
        decimal_places=6,
        ge=Decimal("-99999999999999.999999"),
        le=Decimal("99999999999999.999999"),
        allow_inf_nan=False,
    ),
]
Currency = Annotated[str, StringConstraints(strict=True, pattern=r"^[A-Z]{3}$")]
Confidence = Annotated[Decimal, BeforeValidator(reject_float), Field(ge=0, le=1, decimal_places=4)]


class Money(BaseModel):
    model_config = {"frozen": True}
    amount: Amount
    currency: Currency
