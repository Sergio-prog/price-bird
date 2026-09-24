from __future__ import annotations

from app.core.config import settings
from app.db.enums import AssetType

CUSTOM_EMOJI_IDS = {
    "base": "5918154691220348997",
    "ethereum": "5915524517672787258",
    "bsc": "5917865665691131684",
    "solana": "5917864617719111990",
    "avalanche": "5915726746207919052",
    "hyperliquid": "5918129338028400627",
    "arbitrum": "5918118553365519861",
    "sonic": "5917854056394530693",
    "okx": "5917937121062036309",
    "unichain": "5917976630466191419",
    "monad": "5917962448484178950",
    "megaeth": "5917816007279255246",
    "robinhood": "5892987424111336299",
    "story": "5918212303911657096",
    "uniswap": "5918267391162195125",
    "pancakeswap": "5918205990309731670",
    "pumpfun": "5918021929486261481",
    "pumpswap": "5918117346479708825",
    "raydium": "5918188076001140398",
    "meteora": "5920111486910340104",
    "orca": "5917927693608819271",
    "moonshot": "5917954975241084901",
    "fourmeme": "5918230368544103449",
    "curve": "5918186272114875230",
    "dexscreener": "5917923733648973619",
    "explorer": "5917989854670495706",
    "etherscan": "5917989854670495706",
    "basescan": "5917998972886064369",
    "bscscan": "5917834668912155609",
    "arbiscan": "5917774200067595759",
    "snowscan": "5917955950198660973",
    "solscan": "5918250292897394993",
    "robinscan": "6021610467582025589",
}
FALLBACK_EMOJI = {
    "ethereum": "💎",
    "bsc": "🟠",
    "solana": "🟣",
    "base": "🔵",
    "avalanche": "🔺",
    "hyperliquid": "💠",
    "story": "⚪",
    "okx": "⚫",
    "monad": "🟪",
    "arbitrum": "🔷",
    "robinhood": "🟢",
    "ton": "🔹",
    "tron": "🔴",
    "sui": "💧",
    "sonic": "⚪",
    "unichain": "🦄",
    "megaeth": "Ⓜ️",
    "dexscreener": "🦅",
    "explorer": "🔍",
    "etherscan": "🔍",
    "basescan": "🔍",
    "bscscan": "🔍",
    "arbiscan": "🔍",
    "snowscan": "🔍",
    "solscan": "🔍",
    "robinscan": "🔍",
    "sonicscan": "🔍",
    "uniscan": "🔍",
    "tradingview": "📈",
    "pons": "🅿️",
    "gmgn": "🐸",
    "coinmarketcap": "📊",
    "fomo": "🔥",
    "opensea": "🌊",
    "uniswap": "🦄",
    "pancakeswap": "🥞",
    "pumpfun": "💊",
    "pumpswap": "💊",
    "raydium": "🟣",
    "meteora": "☄️",
    "orca": "🐋",
    "moonshot": "🌙",
    "fourmeme": "🍀",
    "curve": "🌈",
}
ALIASES = {
    "binance": "bsc",
    "bnb": "bsc",
    "eth": "ethereum",
    "sol": "solana",
    "arb": "arbitrum",
    "avax": "avalanche",
    "hyperevm": "hyperliquid",
    "xlayer": "okx",
    "pump": "pumpfun",
    "pumpfunamm": "pumpswap",
    "four": "fourmeme",
}
DEX_LABELS = {
    "pumpfun": "Pump.fun",
    "pumpswap": "PumpSwap",
    "raydium": "Raydium",
    "meteora": "Meteora",
    "orca": "Orca",
    "uniswap": "Uniswap",
    "pancakeswap": "PancakeSwap",
    "fourmeme": "four.meme",
    "moonshot": "Moonshot",
    "curve": "Curve",
}


def icon(key: str | None) -> str:
    name = (key or "").lower()
    name = ALIASES.get(name, name)
    fallback = FALLBACK_EMOJI.get(name)
    if fallback is None:
        return ""
    emoji_id = CUSTOM_EMOJI_IDS.get(name)
    if emoji_id is None or not settings.custom_emoji_enabled:
        return fallback
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


def asset_icon(kind: str | None, chain: str | None, exchange: str | None) -> str:
    if kind == AssetType.CEX_SYMBOL.value:
        return icon(exchange)
    return icon(chain)


def dex_label(dex_id: str) -> str:
    return DEX_LABELS.get(dex_id.lower(), dex_id.replace("_", " ").replace("-", " ").title())


def with_icon(key_icon: str, text: str) -> str:
    return f"{key_icon} {text}" if key_icon else text


def plain_icon(key: str | None) -> str:
    name = (key or "").lower()
    return FALLBACK_EMOJI.get(ALIASES.get(name, name), "")
