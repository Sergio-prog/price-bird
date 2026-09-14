from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.db.enums import AlertDirection, AlertType, AssetType
from app.i18n import LocalizedError
from app.utils.amounts import parse_amount

_PERCENT_RE = re.compile(r"^(?P<value>\d+(?:\.\d+)?)%$")
_THRESHOLD_RE = re.compile(r"^(?P<op>[<>])\s*(?P<amount>.+)$")


@dataclass(frozen=True)
class ParsedAlertCommand:
    query: str
    asset_type_hint: AssetType | None
    alert_type: AlertType
    threshold_value: Decimal
    direction: AlertDirection
    threshold_currency: str | None = None


def parse_alert_command(text: str) -> ParsedAlertCommand:
    body = text.removeprefix("/alert").strip()
    if not body:
        raise LocalizedError("error-alert-usage")

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
        operator_index = next((index for index, part in enumerate(parts) if part in {">", "<"}), None)
        if operator_index:
            query = " ".join(parts[:operator_index]).strip()
            condition_parts = parts[operator_index:]

    if not query or not condition_parts:
        raise LocalizedError("error-alert-missing-parts")

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
        value, currency = parse_amount(threshold_match.group("amount"))
        return ParsedAlertCommand(
            query=query,
            asset_type_hint=asset_type_hint,
            alert_type=AlertType.PRICE_ABOVE if op == ">" else AlertType.PRICE_BELOW,
            threshold_value=value,
            direction=AlertDirection.UP if op == ">" else AlertDirection.DOWN,
            threshold_currency=currency,
        )

    raise LocalizedError("error-alert-condition")


def _decimal(value: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise LocalizedError("error-invalid-number", value=value) from exc
    if parsed <= 0:
        raise LocalizedError("error-amount-not-positive")
    return parsed
