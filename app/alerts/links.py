from __future__ import annotations

from html import escape
from urllib.parse import quote_plus

from app.db.models import Asset


def build_asset_links(asset: Asset) -> dict[str, str]:
    links = {link.kind: link.url for link in asset.links}

    if "tradingview" not in links:
        links["tradingview"] = f"https://www.tradingview.com/search/?query={quote_plus(asset.symbol)}"

    if asset.contract_address and asset.chain:
        chain = asset.chain.lower()
        if "dexscreener" not in links:
            links["dexscreener"] = f"https://dexscreener.com/{chain}/{asset.contract_address}"
        if "axiom" not in links and chain in {"ethereum", "solana", "bsc", "base", "arbitrum", "unichain"}:
            links["axiom"] = f"https://axiom.trade/t/{asset.contract_address}"

    return links


def format_links(links: dict[str, str]) -> str:
    if not links:
        return ""
    return " | ".join(f'<a href="{escape(url, quote=True)}">{escape(_link_label(label))}</a>' for label, url in links.items())


def _link_label(label: str) -> str:
    labels = {
        "axiom": "Axiom",
        "dexscreener": "DexScreener",
        "opensea": "OpenSea",
        "reservoir": "Reservoir",
        "tradingview": "TradingView",
        "website": "Website",
    }
    return labels.get(label, label.replace("_", " ").title())
