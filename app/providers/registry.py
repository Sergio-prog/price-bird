from __future__ import annotations

from app.db.models import Asset
from app.providers.base import AssetCandidate, PriceProvider, PriceQuote
from app.providers.cex import CcxtProvider
from app.providers.dexscreener import DexScreenerProvider
from app.providers.mock_nft import NftPlaceholderProvider


class ProviderRegistry:
    def __init__(self, providers: list[PriceProvider] | None = None) -> None:
        self.providers = providers or [DexScreenerProvider(), CcxtProvider(), NftPlaceholderProvider()]

    async def search_assets(self, query: str, *, nft: bool = False) -> list[AssetCandidate]:
        results: list[AssetCandidate] = []
        for provider in self.providers:
            try:
                results.extend(await provider.search_assets(query, nft=nft))
            except Exception:
                continue
        return results

    async def get_price(self, asset: Asset) -> PriceQuote:
        for provider in self.providers:
            if provider.name == asset.provider:
                return await provider.get_price(asset)
        raise LookupError(f"No provider registered for {asset.provider}")


provider_registry = ProviderRegistry()
