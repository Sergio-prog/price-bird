from datetime import UTC, datetime
from types import SimpleNamespace

from app.preferences import (
    coin_link_keys,
    format_timezone,
    in_quiet_hours,
    quiet_hours,
    shift_hour,
    shift_timezone_offset,
    timezone_offset_minutes,
    toggle_coin_link,
)


def test_overnight_quiet_hours() -> None:
    hours = (22, 7)

    assert in_quiet_hours(datetime(2026, 9, 15, 23, tzinfo=UTC), hours)
    assert in_quiet_hours(datetime(2026, 9, 15, 6, 59, tzinfo=UTC), hours)
    assert not in_quiet_hours(datetime(2026, 9, 15, 7, tzinfo=UTC), hours)


def test_quiet_hours_use_local_timezone_offset() -> None:
    hours = (22, 7)

    assert in_quiet_hours(datetime(2026, 9, 15, 20, tzinfo=UTC), hours, 120)
    assert not in_quiet_hours(datetime(2026, 9, 15, 19, 59, tzinfo=UTC), hours, 120)


def test_invalid_preferences_use_safe_defaults() -> None:
    user = SimpleNamespace(quiet_hours_start=22, quiet_hours_end=22, timezone_offset_minutes=900)

    assert quiet_hours(user) is None
    assert shift_hour(23, 1) == 0
    assert timezone_offset_minutes(user) == 0
    assert shift_timezone_offset(840, 60) == 840
    assert format_timezone(-330) == "UTC-05:30"


def test_coin_links_keep_catalog_order_and_allow_none() -> None:
    assert coin_link_keys(None) == ["dexscreener"]
    assert coin_link_keys(["gmgn", "unknown", "tradingview"]) == ["tradingview", "gmgn"]
    assert toggle_coin_link(["dexscreener"], "tradingview") == ["tradingview", "dexscreener"]
    assert toggle_coin_link(["dexscreener"], "dexscreener") == []
