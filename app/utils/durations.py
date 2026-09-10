from __future__ import annotations

import re
from datetime import timedelta

_UNIT_SECONDS = {
    "s": 1,
    "sec": 1,
    "secs": 1,
    "second": 1,
    "seconds": 1,
    "m": 60,
    "min": 60,
    "mins": 60,
    "minute": 60,
    "minutes": 60,
    "h": 3600,
    "hr": 3600,
    "hrs": 3600,
    "hour": 3600,
    "hours": 3600,
    "d": 86400,
    "day": 86400,
    "days": 86400,
    "w": 604800,
    "wk": 604800,
    "week": 604800,
    "weeks": 604800,
    "mo": 2592000,
    "mon": 2592000,
    "month": 2592000,
    "months": 2592000,
    "y": 31536000,
    "yr": 31536000,
    "yrs": 31536000,
    "year": 31536000,
    "years": 31536000,
}
_DURATION_RE = re.compile(r"^(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>[a-z]+)$")
_UNITS_HINT = "Use a number with a unit: 15m, 24h, 2d, 5w, 3mo, 1y (also 15 min, 5 years)."


def parse_duration(text: str) -> timedelta:
    match = _DURATION_RE.match(text.strip().lower())
    if not match:
        raise ValueError(_UNITS_HINT)
    unit = _UNIT_SECONDS.get(match.group("unit"))
    if unit is None:
        raise ValueError(_UNITS_HINT)
    seconds = float(match.group("value").replace(",", ".")) * unit
    if seconds <= 0:
        raise ValueError("Duration must be positive.")
    return timedelta(seconds=round(seconds))


_FORMAT_UNITS = ((31536000, "y"), (2592000, "mo"), (604800, "w"), (86400, "d"), (3600, "h"), (60, "m"))


def format_duration(seconds: int) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    for unit_seconds, label in _FORMAT_UNITS:
        if seconds >= unit_seconds:
            whole, rest = divmod(seconds, unit_seconds)
            rest -= rest % 60
            return f"{whole}{label} {format_duration(rest)}" if rest else f"{whole}{label}"
    return f"{seconds}s"
