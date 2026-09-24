from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.core.config import settings
from app.db.enums import AssetType
from app.db.models import Asset
from app.providers.base import AssetCandidate, PriceQuote
from app.utils.http import HttpClient
from app.utils.parsing import format_price, to_decimal
from app.utils.ratelimit import ProviderThrottle

logger = logging.getLogger(__name__)

SPOT = "spot"
PERP = "perp"
STABLE_QUOTE_PREFIX = "USD"
MARKETS_CACHE_SECONDS = 2.0


@dataclass(frozen=True)
class Market:
    kind: str
    coin: str
    base: str
    quote: str
    price: Decimal
    volume_usd: float
    market_cap_usd: Decimal | None = None

    @property
    def symbol(self) -> str:
        return f"{self.base}/{self.quote}" if self.kind == SPOT else f"{self.base}-PERP"

    @property
    def url(self) -> str:
        path = f"{self.base}/{self.quote}" if self.kind == SPOT else self.base
        return f"https://app.hyperliquid.xyz/trade/{path}"


def split_asset_id(provider_asset_id: str) -> tuple[str, str]:
    kind, coin = provider_asset_id.split(":", 1)
    return kind, coin


def spot_markets(payload: Any) -> list[Market]:
    meta, contexts = payload
    tokens = {token["index"]: token["name"] for token in meta["tokens"]}
    context_by_coin = {context.get("coin"): context for context in contexts}
    markets: list[Market] = []
    for pair in meta["universe"]:
        context = context_by_coin.get(pair["name"])
        price = _price(context)
        if price is None:
            continue
        base, quote = (tokens.get(index) for index in pair["tokens"])
        if not base or not quote:
            continue
        supply = to_decimal(context.get("circulatingSupply"))
        markets.append(
            Market(
                kind=SPOT,
                coin=pair["name"],
                base=base,
                quote=quote,
                price=price,
                volume_usd=float(context.get("dayNtlVlm") or 0),
                market_cap_usd=supply * price if supply else None,
            )
        )
    return markets


def perp_markets(payload: Any) -> list[Market]:
    meta, contexts = payload
    markets: list[Market] = []
    for perp, context in zip(meta["universe"], contexts, strict=False):
        price = _price(context)
        if price is None or perp.get("isDelisted"):
            continue
        markets.append(
            Market(
                kind=PERP,
                coin=perp["name"],
                base=perp["name"],
                quote="USD",
                price=price,
                volume_usd=float(context.get("dayNtlVlm") or 0),
            )
        )
    return markets


def _price(context: dict[str, Any] | None) -> Decimal | None:
    if not context:
        return None
    price = to_decimal(context.get("midPx")) or to_decimal(context.get("markPx"))
    return price if price is not None and price > 0 else None


class HyperliquidProvider:
    name = "hyperliquid"
    info_url = "https://api.hyperliquid.xyz/info"

    def __init__(self, *, client: HttpClient | None = None, markets_cache_seconds: float = MARKETS_CACHE_SECONDS) -> None:
        self.client = client or HttpClient(
            throttle=ProviderThrottle(self.name, rate_per_minute=settings.hyperliquid_requests_per_minute)
        )
        self.markets_cache_seconds = markets_cache_seconds
        self._markets_cache: dict[str, tuple[float, list[Market]]] = {}

    async def search_assets(self, query: str, *, nft: bool = False) -> list[AssetCandidate]:
        if nft:
            return []
        base, _, quote = query.strip().upper().partition("/")
        if not base:
            return []

        spot_list, *perp_lists = await asyncio.gather(*(self._markets(kind) for kind in ((SPOT,) if quote else (SPOT, PERP))))
        spot = [
            market
            for market in spot_list
            if market.base.upper() == base
            and market.quote.upper().startswith(STABLE_QUOTE_PREFIX)
            and quote in {"", market.quote.upper()}
        ]
        perps = [market for markets in perp_lists for market in markets if market.base.upper() == base]
        matches = [*sorted(spot, key=lambda market: market.volume_usd, reverse=True)[:1], *perps]
        venue_volume_usd = sum(market.volume_usd for market in matches)
        return [self._candidate(market, volume_usd=venue_volume_usd) for market in matches]

    async def get_price(self, asset: Asset) -> PriceQuote:
        quotes = await self.get_prices([asset])
        quote = quotes.get(asset.id)
        if quote is None:
            raise LookupError(f"No Hyperliquid price for {asset.symbol}")
        return quote

    async def get_prices(self, assets: Sequence[Asset]) -> dict[int, PriceQuote]:
        quotes: dict[int, PriceQuote] = {}
        for kind in (SPOT, PERP):
            wanted = [asset for asset in assets if split_asset_id(asset.provider_asset_id)[0] == kind]
            if not wanted:
                continue
            try:
                markets = {market.coin: market for market in await self._markets(kind)}
            except Exception:
                logger.exception("Hyperliquid batch failed; kind=%s assets=%s", kind, len(wanted))
                continue
            for asset in wanted:
                market = markets.get(split_asset_id(asset.provider_asset_id)[1])
                if market is None:
                    logger.warning("No Hyperliquid market in batch; asset_id=%s symbol=%s", asset.id, asset.symbol)
                    continue
                quotes[asset.id] = PriceQuote(
                    price_usd=market.price,
                    source=self.name,
                    raw={"coin": market.coin, "kind": market.kind, "price": str(market.price)},
                    market_cap_usd=market.market_cap_usd,
                )
        return quotes

    async def close(self) -> None:
        await self.client.close()

    async def _markets(self, kind: str) -> list[Market]:
        cached = self._markets_cache.get(kind)
        if cached is not None and time.monotonic() - cached[0] < self.markets_cache_seconds:
            return cached[1]
        if kind == SPOT:
            markets = spot_markets(await self.client.post_json(self.info_url, body={"type": "spotMetaAndAssetCtxs"}))
        else:
            markets = perp_markets(await self.client.post_json(self.info_url, body={"type": "metaAndAssetCtxs"}))
        self._markets_cache[kind] = (time.monotonic(), markets)
        return markets

    def _candidate(self, market: Market, *, volume_usd: float) -> AssetCandidate:
        return AssetCandidate(
            type=AssetType.CEX_SYMBOL,
            provider=self.name,
            provider_asset_id=f"{market.kind}:{market.coin}",
            symbol=market.symbol,
            name=f"Hyperliquid {market.symbol}",
            metadata={"exchange": self.name, "market": market.kind, "price_usd": format_price(market.price)},
            links={"hyperliquid": market.url},
            volume_usd=volume_usd,
        )
