from __future__ import annotations

import asyncio
from decimal import Decimal, InvalidOperation
from typing import Any

import aiohttp

from app.core.config import settings
from app.db.enums import AssetType
from app.db.models import Asset
from app.providers.base import AssetCandidate, PriceQuote


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
                candidates.append(_candidate_from_collection(collection))
            except ValueError:
                continue
        return candidates

    async def get_price(self, asset: Asset) -> PriceQuote:
        payload = await self._get_json("/collections/v7", params={"id": asset.provider_asset_id, "limit": "1"})
        collections = payload.get("collections") or []
        if not collections:
            raise LookupError(f"No Reservoir collection found for {asset.symbol}")

        collection = collections[0]
        price = _floor_price(collection)
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
                "chain": _chain_name(collection),
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
                            await _sleep_before_retry(response, attempt)
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


def _candidate_from_collection(collection: dict[str, Any]) -> AssetCandidate:
    collection_id = str(collection.get("id") or collection.get("collectionId") or "")
    if not collection_id:
        raise ValueError("Reservoir collection is missing id")

    name = collection.get("name")
    slug = collection.get("slug")
    symbol = str(slug or name or collection_id)
    contract = collection.get("primaryContract") or collection.get("contract")

    links: dict[str, str] = {}
    if collection.get("externalUrl"):
        links["website"] = collection["externalUrl"]
    if slug:
        links["reservoir"] = f"https://reservoir.tools/collection/{slug}"
        links["opensea"] = f"https://opensea.io/collection/{slug}"

    return AssetCandidate(
        type=AssetType.NFT_COLLECTION,
        provider=ReservoirNftProvider.name,
        provider_asset_id=collection_id,
        symbol=symbol.upper()[:64],
        name=name,
        chain=_chain_name(collection),
        contract_address=contract,
        metadata={
            "slug": slug,
            "image": collection.get("image"),
            "token_count": collection.get("tokenCount"),
            "chain": _chain_name(collection),
            "source": ReservoirNftProvider.name,
        },
        links=links,
    )


def _floor_price(collection: dict[str, Any]) -> dict[str, Decimal | str] | None:
    amount = ((collection.get("floorAsk") or {}).get("price") or {}).get("amount") or {}
    usd = _to_decimal(amount.get("usd"))
    native = _to_decimal(amount.get("native") or amount.get("decimal"))
    if usd is None or native is None:
        return None

    currency = ((collection.get("floorAsk") or {}).get("price") or {}).get("currency") or {}
    native_symbol = str(currency.get("symbol") or collection.get("currency") or "ETH")
    return {"usd": usd, "native": native, "native_symbol": native_symbol}


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _chain_name(collection: dict[str, Any]) -> str:
    chain_id = collection.get("chainId")
    chains = {
        1: "ethereum",
        10: "optimism",
        56: "bsc",
        137: "polygon",
        42161: "arbitrum",
        8453: "base",
    }
    return chains.get(chain_id, str(chain_id or "ethereum"))


async def _sleep_before_retry(response: aiohttp.ClientResponse, attempt: int) -> None:
    retry_after = response.headers.get("retry-after")
    if retry_after:
        try:
            await asyncio.sleep(min(float(retry_after), 5))
            return
        except ValueError:
            pass
    await asyncio.sleep(0.5 * (2**attempt))
