from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

import aiohttp

from app.core.config import settings
from app.db.models import Asset
from app.providers.base import AssetCandidate, PriceQuote, ProviderConfigurationError
from app.providers.opensea_mapping import (
    candidate_from_collection,
    collections_from_search,
    floor_price,
    market_cap,
    slug_variants,
)
from app.utils.http import sleep_before_retry


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

        configuration_error: ProviderConfigurationError | None = None
        if self.api_key:
            try:
                candidates = await self._search_collections(query)
            except ProviderConfigurationError as exc:
                configuration_error = exc
            else:
                if candidates:
                    return candidates
        else:
            configuration_error = ProviderConfigurationError("OPENSEA_API_KEY is missing; only exact collection slugs work")

        candidates = await self._lookup_by_slug(query)
        if candidates or configuration_error is None:
            return candidates
        raise configuration_error

    async def get_price(self, asset: Asset) -> PriceQuote:
        stats = await self._get_json(f"/api/v2/collections/{asset.provider_asset_id}/stats", params={})
        floor_native = floor_price(stats or {})
        if floor_native is None:
            raise LookupError(f"No OpenSea floor price found for {asset.symbol}")

        eth_usd = await self._get_eth_usd()
        market_cap_native = market_cap(stats or {})
        return PriceQuote(
            price_usd=floor_native * eth_usd,
            price_native=floor_native,
            native_symbol="ETH",
            market_cap_usd=market_cap_native * eth_usd if market_cap_native is not None else None,
            source=self.name,
            raw={
                **stats,
                "provider": self.name,
                "chain": settings.opensea_chain,
                "native_symbol": "ETH",
                "eth_usd": str(eth_usd),
            },
        )

    async def _search_collections(self, query: str) -> list[AssetCandidate]:
        payload = await self._get_json(
            "/api/v2/search",
            params={
                "query": query,
                "chains": settings.opensea_chain,
                "asset_types": "collection",
                "limit": "10",
            },
        )
        candidates: list[AssetCandidate] = []
        for collection in collections_from_search(payload or {}):
            try:
                candidates.append(candidate_from_collection(collection, provider_name=self.name))
            except ValueError:
                continue
        return candidates

    async def _lookup_by_slug(self, query: str) -> list[AssetCandidate]:
        candidates: list[AssetCandidate] = []
        for slug in slug_variants(query):
            try:
                collection = await self._get_json(f"/api/v2/collections/{slug}", params={}, missing_ok=True)
            except ProviderConfigurationError:
                continue
            if not collection:
                continue
            try:
                candidates.append(candidate_from_collection(collection, provider_name=self.name))
            except ValueError:
                continue
        return candidates

    async def _get_json(self, path: str, *, params: dict[str, str], missing_ok: bool = False) -> dict[str, Any] | None:
        headers = {"accept": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
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
                        if response.status in {401, 403}:
                            raise ProviderConfigurationError(
                                f"OpenSea rejected the API key ({response.status}); renew OPENSEA_API_KEY"
                            )
                        if missing_ok and response.status in {400, 404}:
                            return None
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
