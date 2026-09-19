from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.db.enums import AlertType
from app.i18n import t

_MAX_FRACTION_DIGITS = 18
VENUE_LABELS = {"bsc": "BSC", "okx": "OKX", "ton": "TON", "opensea": "OpenSea"}


def _trim(text: str) -> str:
    return text.rstrip("0").rstrip(".") if "." in text else text


def _fraction_digits(value: Decimal) -> int:
    magnitude = abs(value)
    if magnitude >= 1000:
        return 2
    if magnitude >= 1:
        return 4
    return min(_MAX_FRACTION_DIGITS, 3 - magnitude.adjusted())


def format_decimal(value: Decimal, *, grouped: bool = True) -> str:
    if not value.is_finite():
        return str(value)
    if value == 0:
        return "0"
    digits = _fraction_digits(value)
    rounded = value.quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
    if rounded == 0:
        return "0"
    text = format(rounded, ",f" if grouped else "f")
    keep_cents = digits == 2 and rounded != rounded.to_integral_value()
    return text if keep_cents else _trim(text)


def format_percent(value: Decimal, *, signed: bool = False) -> str:
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    text = _trim(f"{rounded:.2f}")
    if signed and rounded > 0:
        text = f"+{text}"
    return f"{text}%"


def format_compact(value: Decimal) -> str:
    for limit, suffix in ((Decimal("1e9"), "B"), (Decimal("1e6"), "M"), (Decimal("1e3"), "K")):
        if abs(value) >= limit:
            scaled = (value / limit).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return f"{_trim(f'{scaled:.2f}')}{suffix}"
    return format_decimal(value)


def format_amount(value: Decimal, currency: str = "USD", *, compact: bool = False) -> str:
    text = format_compact(value) if compact else format_decimal(value)
    return f"${text}" if currency == "USD" else f"{text} {currency}"


def format_compact_usd(value: Decimal) -> str:
    return format_amount(value, compact=True)


def format_threshold(alert_type: str, value: Decimal, currency: str = "USD", *, compact: bool = False) -> str:
    if alert_type == AlertType.PERCENT_CHANGE.value:
        return format_percent(value)
    return format_amount(value, currency, compact=compact)


def format_direction(value: str) -> str:
    if value in {"up", "down", "both"}:
        return t(f"direction-{value}")
    return value.replace("_", " ").capitalize()


def format_direction_arrows(value: str) -> str:
    return {"up": "↑", "down": "↓"}.get(value, "↑↓")


def format_change(percent: Decimal, direction: str | None = None) -> str:
    arrow = format_direction_arrows(direction or ("down" if percent < 0 else "up"))
    return f"{arrow} {format_percent(percent, signed=True)}"


def venue_label(venue: str) -> str:
    return VENUE_LABELS.get(venue.lower(), venue.replace("_", " ").title())
