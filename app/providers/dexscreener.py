from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Sequence

from app.core.config import settings
from app.db.enums import AssetType
from app.db.models import Asset
from app.providers.base import AssetCandidate, PriceQuote
from app.providers.dexscreener_mapping import (
    address_key,
    best_pair,
    format_pair,
    format_price,
    normalize_chain,
    pairs_from_payload,
    quote_from_pair,
)
from app.utils.currency import native_symbol_or_none
from app.utils.http import HttpClient
from app.utils.ratelimit import ProviderThrottle

logger = logging.getLogger(__name__)

TOKEN_BATCH_SIZE = 30


def split_asset_id(provider_asset_id: str) -> tuple[str, str]:
    chain, address = provider_asset_id.split(":", 1)
    return chain, address


class DexScreenerProvider:
    name = "dexscreener"
    base_url = "https://api.dexscreener.com"

    def __init__(self, *, client: HttpClient | None = None) -> None:
        self.client = client or HttpClient(
            throttle=ProviderThrottle(self.name, rate_per_minute=settings.dexscreener_requests_per_minute)
        )

    async def search_assets(self, query: str, *, nft: bool = False) -> list[AssetCandidate]:
        if nft:
            return []
        payload = await self.client.get_json(f"{self.base_url}/latest/dex/search", params={"q": query})

        candidates: list[AssetCandidate] = []
        for pair in pairs_from_payload(payload):
            base = pair.get("baseToken") or {}
            quote = pair.get("quoteToken") or {}
            address = base.get("address")
            chain = pair.get("chainId")
            symbol = base.get("symbol")
            if not address or not chain or not symbol:
                continue
            candidates.append(
                AssetCandidate(
                    type=AssetType.TOKEN,
                    provider=self.name,
                    provider_asset_id=f"{chain}:{address}",
                    chain=normalize_chain(chain),
                    symbol=symbol,
                    name=base.get("name"),
                    contract_address=address,
                    metadata={
                        "pair_address": pair.get("pairAddress"),
                        "dex_id": pair.get("dexId"),
                        "pair": format_pair(base.get("symbol"), quote.get("symbol")),
                        "price_usd": format_price(pair.get("priceUsd")),
                        "native_symbol": native_symbol_or_none(quote.get("symbol")),
                    },
                    links={"dexscreener": pair.get("url")} if pair.get("url") else {},
                )
            )
        return candidates[:10]

    async def get_price(self, asset: Asset) -> PriceQuote:
        chain, address = split_asset_id(asset.provider_asset_id)
        best = best_pair(await self._fetch_pairs(chain, [address]), chain, address)
        if best is None:
            raise LookupError(f"No DexScreener pair for {asset.symbol}")
        return quote_from_pair(best, self.name)

    async def get_prices(self, assets: Sequence[Asset]) -> dict[int, PriceQuote]:
        quotes: dict[int, PriceQuote] = {}
        grouped: dict[str, list[Asset]] = defaultdict(list)
        for asset in assets:
            grouped[split_asset_id(asset.provider_asset_id)[0]].append(asset)
        for chain, items in grouped.items():
            by_address: dict[str, list[Asset]] = defaultdict(list)
            for asset in items:
                by_address[split_asset_id(asset.provider_asset_id)[1]].append(asset)
            addresses = sorted(by_address)
            for start in range(0, len(addresses), TOKEN_BATCH_SIZE):
                chunk = addresses[start : start + TOKEN_BATCH_SIZE]
                try:
                    pairs = await self._fetch_pairs(chain, chunk)
                except Exception:
                    logger.exception("DexScreener batch failed; chain=%s addresses=%s", chain, len(chunk))
                    continue
                for address in chunk:
                    best = best_pair(pairs, chain, address)
                    if best is None:
                        logger.warning("No DexScreener pair in batch; chain=%s address=%s", chain, address_key(address))
                        continue
                    for asset in by_address[address]:
                        quotes[asset.id] = quote_from_pair(best, self.name)
        return quotes

    async def close(self) -> None:
        await self.client.close()

    async def _fetch_pairs(self, chain: str, addresses: list[str]) -> list[dict]:
        payload = await self.client.get_json(f"{self.base_url}/tokens/v1/{chain}/{','.join(addresses)}")
        return pairs_from_payload(payload)
