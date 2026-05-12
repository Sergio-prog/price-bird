from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.db.enums import AlertDirection, AlertType, AssetType

_PERCENT_RE = re.compile(r"^(?P<value>\d+(?:\.\d+)?)%$")
_THRESHOLD_RE = re.compile(r"^(?P<op>[<>])\s*(?P<value>\d+(?:\.\d+)?)$")


@dataclass(frozen=True)
class ParsedAlertCommand:
    query: str
    asset_type_hint: AssetType | None
    alert_type: AlertType
    threshold_value: Decimal
    direction: AlertDirection


def parse_alert_command(text: str) -> ParsedAlertCommand:
    body = text.removeprefix("/alert").strip()
    if not body:
        raise ValueError("Usage: /alert BTC 10% or /alert ETH > 70000")

    parts = body.split()
    floor = "floor" in [part.lower() for part in parts]
    if floor:
        floor_index = [part.lower() for part in parts].index("floor")
        query = " ".join(parts[:floor_index]).strip()
        condition_parts = parts[floor_index + 1 :]
        asset_type_hint = AssetType.NFT_COLLECTION
    else:
        query = " ".join(parts[:-1]).strip()
        condition_parts = parts[-1:]
        asset_type_hint = None
        if len(parts) >= 3 and parts[-2] in {">", "<"}:
            query = " ".join(parts[:-2]).strip()
            condition_parts = parts[-2:]

    if not query or not condition_parts:
        raise ValueError("Missing asset query or alert condition")

    condition = " ".join(condition_parts).strip()
    percent_match = _PERCENT_RE.match(condition)
    if percent_match:
        return ParsedAlertCommand(
            query=query,
            asset_type_hint=asset_type_hint,
            alert_type=AlertType.PERCENT_CHANGE,
            threshold_value=_decimal(percent_match.group("value")),
            direction=AlertDirection.BOTH,
        )

    threshold_match = _THRESHOLD_RE.match(condition)
    if threshold_match:
        op = threshold_match.group("op")
        return ParsedAlertCommand(
            query=query,
            asset_type_hint=asset_type_hint,
            alert_type=AlertType.PRICE_ABOVE if op == ">" else AlertType.PRICE_BELOW,
            threshold_value=_decimal(threshold_match.group("value")),
            direction=AlertDirection.UP if op == ">" else AlertDirection.DOWN,
        )

    raise ValueError("Condition must be a percent like 10% or threshold like > 70000")


def _decimal(value: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid number: {value}") from exc
    if parsed <= 0:
        raise ValueError("Alert value must be positive")
    return parsed
