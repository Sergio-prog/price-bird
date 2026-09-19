from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.providers.hyperliquid import HyperliquidProvider

SPOT_PAYLOAD = [
    {
        "tokens": [{"index": 0, "name": "USDC"}, {"index": 150, "name": "HYPE"}, {"index": 268, "name": "USDT0"}],
        "universe": [
            {"name": "@107", "tokens": [150, 0]},
            {"name": "@207", "tokens": [150, 268]},
        ],
    },
    [
        {"coin": "@107", "midPx": "92.42", "markPx": "92.40", "dayNtlVlm": "84000000", "circulatingSupply": "1000"},
        {"coin": "@207", "midPx": "92.47", "markPx": "92.48", "dayNtlVlm": "200000", "circulatingSupply": "1000"},
    ],
]
PERP_PAYLOAD = [
    {"universe": [{"name": "BTC"}, {"name": "HYPE"}, {"name": "OLD", "isDelisted": True}]},
    [
        {"midPx": "81390.5", "markPx": "81390", "dayNtlVlm": "1388404103"},
        {"midPx": None, "markPx": "92.47", "dayNtlVlm": "391000000"},
        {"midPx": "1", "markPx": "1", "dayNtlVlm": "0"},
    ],
]


class FakeClient:
    def __init__(self) -> None:
        self.requests: list[str] = []

    async def post_json(self, url: str, *, body: dict):
        self.requests.append(body["type"])
        return SPOT_PAYLOAD if body["type"] == "spotMetaAndAssetCtxs" else PERP_PAYLOAD

    async def close(self) -> None:
        pass


@pytest.mark.asyncio
async def test_search_offers_the_busiest_stable_spot_pair_then_the_perp() -> None:
    candidates = await HyperliquidProvider(client=FakeClient()).search_assets("hype")

    assert [(candidate.provider_asset_id, candidate.symbol) for candidate in candidates] == [
        ("spot:@107", "HYPE/USDC"),
        ("perp:HYPE", "HYPE-PERP"),
    ]
    assert candidates[0].metadata["price_usd"] == "92.42"
    assert candidates[0].venue == "hyperliquid"
    assert candidates[0].volume_usd == candidates[1].volume_usd == 475_000_000


@pytest.mark.asyncio
async def test_get_prices_uses_one_request_per_market_kind() -> None:
    client = FakeClient()
    assets = [
        SimpleNamespace(id=1, provider_asset_id="spot:@107", symbol="HYPE/USDC"),
        SimpleNamespace(id=2, provider_asset_id="perp:HYPE", symbol="HYPE-PERP"),
        SimpleNamespace(id=3, provider_asset_id="perp:BTC", symbol="BTC-PERP"),
        SimpleNamespace(id=4, provider_asset_id="perp:OLD", symbol="OLD-PERP"),
    ]

    quotes = await HyperliquidProvider(client=client).get_prices(assets)

    assert client.requests == ["spotMetaAndAssetCtxs", "metaAndAssetCtxs"]
    assert quotes[1].price_usd == Decimal("92.42")
    assert quotes[1].market_cap_usd == Decimal("92420")
    assert quotes[2].price_usd == Decimal("92.47")
    assert quotes[2].market_cap_usd is None
    assert 4 not in quotes
