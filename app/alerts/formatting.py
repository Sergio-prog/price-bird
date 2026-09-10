from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.db.enums import AlertType


def format_decimal(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def format_percent(value: Decimal, *, signed: bool = False) -> str:
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    text = f"{rounded:.2f}"
    if signed and rounded > 0:
        text = f"+{text}"
    return f"{text}%"


def format_compact(value: Decimal) -> str:
    for limit, suffix in ((Decimal("1e9"), "B"), (Decimal("1e6"), "M"), (Decimal("1e3"), "K")):
        if abs(value) >= limit:
            scaled = (value / limit).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            return f"{format_decimal(scaled)}{suffix}"
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
    labels = {
        "up": "Up",
        "down": "Down",
        "both": "Up or down",
    }
    return labels.get(value, value.replace("_", " ").capitalize())


def format_direction_arrows(value: str) -> str:
    return {"up": "↑", "down": "↓"}.get(value, "↑↓")
