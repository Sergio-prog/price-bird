from __future__ import annotations

from app.providers.parsing import format_price


def normalize_chain(chain: str) -> str:
    mapping = {
        "ethereum": "ethereum",
        "solana": "solana",
        "bsc": "bsc",
        "arbitrum": "arbitrum",
        "unichain": "unichain",
    }
    return mapping.get(chain.lower(), chain.lower())


def format_pair(base_symbol: str | None, quote_symbol: str | None) -> str | None:
    if not base_symbol or not quote_symbol:
        return None
    return f"{base_symbol}/{quote_symbol}"


__all__ = ["format_pair", "format_price", "normalize_chain"]
