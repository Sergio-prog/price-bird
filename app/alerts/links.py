from __future__ import annotations

import re
from html import escape
from urllib.parse import quote_plus

from app.alerts.icons import icon, with_icon
from app.db.enums import AssetType
from app.db.models import Asset

GMGN_CHAINS = {
    "arbitrum": "arb",
    "arc": "arc",
    "base": "base",
    "bsc": "bsc",
    "ethereum": "eth",
    "robinhood": "robinhood",
    "solana": "sol",
}
FOMO_CHAINS = {"base", "bsc", "ethereum", "monad", "robinhood", "solana"}


def build_asset_links(asset: Asset) -> dict[str, str]:
    links = {link.kind: link.url for link in asset.links}

    if "tradingview" not in links:
        query = re.sub(r"-PERP$|/", "", asset.symbol) if asset.type == AssetType.CEX_SYMBOL else asset.symbol
        links["tradingview"] = f"https://www.tradingview.com/search/?query={quote_plus(query)}"

    if asset.contract_address and asset.chain and asset.type != AssetType.NFT_COLLECTION:
        chain = asset.chain.lower()
        address = asset.contract_address
        if "dexscreener" not in links:
            links["dexscreener"] = f"https://dexscreener.com/{chain}/{address}"
        if gmgn_chain := GMGN_CHAINS.get(chain):
            links.setdefault("gmgn", f"https://gmgn.ai/{gmgn_chain}/token/{address}")
        if chain in FOMO_CHAINS:
            links.setdefault("fomo", f"https://fomo.family/tokens/{chain}/{address}")
        links.setdefault("coinmarketcap", f"https://coinmarketcap.com/search/?q={quote_plus(address)}")

    return links


def format_links(links: dict[str, str]) -> str:
    if not links:
        return ""
    return " | ".join(
        with_icon(icon(label), f'<a href="{escape(url, quote=True)}">{escape(_link_label(label))}</a>')
        for label, url in links.items()
    )


def _link_label(label: str) -> str:
    labels = {
        "coinmarketcap": "CoinMarketCap",
        "dexscreener": "DexScreener",
        "fomo": "Fomo Trade",
        "gmgn": "GMGN",
        "hyperliquid": "Hyperliquid",
        "opensea": "OpenSea",
        "reservoir": "Reservoir",
        "tradingview": "TradingView",
        "website": "Website",
    }
    return labels.get(label, label.replace("_", " ").title())
