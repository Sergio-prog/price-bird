from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def format_price(value: object) -> str | None:
    price = to_decimal(value)
    if price is None:
        return None
    if price >= Decimal("1"):
        return f"{price.normalize():f}"
    return f"{price:.8f}".rstrip("0").rstrip(".")
