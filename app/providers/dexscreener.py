from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.core.config import settings
from app.db.enums import AssetType
from app.db.models import Asset
from app.providers.base import AssetCandidate, PriceQuote
from app.providers.dexscreener_mapping import (
    address_key,
    best_pair,
    format_pair,
    format_price,
    normalize_chain,
    pair_by_address,
    pair_liquidity,
    pair_volume,
    pairs_from_payload,
    quote_from_pair,
)
from app.utils.currency import native_symbol_or_none
from app.utils.http import HttpClient
from app.utils.parsing import is_onchain_address
from app.utils.ratelimit import ProviderThrottle

logger = logging.getLogger(__name__)

TOKEN_BATCH_SIZE = 30
MAX_TOKEN_CANDIDATES = 10
MIN_TOKEN_VOLUME_USD = 1000
PAIR_PREFIX = "pair:"


@dataclass(frozen=True)
class DexAssetId:
    chain: str
    address: str
    is_pair: bool


def parse_asset_id(provider_asset_id: str) -> DexAssetId:
    chain, rest = provider_asset_id.split(":", 1)
    if rest.startswith(PAIR_PREFIX):
        return DexAssetId(chain, rest.removeprefix(PAIR_PREFIX), True)
    return DexAssetId(chain, rest, False)


class DexScreenerProvider:
    name = "dexscreener"
    base_url = "https://api.dexscreener.com"

    def __init__(self, *, client: HttpClient | None = None) -> None:
        self.client = client or HttpClient(
            throttle=ProviderThrottle(self.name, rate_per_minute=settings.dexscreener_requests_per_minute)
        )

    async def search_assets(self, query: str, *, nft: bool = False) -> list[AssetCandidate]:
        if nft:
            return []
        query = query.strip()
        payload = await self.client.get_json(f"{self.base_url}/latest/dex/search", params={"q": query})
        pairs = [pair for pair in pairs_from_payload(payload) if _is_complete(pair)]
        if not is_onchain_address(query):
            return self._token_candidates(pairs, min_volume_usd=MIN_TOKEN_VOLUME_USD)

        wanted = address_key(query)
        for pair in pairs:
            if address_key(pair["pairAddress"]) == wanted:
                return [self._candidate(pair, volume_usd=pair_volume(pair), track_pair=True)]
        return self._token_candidates(
            [pair for pair in pairs if address_key(pair["baseToken"]["address"]) == wanted],
            min_volume_usd=0,
        )

    async def get_price(self, asset: Asset) -> PriceQuote:
        asset_id = parse_asset_id(asset.provider_asset_id)
        quotes = await self._quotes(asset_id.chain, [asset_id.address], pairs_only=asset_id.is_pair)
        quote = quotes.get(asset_id.address)
        if quote is None:
            raise LookupError(f"No DexScreener pair for {asset.symbol}")
        return quote

    async def get_prices(self, assets: Sequence[Asset]) -> dict[int, PriceQuote]:
        quotes: dict[int, PriceQuote] = {}
        grouped: dict[tuple[str, bool], dict[str, list[Asset]]] = defaultdict(lambda: defaultdict(list))
        for asset in assets:
            asset_id = parse_asset_id(asset.provider_asset_id)
            grouped[(asset_id.chain, asset_id.is_pair)][asset_id.address].append(asset)
        for (chain, is_pair), by_address in grouped.items():
            addresses = sorted(by_address)
            for start in range(0, len(addresses), TOKEN_BATCH_SIZE):
                chunk = addresses[start : start + TOKEN_BATCH_SIZE]
                try:
                    chunk_quotes = await self._quotes(chain, chunk, pairs_only=is_pair)
                except Exception:
                    logger.exception("DexScreener batch failed; chain=%s pairs=%s addresses=%s", chain, is_pair, len(chunk))
                    continue
                for address in chunk:
                    quote = chunk_quotes.get(address)
                    if quote is None:
                        logger.warning("No DexScreener pair in batch; chain=%s address=%s", chain, address_key(address))
                        continue
                    for asset in by_address[address]:
                        quotes[asset.id] = quote
        return quotes

    async def close(self) -> None:
        await self.client.close()

    async def _quotes(self, chain: str, addresses: list[str], *, pairs_only: bool) -> dict[str, PriceQuote]:
        path = f"latest/dex/pairs/{chain}" if pairs_only else f"tokens/v1/{chain}"
        pairs = pairs_from_payload(await self.client.get_json(f"{self.base_url}/{path}/{','.join(addresses)}"))
        pick = pair_by_address if pairs_only else best_pair
        quotes: dict[str, PriceQuote] = {}
        for address in addresses:
            pair = pick(pairs, chain, address)
            if pair is not None:
                quotes[address] = quote_from_pair(pair, self.name)
        return quotes

    def _token_candidates(self, pairs: list[dict[str, Any]], *, min_volume_usd: float) -> list[AssetCandidate]:
        by_token: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for pair in pairs:
            by_token[(pair["chainId"], address_key(pair["baseToken"]["address"]))].append(pair)
        tokens = [
            (sum(pair_volume(pair) for pair in token_pairs), max(token_pairs, key=pair_liquidity))
            for token_pairs in by_token.values()
        ]
        traded = [token for token in tokens if token[0] >= min_volume_usd] or tokens
        traded.sort(key=lambda token: token[0], reverse=True)
        return [
            self._candidate(pair, volume_usd=volume_usd, track_pair=False) for volume_usd, pair in traded[:MAX_TOKEN_CANDIDATES]
        ]

    def _candidate(self, pair: dict[str, Any], *, volume_usd: float, track_pair: bool) -> AssetCandidate:
        base = pair["baseToken"]
        quote = pair.get("quoteToken") or {}
        chain = pair["chainId"]
        pair_label = format_pair(base["symbol"], quote.get("symbol"))
        return AssetCandidate(
            type=AssetType.TOKEN,
            provider=self.name,
            provider_asset_id=f"{chain}:{PAIR_PREFIX}{pair['pairAddress']}" if track_pair else f"{chain}:{base['address']}",
            chain=normalize_chain(chain),
            symbol=(pair_label if track_pair else None) or base["symbol"],
            name=base.get("name"),
            contract_address=base["address"],
            metadata={
                "pair_address": pair["pairAddress"],
                "dex_id": pair.get("dexId"),
                "pair": pair_label,
                "price_usd": format_price(pair.get("priceUsd")),
                "native_symbol": native_symbol_or_none(quote.get("symbol")),
            },
            links={"dexscreener": pair["url"]} if pair.get("url") else {},
            volume_usd=volume_usd,
        )


def _is_complete(pair: dict[str, Any]) -> bool:
    base = pair.get("baseToken") or {}
    return bool(pair.get("chainId") and pair.get("pairAddress") and base.get("address") and base.get("symbol"))
