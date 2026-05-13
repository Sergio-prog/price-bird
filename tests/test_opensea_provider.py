from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.db.enums import AssetType
from app.providers.opensea import OpenSeaNftProvider


@pytest.mark.asyncio
async def test_search_assets_maps_opensea_collection(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OpenSeaNftProvider(base_url="https://example.test", api_key="key")

    async def fake_get_json(path: str, *, params: dict[str, str]) -> dict:
        assert path == "/api/v2/search"
        assert params["query"] == "bayc"
        assert params["chains"] == "ethereum"
        assert params["asset_types"] == "collection"
        return {
            "collections": [
                {
                    "collection": "boredapeyachtclub",
                    "name": "Bored Ape Yacht Club",
                    "chain": "ethereum",
                    "image_url": "https://example.test/bayc.png",
                }
            ]
        }

    monkeypatch.setattr(provider, "_get_json", fake_get_json)

    candidates = await provider.search_assets("bayc", nft=True)

    assert len(candidates) == 1
    assert candidates[0].type == AssetType.NFT_COLLECTION
    assert candidates[0].provider == "opensea"
    assert candidates[0].provider_asset_id == "boredapeyachtclub"
    assert candidates[0].links["opensea"] == "https://opensea.io/collection/boredapeyachtclub"


@pytest.mark.asyncio
async def test_get_price_converts_native_floor_to_usd(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OpenSeaNftProvider(base_url="https://example.test", api_key="key")

    async def fake_get_json(path: str, *, params: dict[str, str]) -> dict:
        assert path == "/api/v2/collections/boredapeyachtclub/stats"
        return {"total": {"floor_price": 12.5}}

    async def fake_get_eth_usd() -> Decimal:
        return Decimal("3000")

    monkeypatch.setattr(provider, "_get_json", fake_get_json)
    monkeypatch.setattr(provider, "_get_eth_usd", fake_get_eth_usd)
    asset = SimpleNamespace(provider_asset_id="boredapeyachtclub", symbol="BAYC")

    quote = await provider.get_price(asset)

    assert quote.price_usd == Decimal("37500.0")
    assert quote.price_native == Decimal("12.5")
    assert quote.native_symbol == "ETH"
    assert quote.source == "opensea"


@pytest.mark.asyncio
async def test_opensea_requires_api_key() -> None:
    provider = OpenSeaNftProvider(base_url="https://example.test", api_key="")

    with pytest.raises(RuntimeError, match="OPENSEA_API_KEY"):
        await provider.search_assets("bayc", nft=True)
