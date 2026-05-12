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
