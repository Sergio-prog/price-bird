from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.providers.base import PriceQuote
from app.utils.currency import native_symbol_or_none
from app.utils.parsing import format_price


def normalize_chain(chain: str) -> str:
    mapping = {
        "ethereum": "ethereum",
        "solana": "solana",
        "bsc": "bsc",
        "arbitrum": "arbitrum",
        "unichain": "unichain",
        "arc": "arc",
    }
    return mapping.get(chain.lower(), chain.lower())


def format_pair(base_symbol: str | None, quote_symbol: str | None) -> str | None:
    if not base_symbol or not quote_symbol:
        return None
    return f"{base_symbol}/{quote_symbol}"


def address_key(address: str) -> str:
    return address.lower() if address.startswith("0x") else address


def pairs_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [pair for pair in payload if isinstance(pair, dict)]
    if isinstance(payload, dict):
        return [pair for pair in payload.get("pairs") or [] if isinstance(pair, dict)]
    return []


def best_pair(pairs: list[dict[str, Any]], chain: str, address: str) -> dict[str, Any] | None:
    wanted = address_key(address)
    matching = [
        pair
        for pair in pairs
        if pair.get("chainId") == chain
        and address_key((pair.get("baseToken") or {}).get("address") or "") == wanted
        and pair.get("priceUsd") is not None
    ]
    if not matching:
        return None
    return max(matching, key=lambda pair: float((pair.get("liquidity") or {}).get("usd") or 0))


def quote_from_pair(pair: dict[str, Any], source: str) -> PriceQuote:
    native_symbol = native_symbol_or_none((pair.get("quoteToken") or {}).get("symbol"))
    price_native = pair.get("priceNative")
    has_native = bool(native_symbol) and price_native is not None
    return PriceQuote(
        price_usd=Decimal(str(pair["priceUsd"])),
        source=source,
        raw=pair,
        market_cap_usd=Decimal(str(pair["marketCap"])) if pair.get("marketCap") is not None else None,
        price_native=Decimal(str(price_native)) if has_native else None,
        native_symbol=native_symbol if has_native else None,
    )


__all__ = [
    "address_key",
    "best_pair",
    "format_pair",
    "format_price",
    "normalize_chain",
    "pairs_from_payload",
    "quote_from_pair",
]
