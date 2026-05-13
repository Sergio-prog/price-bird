from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.db.enums import AssetType
from app.providers.reservoir import ReservoirNftProvider


@pytest.mark.asyncio
async def test_search_assets_maps_reservoir_collection(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = ReservoirNftProvider(base_url="https://example.test", api_key="")

    async def fake_get_json(path: str, *, params: dict[str, str]) -> dict:
        assert path == "/collections/search/v1"
        assert params["prefix"] == "bayc"
        return {
            "collections": [
                {
                    "id": "0xbc4ca0eda7647a8ab7c2061c2e118a18a936f13d",
                    "slug": "boredapeyachtclub",
                    "name": "Bored Ape Yacht Club",
                    "primaryContract": "0xbc4ca0eda7647a8ab7c2061c2e118a18a936f13d",
                    "chainId": 1,
                    "externalUrl": "https://boredapeyachtclub.com",
                }
            ]
        }

    monkeypatch.setattr(provider, "_get_json", fake_get_json)

    candidates = await provider.search_assets("bayc", nft=True)

    assert len(candidates) == 1
    assert candidates[0].type == AssetType.NFT_COLLECTION
    assert candidates[0].provider == "reservoir"
    assert candidates[0].provider_asset_id == "0xbc4ca0eda7647a8ab7c2061c2e118a18a936f13d"
    assert candidates[0].chain == "ethereum"
    assert candidates[0].links["opensea"] == "https://opensea.io/collection/boredapeyachtclub"


@pytest.mark.asyncio
async def test_get_price_returns_usd_and_native_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = ReservoirNftProvider(base_url="https://example.test", api_key="")

    async def fake_get_json(path: str, *, params: dict[str, str]) -> dict:
        assert path == "/collections/v7"
        assert params["id"] == "collection-id"
        return {
            "collections": [
                {
                    "id": "collection-id",
                    "floorAsk": {
                        "price": {
                            "amount": {"native": 12.34, "usd": 43210.5},
                            "currency": {"symbol": "ETH"},
                        }
                    },
                }
            ]
        }

    monkeypatch.setattr(provider, "_get_json", fake_get_json)
    asset = SimpleNamespace(provider_asset_id="collection-id", symbol="BAYC")

    quote = await provider.get_price(asset)

    assert quote.price_usd == Decimal("43210.5")
    assert quote.price_native == Decimal("12.34")
    assert quote.native_symbol == "ETH"
    assert quote.source == "reservoir"


@pytest.mark.asyncio
async def test_get_price_fails_when_floor_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = ReservoirNftProvider(base_url="https://example.test", api_key="")

    async def fake_get_json(path: str, *, params: dict[str, str]) -> dict:
        return {"collections": [{"id": "collection-id"}]}

    monkeypatch.setattr(provider, "_get_json", fake_get_json)
    asset = SimpleNamespace(provider_asset_id="collection-id", symbol="BAYC")

    with pytest.raises(LookupError, match="No floor price"):
        await provider.get_price(asset)
