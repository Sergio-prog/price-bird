from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.core.config import settings
from app.db.models import Asset
from app.providers.base import AssetCandidate, PriceQuote, sequential_prices
from app.providers.reservoir_mapping import candidate_from_collection, chain_name, floor_price
from app.utils.http import HttpClient
from app.utils.parsing import is_evm_address
from app.utils.ratelimit import ProviderThrottle

REQUESTS_PER_MINUTE = 60


class ReservoirNftProvider:
    name = "reservoir"

    def __init__(self, *, base_url: str | None = None, api_key: str | None = None) -> None:
        self.base_url = (base_url or settings.reservoir_base_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.reservoir_api_key
        headers = {"accept": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        self.client = HttpClient(throttle=ProviderThrottle(self.name, rate_per_minute=REQUESTS_PER_MINUTE), headers=headers)

    async def search_assets(self, query: str, *, nft: bool = False) -> list[AssetCandidate]:
        if not nft:
            return []

        if is_evm_address(query):
            payload = await self._get_json("/collections/v7", params={"id": query.strip(), "limit": "1"})
        else:
            payload = await self._get_json(
                "/collections/search/v1",
                params={
                    "prefix": query,
                    "excludeSpam": "true",
                    "excludeNsfw": "true",
                    "limit": "10",
                },
            )
        candidates: list[AssetCandidate] = []
        for collection in payload.get("collections") or []:
            try:
                candidates.append(candidate_from_collection(collection, provider_name=self.name))
            except ValueError:
                continue
        return candidates

    async def get_price(self, asset: Asset) -> PriceQuote:
        payload = await self._get_json("/collections/v7", params={"id": asset.provider_asset_id, "limit": "1"})
        collections = payload.get("collections") or []
        if not collections:
            raise LookupError(f"No Reservoir collection found for {asset.symbol}")

        collection = collections[0]
        price = floor_price(collection)
        if price is None:
            raise LookupError(f"No floor price found for {asset.symbol}")

        return PriceQuote(
            price_usd=price["usd"],
            price_native=price["native"],
            native_symbol=price["native_symbol"],
            source=self.name,
            raw={
                **collection,
                "provider": self.name,
                "chain": chain_name(collection),
                "native_symbol": price["native_symbol"],
            },
        )

    async def get_prices(self, assets: Sequence[Asset]) -> dict[int, PriceQuote]:
        return await sequential_prices(self.name, assets, self.get_price)

    async def close(self) -> None:
        await self.client.close()

    async def _get_json(self, path: str, *, params: dict[str, str]) -> dict[str, Any]:
        return await self.client.get_json(f"{self.base_url}{path}", params=params)
