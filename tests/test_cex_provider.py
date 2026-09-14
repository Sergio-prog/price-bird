from decimal import Decimal
from types import SimpleNamespace

import pytest
from ccxt.base.errors import DDoSProtection

from app.providers.cex import CcxtProvider
from app.utils.ratelimit import ProviderThrottle, RateLimited


class FakeExchange:
    def __init__(self) -> None:
        self.has = {"fetchTickers": True}
        self.markets: dict[str, dict] = {}
        self.load_calls = 0
        self.batches: list[list[str]] = []
        self.fail_with: Exception | None = None

    async def load_markets(self, reload: bool = False) -> dict:
        self.load_calls += 1
        self.markets = {f"S{i}/USDT": {"base": f"S{i}", "quote": "USDT"} for i in range(25)}
        return self.markets

    async def fetch_tickers(self, symbols: list[str]) -> dict:
        if self.fail_with is not None:
            raise self.fail_with
        self.batches.append(symbols)
        return {symbol: {"last": float(index + 1)} for index, symbol in enumerate(symbols) if symbol != "S3/USDT"}

    async def close(self) -> None:
        pass


def _provider(exchange: FakeExchange) -> CcxtProvider:
    return CcxtProvider(
        exchange_factory=lambda exchange_id: exchange,
        throttle=ProviderThrottle("ccxt", rate_per_minute=6000),
    )


def _assets(count: int) -> list[SimpleNamespace]:
    return [SimpleNamespace(id=i, provider_asset_id=f"binance:S{i}/USDT", symbol=f"S{i}") for i in range(count)]


@pytest.mark.asyncio
async def test_get_prices_batches_symbols_and_loads_markets_once() -> None:
    exchange = FakeExchange()
    provider = _provider(exchange)

    quotes = await provider.get_prices(_assets(25))
    await provider.get_prices(_assets(2))

    assert exchange.load_calls == 1
    assert [len(batch) for batch in exchange.batches] == [20, 5, 2]
    assert len(quotes) == 24
    assert 3 not in quotes
    assert quotes[0].price_usd == Decimal("1")


@pytest.mark.asyncio
async def test_unknown_markets_are_skipped_without_request() -> None:
    exchange = FakeExchange()
    provider = _provider(exchange)

    quotes = await provider.get_prices([SimpleNamespace(id=9, provider_asset_id="binance:NOPE/USDT", symbol="NOPE")])

    assert quotes == {}
    assert exchange.batches == [[]] or exchange.batches == []


@pytest.mark.asyncio
async def test_last_price_uses_batch_cache() -> None:
    exchange = FakeExchange()
    provider = _provider(exchange)
    await provider.get_prices(_assets(1))

    price = await provider.last_price("S0/USDT")

    assert price == Decimal("1")
    assert len(exchange.batches) == 1


@pytest.mark.asyncio
async def test_ban_pauses_provider() -> None:
    exchange = FakeExchange()
    provider = _provider(exchange)
    await provider.get_prices(_assets(1))
    exchange.fail_with = DDoSProtection("binance 418 banned until 1893456000000")

    with pytest.raises(RateLimited):
        await provider.get_price(_assets(1)[0])

    assert provider.throttle.remaining_pause() > 100
