from __future__ import annotations

from decimal import Decimal

import aiohttp

from app.core.config import settings
from app.db.enums import AssetType
from app.db.models import Asset
from app.providers.base import AssetCandidate, PriceQuote
from app.providers.dexscreener_mapping import format_pair, format_price, normalize_chain


class DexScreenerProvider:
    name = "dexscreener"
    base_url = "https://api.dexscreener.com/latest/dex"

    async def search_assets(self, query: str, *, nft: bool = False) -> list[AssetCandidate]:
        if nft:
            return []
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=settings.provider_timeout_seconds)) as session:
            async with session.get(f"{self.base_url}/search", params={"q": query}) as response:
                response.raise_for_status()
                payload = await response.json()

        candidates: list[AssetCandidate] = []
        for pair in payload.get("pairs") or []:
            base = pair.get("baseToken") or {}
            quote = pair.get("quoteToken") or {}
            address = base.get("address")
            chain = pair.get("chainId")
            symbol = base.get("symbol")
            if not address or not chain or not symbol:
                continue
            provider_asset_id = f"{chain}:{address}"
            candidates.append(
                AssetCandidate(
                    type=AssetType.TOKEN,
                    provider=self.name,
                    provider_asset_id=provider_asset_id,
                    chain=normalize_chain(chain),
                    symbol=symbol,
                    name=base.get("name"),
                    contract_address=address,
                    metadata={
                        "pair_address": pair.get("pairAddress"),
                        "dex_id": pair.get("dexId"),
                        "pair": format_pair(base.get("symbol"), quote.get("symbol")),
                        "price_usd": format_price(pair.get("priceUsd")),
                    },
                    links={"dexscreener": pair.get("url")} if pair.get("url") else {},
                )
            )
        return candidates[:10]

    async def get_price(self, asset: Asset) -> PriceQuote:
        chain, address = asset.provider_asset_id.split(":", 1)
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=settings.provider_timeout_seconds)) as session:
            async with session.get(f"{self.base_url}/tokens/{address}") as response:
                response.raise_for_status()
                payload = await response.json()
        pairs = [pair for pair in payload.get("pairs") or [] if pair.get("chainId") == chain]
        if not pairs:
            raise LookupError(f"No DexScreener pair for {asset.symbol}")
        best = max(pairs, key=lambda pair: float((pair.get("liquidity") or {}).get("usd") or 0))
        return PriceQuote(price_usd=Decimal(str(best["priceUsd"])), source=self.name, raw=best)
