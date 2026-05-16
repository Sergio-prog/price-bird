from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

import aiohttp

from app.core.config import settings
from app.db.models import Asset
from app.providers.base import AssetCandidate, PriceQuote
from app.providers.http import sleep_before_retry
from app.providers.opensea_mapping import candidate_from_collection, floor_price


class OpenSeaNftProvider:
    name = "opensea"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        eth_usd_symbol: str = "ETH/USDT",
    ) -> None:
        self.base_url = (base_url or settings.opensea_base_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.opensea_api_key
        self.eth_usd_symbol = eth_usd_symbol

    async def search_assets(self, query: str, *, nft: bool = False) -> list[AssetCandidate]:
        if not nft:
            return []
        self._ensure_configured()

        payload = await self._get_json(
            "/api/v2/search",
            params={
                "query": query,
                "chains": settings.opensea_chain,
                "asset_types": "collection",
                "limit": "10",
            },
        )
        collections = payload.get("collections") or payload.get("collection") or []
        if isinstance(collections, dict):
            collections = [collections]

        candidates: list[AssetCandidate] = []
        for collection in collections:
            try:
                candidates.append(candidate_from_collection(collection, provider_name=self.name))
            except ValueError:
                continue
        return candidates

    async def get_price(self, asset: Asset) -> PriceQuote:
        self._ensure_configured()

        stats = await self._get_json(f"/api/v2/collections/{asset.provider_asset_id}/stats", params={})
        floor_native = floor_price(stats)
        if floor_native is None:
            raise LookupError(f"No OpenSea floor price found for {asset.symbol}")

        eth_usd = await self._get_eth_usd()
        return PriceQuote(
            price_usd=floor_native * eth_usd,
            price_native=floor_native,
            native_symbol="ETH",
            source=self.name,
            raw={
                **stats,
                "provider": self.name,
                "chain": settings.opensea_chain,
                "native_symbol": "ETH",
                "eth_usd": str(eth_usd),
            },
        )

    async def _get_json(self, path: str, *, params: dict[str, str]) -> dict[str, Any]:
        headers = {"accept": "application/json", "x-api-key": self.api_key}
        timeout = aiohttp.ClientTimeout(total=settings.provider_timeout_seconds)
        url = f"{self.base_url}{path}"
        last_error: Exception | None = None
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            for attempt in range(settings.provider_max_attempts):
                try:
                    async with session.get(url, params=params) as response:
                        if response.status == 429 or 500 <= response.status < 600:
                            await sleep_before_retry(response, attempt)
                            continue
                        response.raise_for_status()
                        return await response.json()
                except (aiohttp.ClientError, TimeoutError) as exc:
                    last_error = exc
                    if attempt + 1 >= settings.provider_max_attempts:
                        break
                    await asyncio.sleep(0.5 * (2**attempt))

        if last_error is not None:
            raise last_error
        raise RuntimeError(f"OpenSea request failed after {settings.provider_max_attempts} attempts")

    async def _get_eth_usd(self) -> Decimal:
        import ccxt.async_support as ccxt

        exchange = ccxt.binance()
        try:
            ticker = await exchange.fetch_ticker(self.eth_usd_symbol)
        finally:
            await exchange.close()
        price = ticker.get("last") or ticker.get("close")
        if price is None:
            raise LookupError(f"No CEX price for {self.eth_usd_symbol}")
        return Decimal(str(price))

    def _ensure_configured(self) -> None:
        if not self.api_key:
            raise RuntimeError("OPENSEA_API_KEY is required when NFT_PROVIDER=opensea")
