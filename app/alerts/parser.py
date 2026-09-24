from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from app.db.enums import AlertDirection, AlertType, AssetType
from app.i18n import LocalizedError
from app.utils.amounts import parse_amount, parse_percent, split_market_cap_suffix

PERCENT_DIRECTIONS = {None: AlertDirection.BOTH, "+": AlertDirection.UP, "-": AlertDirection.DOWN}
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
    if condition.endswith("%"):
        value, sign = parse_percent(condition)
        return ParsedAlertCommand(
            query=query,
            asset_type_hint=asset_type_hint,
            alert_type=AlertType.PERCENT_CHANGE,
            threshold_value=value,
            direction=PERCENT_DIRECTIONS[sign],
        )

    threshold_match = _THRESHOLD_RE.match(condition)
    if threshold_match:
        above = threshold_match.group("op") == ">"
        amount, market_cap = split_market_cap_suffix(threshold_match.group("amount"))
        value, currency = parse_amount(amount)
        return ParsedAlertCommand(
            query=query,
            asset_type_hint=asset_type_hint,
            alert_type=threshold_alert_type(above=above, market_cap=market_cap),
            threshold_value=value,
            direction=AlertDirection.UP if above else AlertDirection.DOWN,
            threshold_currency=currency,
        )

    raise LocalizedError("error-alert-condition")


def threshold_alert_type(*, above: bool, market_cap: bool) -> AlertType:
    if market_cap:
        return AlertType.MCAP_ABOVE if above else AlertType.MCAP_BELOW
    return AlertType.PRICE_ABOVE if above else AlertType.PRICE_BELOW
