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


def _pair(chain: str, address: str, *, price: str, liquidity: float) -> dict:
    return {
        "chainId": chain,
        "baseToken": {"address": "0x" + address[2:].upper() if address.startswith("0x") else address, "symbol": "TKN"},
        "quoteToken": {"symbol": "WETH"},
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
