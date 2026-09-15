from __future__ import annotations

from datetime import datetime, timedelta

COIN_LINKS = {
    "tradingview": "TradingView",
    "dexscreener": "DexScreener",
    "gmgn": "GMGN",
    "fomo": "Fomo Trade",
    "coinmarketcap": "CoinMarketCap",
}
DEFAULT_COIN_LINK = "dexscreener"
DEFAULT_QUIET_HOURS = (22, 7)
MIN_TIMEZONE_OFFSET_MINUTES = -12 * 60
MAX_TIMEZONE_OFFSET_MINUTES = 14 * 60


def coin_link_key(value: str | None) -> str:
    return value if value in COIN_LINKS else DEFAULT_COIN_LINK


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
