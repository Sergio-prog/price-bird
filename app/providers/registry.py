from __future__ import annotations

import time

from app.core.config import settings
from app.db.models import Asset
from app.providers.base import AssetCandidate, PriceProvider, PriceQuote
from app.providers.cex import default_cex_provider
from app.providers.dexscreener import DexScreenerProvider
from app.providers.opensea import OpenSeaNftProvider
from app.providers.reservoir import ReservoirNftProvider

SEARCH_CACHE_MAX_ENTRIES = 1000


class ProviderRegistry:
    def __init__(self, providers: list[PriceProvider] | None = None, *, search_cache_seconds: int | None = None) -> None:
        self.providers = providers or [DexScreenerProvider(), default_cex_provider, *_build_nft_providers()]
        self.search_cache_seconds = settings.search_cache_seconds if search_cache_seconds is None else search_cache_seconds
        self._search_cache: dict[tuple[str, bool], tuple[float, list[AssetCandidate]]] = {}

    async def search_assets(self, query: str, *, nft: bool = False) -> list[AssetCandidate]:
        key = (query.strip().lower(), nft)
        cached = self._search_cache.get(key)
        if cached is not None and time.monotonic() - cached[0] < self.search_cache_seconds:
            return list(cached[1])

        results: list[AssetCandidate] = []
        errors: list[Exception] = []
        for provider in self.providers:
            try:
                results.extend(await provider.search_assets(query, nft=nft))
            except Exception as exc:
                errors.append(exc)
                continue
        if nft and not results and errors:
            raise errors[0]
        self._remember_search(key, results)
        return results

    async def get_price(self, asset: Asset) -> PriceQuote:
        return await self.provider_for(asset.provider).get_price(asset)

    def provider_for(self, name: str) -> PriceProvider:
        for provider in self.providers:
            if provider.name == name:
                return provider
        raise LookupError(f"No provider registered for {name}")

    async def close(self) -> None:
        for provider in self.providers:
            close = getattr(provider, "close", None)
            if close is not None:
                await close()

    def _remember_search(self, key: tuple[str, bool], results: list[AssetCandidate]) -> None:
        if self.search_cache_seconds <= 0:
            return
        now = time.monotonic()
        if len(self._search_cache) >= SEARCH_CACHE_MAX_ENTRIES:
            self._search_cache = {
                cached_key: entry
                for cached_key, entry in self._search_cache.items()
                if now - entry[0] < self.search_cache_seconds
            }
        self._search_cache[key] = (now, list(results))


def _build_nft_providers() -> list[PriceProvider]:
    providers: list[PriceProvider] = []
    for provider in [name.strip().lower() for name in settings.nft_providers.split(",") if name.strip()]:
        if provider == "opensea":
            providers.append(OpenSeaNftProvider())
        elif provider == "reservoir":
            providers.append(ReservoirNftProvider())
        else:
            raise RuntimeError(f"Unsupported NFT provider: {provider}")
    return providers


provider_registry = ProviderRegistry()
