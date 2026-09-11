from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.alerts.formatting import format_compact_usd, format_threshold
from app.bot.handlers.alert_settings import _next_option, _parse_bounded_duration, alert_settings_view
from app.utils.durations import format_duration, parse_duration


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

    assert "Threshold: 10%" in text
    assert "Baseline: $0.5" in text
    assert "Cooldown: 15m" in text
    assert "Direction: Up or down" in text
    assert "Expires: never" in text
    labels = [button.text for row in markup.inline_keyboard for button in row]
    assert labels[:3] == ["⏸ Pause", "One time: ❌", "⏱ Cooldown: 15m"]
    assert "⏳ Expires: never" in labels
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
            expires_at=datetime.now(UTC) + timedelta(days=3, seconds=5),
            note="<b>",
        )
    )

    assert "Threshold: $1,500,000" in text
    assert "Status: ⏸ paused" in text
    assert "(in 3d)" in text
    assert "Note: &lt;b&gt;" in text
    labels = [button.text for row in markup.inline_keyboard for button in row]
    assert labels[:2] == ["▶️ Resume", "One time: ✅"]
    assert "Direction: ↑↓" not in labels
    assert "⏳ Expires: in 3d" in labels


def test_formatting_helpers() -> None:
    assert format_threshold("percent_change", Decimal("12.5")) == "12.5%"
    assert format_threshold("price_above", Decimal("100.10")) == "$100.1"
    assert format_threshold("price_above", Decimal("2473.203834539996094045")) == "$2,473.20"
    assert format_threshold("price_above", Decimal("0.9497819999999985"), "ETH") == "0.9498 ETH"
    assert format_threshold("price_above", Decimal("0.00001234567")) == "$0.00001235"
    assert format_compact_usd(Decimal("999")) == "$999"
    assert format_compact_usd(Decimal("12345")) == "$12.35K"
    assert format_compact_usd(Decimal("5000000000")) == "$5B"
    assert _next_option([60, 900, 3600], 3600) == 60
    assert _next_option([60, 900, 3600], 42) == 900


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("24h", timedelta(hours=24)),
        ("2d", timedelta(days=2)),
        ("5w", timedelta(weeks=5)),
        ("5m", timedelta(minutes=5)),
        ("3mo", timedelta(days=90)),
        ("1y", timedelta(days=365)),
        ("15 min", timedelta(minutes=15)),
        ("15 minutes", timedelta(minutes=15)),
        ("5 years", timedelta(days=5 * 365)),
        ("1.5h", timedelta(minutes=90)),
        (" 2 Days ", timedelta(days=2)),
    ],
)
def test_parse_duration(text: str, expected: timedelta) -> None:
    assert parse_duration(text) == expected


@pytest.mark.parametrize("text", ["", "abc", "5", "5 lightyears", "0h", "-2d"])
def test_parse_duration_rejects_invalid(text: str) -> None:
    with pytest.raises(ValueError):
        parse_duration(text)


def test_format_duration() -> None:
    assert format_duration(60) == "1m"
    assert format_duration(900) == "15m"
    assert format_duration(86400) == "1d"
    assert format_duration(90000) == "1d 1h"
    assert format_duration(90059) == "1d 1h"
    assert format_duration(691200) == "1w 1d"
    assert format_duration(2592000) == "1mo"
    assert format_duration(31536000) == "1y"
    assert format_duration(45) == "45s"


def test_bounded_duration_limits() -> None:
    assert _parse_bounded_duration("2h", timedelta(days=1)) == timedelta(hours=2)
    with pytest.raises(ValueError, match="at least 1 minute"):
        _parse_bounded_duration("30s", timedelta(days=1))
    with pytest.raises(ValueError, match="at most 1d"):
        _parse_bounded_duration("2d", timedelta(days=1))
