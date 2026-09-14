from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.db.enums import AssetType
from app.providers.base import ProviderConfigurationError
from app.providers.opensea import OpenSeaNftProvider
from app.providers.opensea_mapping import slug_variants


@pytest.mark.asyncio
async def test_search_assets_maps_opensea_search_results(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OpenSeaNftProvider(base_url="https://example.test", api_key="key")

    async def fake_get_json(path: str, *, params: dict[str, str], missing_ok: bool = False) -> dict:
        assert path == "/api/v2/search"
        assert params["query"] == "bayc"
        assert params["chains"] == "ethereum"
        assert params["asset_types"] == "collection"
        return {
            "results": [
                {
                    "type": "collection",
                    "collection": {
                        "collection": "boredapeyachtclub",
                        "name": "Bored Ape Yacht Club",
                        "image_url": "https://example.test/bayc.png",
                        "is_disabled": False,
                    },
                },
                {"type": "collection", "collection": {"collection": "spam", "is_disabled": True}},
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
async def test_search_falls_back_to_slug_lookup_when_key_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OpenSeaNftProvider(base_url="https://example.test", api_key="expired")

    async def fake_get_json(path: str, *, params: dict[str, str], missing_ok: bool = False) -> dict | None:
        if path == "/api/v2/search":
            raise ProviderConfigurationError("expired")
        assert missing_ok is True
        if path == "/api/v2/collections/pudgypenguins":
            return {"collection": "pudgypenguins", "name": "Pudgy Penguins"}
        return None

    monkeypatch.setattr(provider, "_get_json", fake_get_json)

    candidates = await provider.search_assets("Pudgy Penguins", nft=True)

    assert [candidate.provider_asset_id for candidate in candidates] == ["pudgypenguins"]


@pytest.mark.asyncio
async def test_search_reports_rejected_key_when_slug_lookup_finds_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OpenSeaNftProvider(base_url="https://example.test", api_key="")

    async def fake_get_json(path: str, *, params: dict[str, str], missing_ok: bool = False) -> dict | None:
        assert path.startswith("/api/v2/collections/")
        return None

    monkeypatch.setattr(provider, "_get_json", fake_get_json)

    with pytest.raises(ProviderConfigurationError, match="OPENSEA_API_KEY"):
        await provider.search_assets("unknown", nft=True)


@pytest.mark.asyncio
async def test_get_price_converts_native_floor_to_usd(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OpenSeaNftProvider(base_url="https://example.test", api_key="key")

    async def fake_get_json(path: str, *, params: dict[str, str], missing_ok: bool = False) -> dict:
        assert path == "/api/v2/collections/boredapeyachtclub/stats"
        return {"total": {"floor_price": 12.5, "market_cap": 125000}}

    async def fake_get_eth_usd() -> Decimal:
        return Decimal("3000")

    monkeypatch.setattr(provider, "_get_json", fake_get_json)
    monkeypatch.setattr(provider, "_get_eth_usd", fake_get_eth_usd)
    asset = SimpleNamespace(provider_asset_id="boredapeyachtclub", symbol="BAYC")

    quote = await provider.get_price(asset)

    assert quote.price_usd == Decimal("37500.0")
    assert quote.price_native == Decimal("12.5")
    assert quote.native_symbol == "ETH"
    assert quote.market_cap_usd == Decimal("375000000")
    assert quote.source == "opensea"


def test_slug_variants_cover_hyphenated_and_joined_forms() -> None:
    assert slug_variants("Pudgy Penguins") == ["pudgy-penguins", "pudgypenguins"]
    assert slug_variants("milady") == ["milady"]


@pytest.mark.asyncio
async def test_get_prices_fetches_eth_usd_once_and_skips_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OpenSeaNftProvider(base_url="https://example.test", api_key="key")
    eth_calls = 0

    async def fake_get_json(path: str, *, params: dict[str, str], missing_ok: bool = False) -> dict:
        if "broken" in path:
            raise RuntimeError("boom")
        return {"total": {"floor_price": 2}}

    async def fake_get_eth_usd() -> Decimal:
        nonlocal eth_calls
        eth_calls += 1
        return Decimal("1000")

    monkeypatch.setattr(provider, "_get_json", fake_get_json)
    monkeypatch.setattr(provider, "_get_eth_usd", fake_get_eth_usd)
    assets = [
        SimpleNamespace(id=1, provider_asset_id="milady", symbol="MILADY"),
        SimpleNamespace(id=2, provider_asset_id="broken", symbol="BROKEN"),
    ]

    quotes = await provider.get_prices(assets)

    assert eth_calls == 1
    assert list(quotes) == [1]
    assert quotes[1].price_usd == Decimal("2000")
