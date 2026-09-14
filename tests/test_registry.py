from dataclasses import dataclass
from decimal import Decimal

import pytest

from app.db.enums import AssetType
from app.providers.base import AssetCandidate, PriceQuote
from app.providers.registry import ProviderRegistry


@dataclass
class FakeProvider:
    name: str
    candidates: list[AssetCandidate] | None = None
    error: Exception | None = None

    async def search_assets(self, query: str, *, nft: bool = False) -> list[AssetCandidate]:
        if self.error is not None:
            raise self.error
        return self.candidates or []

    async def get_price(self, asset) -> PriceQuote:
        return PriceQuote(price_usd=Decimal("1"), source=self.name, raw={})

    async def get_prices(self, assets) -> dict[int, PriceQuote]:
        return {asset.id: await self.get_price(asset) for asset in assets}

    async def close(self) -> None:
        pass


@pytest.mark.asyncio
async def test_nft_search_falls_back_to_next_provider() -> None:
    candidate = AssetCandidate(
        type=AssetType.NFT_COLLECTION,
        provider="second",
        provider_asset_id="collection",
        symbol="COLLECTION",
    )
    registry = ProviderRegistry(
        providers=[
            FakeProvider(name="first", error=RuntimeError("first failed")),
            FakeProvider(name="second", candidates=[candidate]),
        ]
    )

    results = await registry.search_assets("collection", nft=True)

    assert results == [candidate]


@pytest.mark.asyncio
async def test_nft_search_raises_when_all_providers_fail() -> None:
    registry = ProviderRegistry(
        providers=[
            FakeProvider(name="first", error=RuntimeError("first failed")),
            FakeProvider(name="second", error=RuntimeError("second failed")),
        ]
    )

    with pytest.raises(RuntimeError, match="first failed"):
        await registry.search_assets("collection", nft=True)


@pytest.mark.asyncio
async def test_search_results_are_cached_per_query() -> None:
    calls: list[str] = []

    class CountingProvider(FakeProvider):
        async def search_assets(self, query: str, *, nft: bool = False) -> list[AssetCandidate]:
            calls.append(query)
            return []

    registry = ProviderRegistry(providers=[CountingProvider(name="only")], search_cache_seconds=60)

    await registry.search_assets("BTC")
    await registry.search_assets(" btc ")
    await registry.search_assets("btc", nft=True)

    assert calls == ["BTC", "btc"]
