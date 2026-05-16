from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from app.core.config import settings
from app.db.models import Asset
from app.providers.base import AssetCandidate, PriceQuote
from app.providers.http import sleep_before_retry
from app.providers.reservoir_mapping import candidate_from_collection, chain_name, floor_price


class ReservoirNftProvider:
    name = "reservoir"

    def __init__(self, *, base_url: str | None = None, api_key: str | None = None) -> None:
        self.base_url = (base_url or settings.reservoir_base_url).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.reservoir_api_key

    async def search_assets(self, query: str, *, nft: bool = False) -> list[AssetCandidate]:
        if not nft:
            return []

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

    async def _get_json(self, path: str, *, params: dict[str, str]) -> dict[str, Any]:
        headers = {"accept": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        timeout = aiohttp.ClientTimeout(total=settings.provider_timeout_seconds)
        url = f"{self.base_url}{path}"
        last_error: Exception | None = None
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            for attempt in range(settings.provider_max_attempts):
                try:
                    async with session.get(url, params=params) as response:
                        if response.status == 429 or 500 <= response.status < 600:
                            await sleep_before_retry(response, attempt)
                            continue
                        response.raise_for_status()
                        return await response.json()
                except (aiohttp.ClientError, TimeoutError) as exc:
                    last_error = exc
                    if attempt + 1 >= settings.provider_max_attempts:
                        break
                    await asyncio.sleep(0.5 * (2**attempt))

        if last_error is not None:
            raise last_error
        raise RuntimeError(f"Reservoir request failed after {settings.provider_max_attempts} attempts")
