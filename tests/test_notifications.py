from decimal import Decimal
from types import SimpleNamespace

from app.db.enums import AssetType
from app.notifications import render_alert_message


def test_render_alert_message_shows_nft_native_and_usd_floor() -> None:
    event = SimpleNamespace(
        direction="up",
        percent_change=Decimal("12.5"),
        alert=SimpleNamespace(
            baseline_price=Decimal("3000"),
            asset=SimpleNamespace(
                symbol="BAYC",
                type=AssetType.NFT_COLLECTION.value,
                chain="ethereum",
                contract_address=None,
                links=[],
            ),
        ),
        snapshot=SimpleNamespace(
            price_usd=Decimal("3600"),
            price_native=Decimal("1.2"),
            native_symbol="ETH",
            source="opensea",
        ),
    )

    message = render_alert_message(event)

    assert "Alert triggered for <b>BAYC</b>" in message
    assert "Direction: Up" in message
    assert "Current: 1.2 ETH ($3600)" in message
    assert "Change: +12.50%" in message
    assert "Source: opensea" in message
    assert '<a href="https://www.tradingview.com/search/?query=BAYC">TradingView</a>' in message
