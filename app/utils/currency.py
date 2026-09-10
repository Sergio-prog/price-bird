from __future__ import annotations

USD_ALIASES = {"$", "usd", "usdt", "usdc", "dai", "busd", "fdusd", "tusd", "usde", "pyusd"}
_WRAPPED_BASES = {"ETH", "BNB", "SOL", "AVAX", "MATIC", "POL", "BTC", "FTM", "TRX", "HYPE"}
_CHAIN_NATIVE = {
    "ethereum": "ETH",
    "base": "ETH",
    "arbitrum": "ETH",
    "optimism": "ETH",
    "blast": "ETH",
    "zora": "ETH",
    "polygon": "POL",
    "solana": "SOL",
    "bsc": "BNB",
    "avalanche": "AVAX",
}


def canonical_symbol(symbol: str | None) -> str | None:
    if not symbol:
        return None
    upper = symbol.strip().upper()
    if upper.lower() in USD_ALIASES:
        return "USD"
    if upper.startswith("W") and upper[1:] in _WRAPPED_BASES:
        return upper[1:]
    return upper


def native_symbol_or_none(symbol: str | None) -> str | None:
    canonical = canonical_symbol(symbol)
    return None if canonical in {None, "USD"} else canonical


def chain_native_symbol(chain: str | None) -> str | None:
    return _CHAIN_NATIVE.get((chain or "").lower())
