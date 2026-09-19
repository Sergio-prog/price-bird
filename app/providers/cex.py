from __future__ import annotations

import logging
import re
import time
from collections import defaultdict
from collections.abc import Callable, Sequence
from decimal import Decimal
from typing import Any

import ccxt.async_support as ccxt
from ccxt.base.errors import DDoSProtection, RateLimitExceeded

from app.core.config import settings
from app.db.enums import AssetType
from app.db.models import Asset
from app.providers.base import AssetCandidate, PriceQuote
from app.utils.parsing import format_price
from app.utils.ratelimit import ProviderThrottle, RateLimited

logger = logging.getLogger(__name__)

TICKER_BATCH_SIZE = 20
PRICE_CACHE_SECONDS = 60
RATE_LIMIT_PAUSE_SECONDS = 60
BAN_PAUSE_SECONDS = 120
STABLE_QUOTES = ("USDT", "USDC", "USD")


def split_asset_id(provider_asset_id: str) -> tuple[str, str]:
    exchange_id, symbol = provider_asset_id.split(":", 1)
    return exchange_id, symbol


def ticker_price(ticker: dict[str, Any] | None) -> Decimal | None:
    if not ticker:
        return None
    price = ticker.get("last") or ticker.get("close")
    return Decimal(str(price)) if price is not None else None


def _is_spot(market: dict[str, Any]) -> bool:
    return market.get("type", "spot") == "spot"


def _quote_volume(ticker: dict[str, Any] | None) -> float:
    return float((ticker or {}).get("quoteVolume") or 0)


def ban_pause_seconds(exc: Exception) -> float:
    match = re.search(r"banned until (\d{13})", str(exc))
    if match:
        return max(BAN_PAUSE_SECONDS, int(match.group(1)) / 1000 - time.time())
    return BAN_PAUSE_SECONDS


