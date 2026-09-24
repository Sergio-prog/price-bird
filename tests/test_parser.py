from decimal import Decimal

import pytest

from app.alerts.parser import parse_alert_command
from app.db.enums import AlertDirection, AlertType, AssetType


def test_percent_alert_is_bidirectional() -> None:
    parsed = parse_alert_command("/alert BTC 10%")

    assert parsed.query == "BTC"
    assert parsed.alert_type == AlertType.PERCENT_CHANGE
    assert parsed.direction == AlertDirection.BOTH
    assert parsed.threshold_value == Decimal("10")


def test_threshold_above() -> None:
    parsed = parse_alert_command("/alert ETH > 70000")

    assert parsed.query == "ETH"
    assert parsed.alert_type == AlertType.PRICE_ABOVE
    assert parsed.direction == AlertDirection.UP


def test_nft_floor_percent() -> None:
    parsed = parse_alert_command("/alert BAYC floor 10%")

    assert parsed.query == "BAYC"
    assert parsed.asset_type_hint == AssetType.NFT_COLLECTION


def test_invalid_condition() -> None:
    with pytest.raises(ValueError):
        parse_alert_command("/alert BTC soon")


def test_threshold_with_suffix_and_currency() -> None:
    parsed = parse_alert_command("/alert BTC > 100k")
    assert parsed.threshold_value == Decimal("100000")
    assert parsed.threshold_currency is None

    parsed = parse_alert_command("/alert milady floor < 0.8 ETH")
    assert parsed.query == "milady"
    assert parsed.asset_type_hint == AssetType.NFT_COLLECTION
    assert parsed.alert_type == AlertType.PRICE_BELOW
    assert parsed.threshold_value == Decimal("0.8")
    assert parsed.threshold_currency == "ETH"

    parsed = parse_alert_command("/alert pudgy penguins > $50000")
    assert parsed.query == "pudgy penguins"
    assert parsed.threshold_currency == "USD"


def test_signed_percent_sets_direction() -> None:
    assert parse_alert_command("/alert SOL +5%").direction == AlertDirection.UP
    assert parse_alert_command("/alert SOL -5%").direction == AlertDirection.DOWN


def test_market_cap_suffix_selects_market_cap_alert() -> None:
    parsed = parse_alert_command("/alert PEPE > 17m mc")

    assert parsed.query == "PEPE"
    assert parsed.alert_type == AlertType.MCAP_ABOVE
    assert parsed.threshold_value == Decimal("17000000")
    assert parse_alert_command("/alert PEPE < 5b mcap").alert_type == AlertType.MCAP_BELOW
