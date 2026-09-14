from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from app.i18n import LocalizedError
from app.utils.currency import USD_ALIASES, canonical_symbol

_MULTIPLIERS = {"k": Decimal("1e3"), "m": Decimal("1e6"), "b": Decimal("1e9")}
_AMOUNT_RE = re.compile(
    r"^(?P<lead>\$)?\s*(?P<number>\d[\d,]*(?:\.\d+)?|\.\d+)\s*(?P<mult>[kmb](?![a-z]))?\s*(?P<unit>\$|[a-z]{2,10})?$"
)


def parse_amount(text: str) -> tuple[Decimal, str | None]:
    match = _AMOUNT_RE.match(text.strip().lower())
    if not match:
        raise LocalizedError("error-amount-format")
    if match.group("lead") and match.group("unit"):
        raise LocalizedError("error-amount-format")
    try:
        value = Decimal(match.group("number").replace(",", ""))
    except InvalidOperation as exc:
        raise LocalizedError("error-amount-format") from exc
    if multiplier := match.group("mult"):
        value *= _MULTIPLIERS[multiplier]
    if value <= 0 or not value.is_finite():
        raise LocalizedError("error-amount-not-positive")
    unit = match.group("unit") or match.group("lead")
    if unit is None:
        return value, None
    if unit in USD_ALIASES:
        return value, "USD"
    return value, canonical_symbol(unit)


def resolve_currency(unit: str | None, *, default: str, native_symbol: str | None) -> str:
    if unit is None:
        return default
    if unit == "USD":
        return "USD"
    if native_symbol and unit == canonical_symbol(native_symbol):
        return unit
    if native_symbol:
        raise LocalizedError("error-currency-native", symbol=canonical_symbol(native_symbol), unit=unit)
    raise LocalizedError("error-currency-usd", unit=unit)
