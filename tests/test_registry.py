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
