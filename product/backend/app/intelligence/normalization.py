"""Exact, conservative normalization; no inferred dates, currencies or totals."""

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.db.types import ExactNumeric

# Explicitly supported ISO-style codes; unsupported codes remain reviewable raw evidence.
CURRENCIES = frozenset(
    (
        "USD EUR GBP MAD CAD AUD NZD CHF JPY CNY INR AED SAR BRL MXN ZAR "
        "SEK NOK DKK PLN SGD HKD KRW TRY EGP TND QAR KWD BHD OMR"
    ).split()
)


def normalize(raw: str, kind: str) -> str | bool | None:
    value = raw.strip()
    if not value:
        return None
    if kind == "text":
        return value
    if kind == "boolean":
        return {"yes": True, "true": True, "no": False, "false": False}.get(value.lower())
    if kind == "currency":
        return value.upper() if value.upper() in CURRENCIES else None
    if kind == "date":
        try:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                return date.fromisoformat(value).isoformat()
            for pattern in ("%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y"):
                try:
                    return datetime.strptime(value, pattern).date().isoformat()
                except ValueError:
                    pass
        except ValueError:
            pass
        return None
    if kind == "decimal":
        # Currency prefixes are accepted only if explicit; the number remains a candidate.
        value = re.sub(r"^(?:" + "|".join(CURRENCIES) + r")\s+", "", value)
        percent = re.fullmatch(r"([a-z]+) percent \(([0-9]+(?:\.[0-9]+)?)%\)", value.lower())
        if percent:
            words = {
                "one": "1",
                "two": "2",
                "three": "3",
                "four": "4",
                "five": "5",
                "six": "6",
                "seven": "7",
                "eight": "8",
                "nine": "9",
                "ten": "10",
            }
            if words.get(percent[1]) != percent[2]:
                return None
            value = percent[2]
        value = value.removesuffix("%").strip()
        if re.fullmatch(r"-?[0-9]{1,3}(?:,[0-9]{3})+\.[0-9]+", value):
            value = value.replace(",", "")
        if not re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", value):
            return None
        try:
            number = Decimal(value)
            ExactNumeric(20, 6).process_bind_param(number, None)
            return format(number, "f")
        except (InvalidOperation, ValueError):
            return None
    return None
