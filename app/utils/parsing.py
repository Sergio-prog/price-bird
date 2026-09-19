from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

_EVM_ADDRESS_RE = re.compile(r"0x[0-9a-fA-F]{40}")
_ONCHAIN_ADDRESS_RE = re.compile(r"0x[0-9a-fA-F]{40,64}|[1-9A-HJ-NP-Za-km-z]{32,44}")


def is_evm_address(text: str) -> bool:
    return bool(_EVM_ADDRESS_RE.fullmatch(text.strip()))


def is_onchain_address(text: str) -> bool:
    return bool(_ONCHAIN_ADDRESS_RE.fullmatch(text.strip()))


def to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def format_price(value: object) -> str | None:
    price = to_decimal(value)
    if price is None:
        return None
    if price >= Decimal("1"):
        return f"{price.normalize():f}"
    return f"{price:.8f}".rstrip("0").rstrip(".")
