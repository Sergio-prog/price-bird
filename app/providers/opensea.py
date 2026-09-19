from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from decimal import Decimal
from functools import partial
from typing import Any

import aiohttp

from app.core.config import settings
from app.db.models import Asset
from app.providers.base import AssetCandidate, PriceQuote, ProviderConfigurationError, sequential_prices
from app.providers.cex import default_cex_provider
from app.providers.opensea_mapping import (
    DEFAULT_FLOOR_SYMBOL,
    candidate_from_collection,
    collections_from_search,
    floor_price,
    floor_symbol,
    market_cap,
    slug_variants,
)
from app.utils.http import HttpClient
from app.utils.parsing import is_evm_address
from app.utils.ratelimit import ProviderThrottle

logger = logging.getLogger(__name__)

CONTRACT_LOOKUP_CHAINS = (
    "ethereum",
    "base",
    "robinhood",
    "abstract",
    "ape_chain",
    "hyperevm",
    "monad",
    "arbitrum",
    "polygon",
    "optimism",
)
THROTTLE_BURST = 10
USD = "USD"


class OpenSeaNftProvider:
    name = "opensea"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        price_source: Callable[[str], Awaitable[Decimal]] | None = None,
    ) -> None:
        self.base_url = (base_url or settings.opensea_base_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.opensea_api_key
        self._price_source = price_source or default_cex_provider.last_price
        headers = {"accept": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        self.client = HttpClient(
            throttle=ProviderThrottle(self.name, rate_per_minute=settings.opensea_reads_per_hour / 60, burst=THROTTLE_BURST),
            headers=headers,
        )

    async def search_assets(self, query: str, *, nft: bool = False) -> list[AssetCandidate]:
        if not nft:
            return []
        if is_evm_address(query):
            return await self._lookup_by_contract(query.strip())

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
        return await self._quote(asset, {})

    async def get_prices(self, assets: Sequence[Asset]) -> dict[int, PriceQuote]:
        if not assets:
            return {}
        try:
            usd_rates = {DEFAULT_FLOOR_SYMBOL: await self._usd_rate(DEFAULT_FLOOR_SYMBOL)}
        except Exception:
            logger.exception("Skipped OpenSea batch because %s/USD is unavailable", DEFAULT_FLOOR_SYMBOL)
            return {}
        return await sequential_prices(self.name, assets, partial(self._quote, usd_rates=usd_rates))

    async def close(self) -> None:
        await self.client.close()

    async def _quote(self, asset: Asset, usd_rates: dict[str, Decimal]) -> PriceQuote:
        stats = await self._get_json(f"/api/v2/collections/{asset.provider_asset_id}/stats", params={})
        floor_native = floor_price(stats or {})
        if floor_native is None:
            raise LookupError(f"No OpenSea floor price found for {asset.symbol}")

        symbol = floor_symbol(stats or {})
        if symbol not in usd_rates:
            usd_rates[symbol] = await self._usd_rate(symbol)
        usd_rate = usd_rates[symbol]
        market_cap_native = market_cap(stats or {})
        return PriceQuote(
            price_usd=floor_native * usd_rate,
            price_native=None if symbol == USD else floor_native,
            native_symbol=None if symbol == USD else symbol,
            market_cap_usd=market_cap_native * usd_rate if market_cap_native is not None else None,
            source=self.name,
            raw={
                **stats,
                "provider": self.name,
                "chain": asset.chain,
                "native_symbol": symbol,
                "usd_rate": str(usd_rate),
            },
        )

    async def _search_collections(self, query: str) -> list[AssetCandidate]:
        payload = await self._get_json(
            "/api/v2/search",
            params={
                "query": query,
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

    async def _lookup_by_contract(self, address: str) -> list[AssetCandidate]:
        for chain in dict.fromkeys([settings.opensea_chain, *CONTRACT_LOOKUP_CHAINS]):
            contract = await self._get_json(f"/api/v2/chain/{chain}/contract/{address}", params={}, missing_ok=True)
            slug = (contract or {}).get("collection")
            if not slug:
                continue
            collection = await self._get_json(f"/api/v2/collections/{slug}", params={}, missing_ok=True)
            if not collection:
                continue
            try:
                return [candidate_from_collection(collection, provider_name=self.name)]
            except ValueError:
                continue
        return []

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
        try:
            return await self.client.get_json(f"{self.base_url}{path}", params=params, missing_ok=missing_ok)
        except aiohttp.ClientResponseError as exc:
            if exc.status in {401, 403}:
                raise ProviderConfigurationError(f"OpenSea rejected the API key ({exc.status}); renew OPENSEA_API_KEY") from exc
            raise

    async def _usd_rate(self, symbol: str) -> Decimal:
        return Decimal(1) if symbol == USD else await self._price_source(f"{symbol}/USDT")
