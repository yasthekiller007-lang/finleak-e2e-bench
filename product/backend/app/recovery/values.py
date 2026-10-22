"""Exact arithmetic and explicit temporal precision; no financial rounding fallback."""

from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, localcontext
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.domain.money import Money
from app.proof.budget import ProofError
from app.recovery.schema import Moment

ZERO = Decimal("0")


def fail(code, message="Recovery inputs cannot grant this authority", status=409):
    raise ProofError(code, message, status)


def exact(value):
    if isinstance(value, (float, bool)):
        fail("recovery_precision")
    try:
        return Money(amount=value, currency="USD").amount
    except (ValueError, TypeError):
        fail("recovery_precision")


def total(values):
    with localcontext() as ctx:
        ctx.prec = 80
        return exact(sum(values, ZERO))


def subtract(a, b):
    with localcontext() as ctx:
        ctx.prec = 80
        return exact(a - b)


def aligned(amount, quantum):
    with localcontext() as ctx:
        ctx.prec = 80
        if quantum <= 0 or amount % quantum != ZERO:
            fail("recovery_quantum")


def percentage(numerator, denominator):
    if denominator is None or denominator <= 0:
        return None
    with localcontext() as ctx:
        ctx.prec = 80
        return str(
            (numerator / denominator * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        )


def zone(name):
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, TypeError):
        fail("recovery_temporal_unresolved")


def instant(moment):
    try:
        return _instant(moment)
    except (OverflowError, ValueError):
        fail("recovery_temporal_unresolved")


def _instant(moment):
    moment = Moment.model_validate(moment)
    if moment.precision == "INSTANT":
        return moment.timestamp.astimezone(UTC)
    if moment.precision == "DATE" or moment.timezone is None:
        fail("recovery_temporal_unresolved")
    tz = zone(moment.timezone)
    a = moment.timestamp.replace(tzinfo=tz, fold=0)
    b = moment.timestamp.replace(tzinfo=tz, fold=1)
    if (
        a.utcoffset() != b.utcoffset()
        or a.astimezone(UTC).astimezone(tz).replace(tzinfo=None) != moment.timestamp
    ):
        fail("recovery_temporal_unresolved")
    return a.astimezone(UTC)


def economic_day(moment):
    moment = Moment.model_validate(moment)
    if moment.precision == "DATE":
        return moment.day
    point = instant(moment)
    if moment.timezone:
        return point.astimezone(zone(moment.timezone)).date()
    # Exact offset is evidenced; preserve its local economic calendar date.
    return moment.timestamp.date()


def in_period(moment, start, end, timezone=None):
    moment, start, end = (Moment.model_validate(x) for x in (moment, start, end))
    if start.precision != end.precision:
        fail("recovery_temporal_unresolved")
    if start.precision == "DATE":
        if start.day >= end.day:
            fail("recovery_reporting_period")
        if moment.precision == "DATE":
            day = moment.day
        else:
            if not timezone:
                fail("recovery_temporal_unresolved")
            day = instant(moment).astimezone(zone(timezone)).date()
        return start.day <= day < end.day
    lo, hi = instant(start), instant(end)
    if lo >= hi:
        fail("recovery_reporting_period")
    if moment.precision != "DATE":
        return lo <= instant(moment) < hi
    if not (moment.timezone or timezone):
        fail("recovery_temporal_unresolved")
    tz = zone(moment.timezone or timezone)
    try:
        day_start = datetime.combine(moment.day, datetime.min.time(), tzinfo=tz).astimezone(UTC)
        day_end = datetime.combine(
            moment.day + timedelta(days=1), datetime.min.time(), tzinfo=tz
        ).astimezone(UTC)
    except (OverflowError, ValueError):
        fail("recovery_temporal_unresolved")
    if day_end <= lo or day_start >= hi:
        return False
    if lo <= day_start and day_end <= hi:
        return True
    fail("recovery_temporal_unresolved")
