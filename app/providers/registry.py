from __future__ import annotations

from app.core.config import settings
from app.db.models import Asset
from app.providers.base import AssetCandidate, PriceProvider, PriceQuote
from app.providers.cex import CcxtProvider
from app.providers.dexscreener import DexScreenerProvider
from app.providers.opensea import OpenSeaNftProvider
from app.providers.reservoir import ReservoirNftProvider


class ProviderRegistry:
    def __init__(self, providers: list[PriceProvider] | None = None) -> None:
        self.providers = providers or [DexScreenerProvider(), CcxtProvider(), *_build_nft_providers()]

    async def search_assets(self, query: str, *, nft: bool = False) -> list[AssetCandidate]:
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
        return results

    async def get_price(self, asset: Asset) -> PriceQuote:
        for provider in self.providers:
            if provider.name == asset.provider:
                return await provider.get_price(asset)
        raise LookupError(f"No provider registered for {asset.provider}")


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
