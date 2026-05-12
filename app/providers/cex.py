from __future__ import annotations

from decimal import Decimal

import ccxt.async_support as ccxt

from app.db.enums import AssetType
from app.db.models import Asset
from app.providers.base import AssetCandidate, PriceQuote


class CcxtProvider:
    name = "ccxt"

    def __init__(self, exchange_id: str = "binance") -> None:
        self.exchange_id = exchange_id

    async def search_assets(self, query: str, *, nft: bool = False) -> list[AssetCandidate]:
        if nft:
            return []
        exchange = getattr(ccxt, self.exchange_id)()
        try:
            markets = await exchange.load_markets()
        finally:
            await exchange.close()
        needle = query.upper()
        candidates = []
        for symbol, market in markets.items():
            base = (market.get("base") or "").upper()
            if needle in {base, symbol.upper()} and market.get("quote") in {"USDT", "USD", "USDC"}:
                candidates.append(
                    AssetCandidate(
                        type=AssetType.CEX_SYMBOL,
                        provider=self.name,
                        provider_asset_id=f"{self.exchange_id}:{symbol}",
                        symbol=symbol,
                        name=f"{self.exchange_id.upper()} {symbol}",
                        metadata={"exchange": self.exchange_id},
                        links={"tradingview": f"https://www.tradingview.com/symbols/{base}USDT/"},
                    )
                )
        return candidates[:10]

    async def get_price(self, asset: Asset) -> PriceQuote:
        exchange_id, symbol = asset.provider_asset_id.split(":", 1)
        exchange = getattr(ccxt, exchange_id)()
        try:
            ticker = await exchange.fetch_ticker(symbol)
        finally:
            await exchange.close()
        price = ticker.get("last") or ticker.get("close")
        if price is None:
            raise LookupError(f"No CEX price for {symbol}")
        return PriceQuote(price_usd=Decimal(str(price)), source=self.name, raw=ticker)
