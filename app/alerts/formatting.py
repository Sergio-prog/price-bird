from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def format_decimal(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def format_percent(value: Decimal, *, signed: bool = False) -> str:
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    text = f"{rounded:.2f}"
    if signed and rounded > 0:
        text = f"+{text}"
    return f"{text}%"


def format_direction(value: str) -> str:
    labels = {
        "up": "Up",
        "down": "Down",
        "both": "Up or down",
    }
    return labels.get(value, value.replace("_", " ").capitalize())
