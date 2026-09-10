from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.alerts.formatting import format_compact_usd, format_cooldown, format_threshold
from app.bot.handlers.alert_settings import _next_option, alert_settings_view


def _alert(**overrides):
    values = {
        "id": 7,
        "type": "percent_change",
        "threshold_value": Decimal("10.000000000000000000000000000000000000"),
        "baseline_price": Decimal("0.500000000000000000000000000000000000"),
        "direction": "both",
        "status": "active",
        "repeat": True,
        "cooldown_seconds": 900,
        "expires_at": None,
        "note": None,
        "asset": SimpleNamespace(symbol="MEME", type="token", chain="solana"),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_alert_settings_view_formats_values() -> None:
    text, markup = alert_settings_view(_alert())

    assert "Threshold: 10.00%" in text
    assert "Baseline: $0.5" in text
    assert "Cooldown: 15 min" in text
    assert "Direction: Up or down" in text
    assert "Expires: never" in text
    labels = [button.text for row in markup.inline_keyboard for button in row]
    assert labels[:3] == ["⏸ Pause", "One time: ❌", "Cooldown: 15 min"]
    assert "Direction: ↑↓" in labels
    assert "🗑 Delete" in labels
    assert markup.inline_keyboard[-1][0].callback_data == "menu:alerts"


def test_alert_settings_view_reflects_toggled_state() -> None:
    text, markup = alert_settings_view(
        _alert(
            type="mcap_above",
            threshold_value=Decimal("1500000"),
            status="paused",
            repeat=False,
            expires_at=datetime(2026, 9, 17, 12, 0, tzinfo=UTC),
            note="<b>",
        )
    )

    assert "Threshold: $1500000" in text
    assert "Status: ⏸ paused" in text
    assert "Expires: 2026-09-17 12:00 UTC" in text
    assert "Note: &lt;b&gt;" in text
    labels = [button.text for row in markup.inline_keyboard for button in row]
    assert labels[:2] == ["▶️ Resume", "One time: ✅"]
    assert "Direction: ↑↓" not in labels
    assert "⏳ Clear expiry" in labels


def test_formatting_helpers() -> None:
    assert format_threshold("percent_change", Decimal("12.5")) == "12.50%"
    assert format_threshold("price_above", Decimal("100.10")) == "$100.1"
    assert format_compact_usd(Decimal("999")) == "$999"
    assert format_compact_usd(Decimal("12345")) == "$12.35K"
    assert format_cooldown(60) == "1 min"
    assert format_cooldown(86400) == "24 h"
    assert _next_option([60, 900, 3600], 3600) == 60
    assert _next_option([60, 900, 3600], 42) == 900