class CcxtProvider:
    name = "ccxt"

    def __init__(
        self,
        exchange_id: str = "binance",
        *,
        exchange_factory: Callable[[str], Any] | None = None,
        throttle: ProviderThrottle | None = None,
    ) -> None:
        self.exchange_id = exchange_id
        self._exchange_factory = exchange_factory or (lambda exchange_id: getattr(ccxt, exchange_id)())
        self._exchanges: dict[str, Any] = {}
        self._markets_loaded_at: dict[str, float] = {}
        self._last_prices: dict[tuple[str, str], tuple[Decimal, float]] = {}
        self.throttle = throttle or ProviderThrottle(self.name, rate_per_minute=settings.ccxt_requests_per_minute)

    async def search_assets(self, query: str, *, nft: bool = False) -> list[AssetCandidate]:
        if nft:
            return []
        exchange = await self._exchange(self.exchange_id)
        needle = query.strip().upper()
        symbols = [
            symbol
            for symbol, market in exchange.markets.items()
            if market.get("quote") in STABLE_QUOTES
            and market.get("active") is not False
            and (symbol.upper() == needle or (_is_spot(market) and (market.get("base") or "").upper() == needle))
        ]
        if not symbols:
            return []
        try:
            tickers = await self._fetch_tickers(self.exchange_id, symbols)
        except RateLimited:
            raise
        except Exception:
            logger.exception("CEX search tickers failed; exchange=%s symbols=%s", self.exchange_id, len(symbols))
            tickers = {}

        exact = next((symbol for symbol in symbols if symbol.upper() == needle), None)
        best = exact or max(symbols, key=lambda symbol: _quote_volume(tickers.get(symbol)))
        ticker = tickers.get(best)
        return [
            AssetCandidate(
                type=AssetType.CEX_SYMBOL,
                provider=self.name,
                provider_asset_id=f"{self.exchange_id}:{best}",
                symbol=best,
                name=f"{self.exchange_id.upper()} {best}",
                metadata={"exchange": self.exchange_id, "price_usd": format_price(ticker_price(ticker))},
                links={"tradingview": f"https://www.tradingview.com/symbols/{exchange.markets[best].get('base')}USDT/"},
                volume_usd=_quote_volume(ticker),
            )
        ]

    async def get_price(self, asset: Asset) -> PriceQuote:
        exchange_id, symbol = split_asset_id(asset.provider_asset_id)
        tickers = await self._fetch_tickers(exchange_id, [symbol])
        quote = self._quote(exchange_id, symbol, tickers.get(symbol))
        if quote is None:
            raise LookupError(f"No CEX price for {symbol}")
        return quote

    async def get_prices(self, assets: Sequence[Asset]) -> dict[int, PriceQuote]:
        quotes: dict[int, PriceQuote] = {}
        grouped: dict[str, list[Asset]] = defaultdict(list)
        for asset in assets:
            grouped[split_asset_id(asset.provider_asset_id)[0]].append(asset)
        for exchange_id, items in grouped.items():
            symbols = sorted({split_asset_id(asset.provider_asset_id)[1] for asset in items})
            try:
                tickers = await self._fetch_tickers(exchange_id, symbols)
            except Exception:
                logger.exception("CEX batch failed; exchange=%s symbols=%s", exchange_id, len(symbols))
                continue
            for asset in items:
                symbol = split_asset_id(asset.provider_asset_id)[1]
                quote = self._quote(exchange_id, symbol, tickers.get(symbol))
                if quote is None:
                    logger.warning("No CEX price in batch; exchange=%s symbol=%s", exchange_id, symbol)
                    continue
                quotes[asset.id] = quote
        return quotes

    async def last_price(self, symbol: str, *, exchange_id: str | None = None) -> Decimal:
        exchange_id = exchange_id or self.exchange_id
        cached = self._last_prices.get((exchange_id, symbol))
        if cached is not None and time.monotonic() - cached[1] <= PRICE_CACHE_SECONDS:
            return cached[0]
        tickers = await self._fetch_tickers(exchange_id, [symbol])
        quote = self._quote(exchange_id, symbol, tickers.get(symbol))
        if quote is None:
            raise LookupError(f"No CEX price for {symbol}")
        return quote.price_usd

    async def close(self) -> None:
        exchanges = list(self._exchanges.values())
        self._exchanges.clear()
        self._markets_loaded_at.clear()
        for exchange in exchanges:
            await exchange.close()

    async def _exchange(self, exchange_id: str) -> Any:
        exchange = self._exchanges.get(exchange_id)
        if exchange is None:
            exchange = self._exchange_factory(exchange_id)
            self._exchanges[exchange_id] = exchange
        loaded_at = self._markets_loaded_at.get(exchange_id)
        if loaded_at is None or time.monotonic() - loaded_at > settings.ccxt_markets_ttl_seconds:
            await self._call(exchange.load_markets, loaded_at is not None)
            self._markets_loaded_at[exchange_id] = time.monotonic()
        return exchange

    async def _fetch_tickers(self, exchange_id: str, symbols: list[str]) -> dict[str, dict[str, Any]]:
        exchange = await self._exchange(exchange_id)
        known = [symbol for symbol in symbols if symbol in exchange.markets]
        for symbol in set(symbols) - set(known):
            logger.warning("Unknown CEX market; exchange=%s symbol=%s", exchange_id, symbol)
        tickers: dict[str, dict[str, Any]] = {}
        if exchange.has.get("fetchTickers"):
            for start in range(0, len(known), TICKER_BATCH_SIZE):
                tickers.update(await self._call(exchange.fetch_tickers, known[start : start + TICKER_BATCH_SIZE]))
            return tickers
        for symbol in known:
            tickers[symbol] = await self._call(exchange.fetch_ticker, symbol)
        return tickers

    async def _call(self, method: Callable[..., Any], *args: Any) -> Any:
        await self.throttle.acquire()
        try:
            return await method(*args)
        except DDoSProtection as exc:
            seconds = ban_pause_seconds(exc)
            self.throttle.pause(seconds)
            raise RateLimited(self.name, seconds) from exc
        except RateLimitExceeded as exc:
            self.throttle.pause(RATE_LIMIT_PAUSE_SECONDS)
            raise RateLimited(self.name, RATE_LIMIT_PAUSE_SECONDS) from exc

    def _quote(self, exchange_id: str, symbol: str, ticker: dict[str, Any] | None) -> PriceQuote | None:
        price = ticker_price(ticker)
        if price is None or ticker is None:
            return None
        self._last_prices[(exchange_id, symbol)] = (price, time.monotonic())
        return PriceQuote(price_usd=price, source=self.name, raw=ticker)


default_cex_provider = CcxtProvider()
