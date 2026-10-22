from decimal import Decimal, localcontext

from sqlalchemy import Numeric
from sqlalchemy.types import TypeDecorator


class ExactNumeric(TypeDecorator[Decimal]):
    """NUMERIC storage with an ORM guard against floats and silent scale rounding."""

    impl = Numeric
    cache_ok = True

    def __init__(self, precision: int, scale: int):
        super().__init__(precision=precision, scale=scale, asdecimal=True)

    def process_bind_param(self, value: Decimal | None, dialect) -> Decimal | None:
        if value is None:
            return None
        if not isinstance(value, Decimal) or not value.is_finite():
            raise ValueError("Database financial values require a finite Decimal")
        with localcontext() as context:
            context.prec = max(38, len(value.as_tuple().digits))
            normalized = value.normalize()
            if normalized.as_tuple().exponent < -self.impl.scale:
                raise ValueError("Value exceeds database decimal scale")
            if abs(value) >= Decimal(10) ** (self.impl.precision - self.impl.scale):
                raise ValueError("Value exceeds database numeric range")
        return value
