from __future__ import annotations

from datetime import datetime, timedelta

COIN_LINKS = {
    "tradingview": "TradingView",
    "dexscreener": "DexScreener",
    "gmgn": "GMGN",
    "fomo": "Fomo Trade",
    "coinmarketcap": "CoinMarketCap",
    "explorer": "Explorer",
    "pons": "Pons",
}
DEFAULT_COIN_LINKS = ("dexscreener",)
DEFAULT_QUIET_HOURS = (22, 7)
MIN_TIMEZONE_OFFSET_MINUTES = -12 * 60
MAX_TIMEZONE_OFFSET_MINUTES = 14 * 60


def coin_link_keys(value) -> list[str]:
    selected = DEFAULT_COIN_LINKS if value is None else value
    return [key for key in COIN_LINKS if key in selected]


def toggle_coin_link(value, key: str) -> list[str]:
    selected = set(coin_link_keys(value)) ^ {key}
    return [item for item in COIN_LINKS if item in selected]


def quiet_hours(user) -> tuple[int, int] | None:
    start = getattr(user, "quiet_hours_start", None)
    end = getattr(user, "quiet_hours_end", None)
    if start is None or end is None or not 0 <= start < 24 or not 0 <= end < 24 or start == end:
        return None
    return start, end


def timezone_offset_minutes(user) -> int:
    value = getattr(user, "timezone_offset_minutes", 0)
    if not isinstance(value, int) or not MIN_TIMEZONE_OFFSET_MINUTES <= value <= MAX_TIMEZONE_OFFSET_MINUTES:
        return 0
    return value


def format_timezone(offset_minutes: int) -> str:
    sign = "+" if offset_minutes >= 0 else "-"
    hours, minutes = divmod(abs(offset_minutes), 60)
    return f"UTC{sign}{hours:02}:{minutes:02}"


def shift_timezone_offset(offset_minutes: int, delta_minutes: int) -> int:
    return max(MIN_TIMEZONE_OFFSET_MINUTES, min(MAX_TIMEZONE_OFFSET_MINUTES, offset_minutes + delta_minutes))


def in_quiet_hours(at: datetime, hours: tuple[int, int] | None, offset_minutes: int = 0) -> bool:
    if hours is None:
        return False
    start, end = hours
    hour = (at + timedelta(minutes=offset_minutes)).hour
    return start <= hour < end if start < end else hour >= start or hour < end


def shift_hour(hour: int, delta: int) -> int:
    return (hour + delta) % 24
