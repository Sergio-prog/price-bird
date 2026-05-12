from __future__ import annotations

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
    return "\n".join(f"{label.title()}: {url}" for label, url in links.items())
