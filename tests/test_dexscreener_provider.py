from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.providers.dexscreener import DexScreenerProvider
from app.providers.dexscreener_mapping import best_pair


class FakeClient:
    def __init__(self) -> None:
        self.urls: list[str] = []

    async def get_json(self, url: str, *, params=None, missing_ok: bool = False):
        self.urls.append(url)
        chain, addresses = url.rsplit("/", 2)[1:]
        pairs = []
        for address in addresses.split(","):
            pairs.append(_pair(chain, address, price="1.5", liquidity=10))
            pairs.append(_pair(chain, address, price="2.5", liquidity=100))
        return pairs

    async def close(self) -> None:
        pass


class SearchClient:
    def __init__(self, pairs: list[dict]) -> None:
        self.pairs = pairs
        self.urls: list[str] = []

    async def get_json(self, url: str, *, params=None, missing_ok: bool = False):
        self.urls.append(url)
        return {"pairs": self.pairs}

    async def close(self) -> None:
        pass


def _pair(
    chain: str,
    address: str,
    *,
    price: str,
    liquidity: float,
    volume: float = 0,
    pair_address: str = "pool",
    quote: str = "WETH",
) -> dict:
    return {
        "chainId": chain,
        "pairAddress": pair_address,
        "volume": {"h24": volume},
        "baseToken": {"address": "0x" + address[2:].upper() if address.startswith("0x") else address, "symbol": "TKN"},
        "quoteToken": {"symbol": quote},
        "priceUsd": price,
        "priceNative": "0.001",
        "liquidity": {"usd": liquidity},
        "marketCap": 1000,
    }


@pytest.mark.asyncio
async def test_get_prices_batches_per_chain_and_picks_deepest_pair() -> None:
    client = FakeClient()
    provider = DexScreenerProvider(client=client)
    assets = [SimpleNamespace(id=i, provider_asset_id=f"ethereum:0x{i:040x}", symbol="TKN") for i in range(31)]
    assets.append(SimpleNamespace(id=99, provider_asset_id="solana:So1anaAddress", symbol="SOL"))

    quotes = await provider.get_prices(assets)

    assert len(client.urls) == 3
    assert client.urls[0].startswith("https://api.dexscreener.com/tokens/v1/ethereum/")
    assert len(client.urls[0].split("/")[-1].split(",")) == 30
    assert len(quotes) == 32
    assert quotes[0].price_usd == Decimal("2.5")
    assert quotes[0].price_native == Decimal("0.001")
    assert quotes[0].native_symbol == "ETH"
    assert quotes[99].market_cap_usd == Decimal("1000")


def test_best_pair_ignores_other_chains_and_missing_prices() -> None:
    pairs = [
        _pair("bsc", "0xabc", price="1", liquidity=999),
        {**_pair("ethereum", "0xabc", price="1", liquidity=999), "priceUsd": None},
        _pair("ethereum", "0xabc", price="3", liquidity=1),
    ]

    assert best_pair(pairs, "ethereum", "0xABC")["priceUsd"] == "3"
    assert best_pair(pairs, "ethereum", "0xdef") is None


@pytest.mark.asyncio
async def test_search_merges_pools_into_tokens_ranked_by_volume() -> None:
    provider = DexScreenerProvider(
        client=SearchClient(
            [
                _pair("solana", "Real", price="92.4", liquidity=10, volume=5_000, pair_address="p1"),
                _pair("solana", "Real", price="92.5", liquidity=900, volume=7_000, pair_address="p2"),
                _pair("solana", "Clone", price="80", liquidity=10**9, volume=20_000, pair_address="p3"),
                _pair("solana", "Dust", price="40", liquidity=10**9, volume=5, pair_address="p4"),
            ]
        )
    )

    candidates = await provider.search_assets("TKN")

    assert [candidate.provider_asset_id for candidate in candidates] == ["solana:Clone", "solana:Real"]
    assert candidates[1].metadata["price_usd"] == "92.5"
    assert candidates[1].volume_usd == 12_000


@pytest.mark.asyncio
async def test_search_by_pool_address_tracks_that_pool() -> None:
    pool = "81GpCm4d13y8TozYtThabuSCLQN2o3bbrvDogXFPn8sA"
    provider = DexScreenerProvider(
        client=SearchClient([_pair("solana", "Real", price="92.4", liquidity=10, pair_address=pool, quote="SOL")])
    )

    candidates = await provider.search_assets(pool)

    assert [(candidate.provider_asset_id, candidate.symbol) for candidate in candidates] == [(f"solana:pair:{pool}", "TKN/SOL")]


@pytest.mark.asyncio
async def test_pool_assets_are_priced_from_their_own_pool() -> None:
    client = SearchClient(
        [
            _pair("solana", "Real", price="92.4", liquidity=10, pair_address="thin"),
            _pair("solana", "Real", price="95", liquidity=900, pair_address="deep"),
        ]
    )
    provider = DexScreenerProvider(client=client)

    quotes = await provider.get_prices([SimpleNamespace(id=1, provider_asset_id="solana:pair:thin", symbol="TKN/SOL")])

    assert client.urls == ["https://api.dexscreener.com/latest/dex/pairs/solana/thin"]
    assert quotes[1].price_usd == Decimal("92.4")
