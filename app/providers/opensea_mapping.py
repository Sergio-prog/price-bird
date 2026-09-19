from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from app.db.enums import AssetType
from app.providers.base import AssetCandidate
from app.utils.currency import canonical_symbol, chain_native_symbol
from app.utils.parsing import to_decimal

DEFAULT_FLOOR_SYMBOL = "ETH"


def candidate_from_collection(collection: dict[str, Any], *, provider_name: str) -> AssetCandidate:
    slug = collection.get("collection") or collection.get("slug") or collection.get("collection_slug")
    if not slug:
        raise ValueError("OpenSea collection is missing slug")

    name = collection.get("name") or slug
    image = collection.get("image_url") or collection.get("image")
    chain = chain_name(collection)

    links = {"opensea": f"https://opensea.io/collection/{slug}"}
    if collection.get("external_url"):
        links["website"] = collection["external_url"]

    return AssetCandidate(
        type=AssetType.NFT_COLLECTION,
        provider=provider_name,
        provider_asset_id=str(slug),
        symbol=str(slug).upper()[:64],
        name=name,
        chain=chain,
        contract_address=collection.get("contract") or _primary_contract(collection).get("address"),
        metadata={
            "image": image,
            "description": collection.get("description"),
            "chain": chain,
            "source": provider_name,
            "native_symbol": chain_native_symbol(chain) or DEFAULT_FLOOR_SYMBOL,
        },
        links=links,
    )


def collections_from_search(payload: dict[str, Any]) -> list[dict[str, Any]]:
    results = payload.get("results")
    if isinstance(results, list):
        return [
            result["collection"]
            for result in results
            if isinstance(result, dict)
            and result.get("type", "collection") == "collection"
            and isinstance(result.get("collection"), dict)
            and not result["collection"].get("is_disabled")
        ]
    collections = payload.get("collections") or payload.get("collection") or []
    if isinstance(collections, dict):
        collections = [collections]
    return [collection for collection in collections if isinstance(collection, dict)]


def slug_variants(query: str) -> list[str]:
    normalized = query.strip().lower()
    hyphenated = re.sub(r"[^a-z0-9-]", "", re.sub(r"\s+", "-", normalized)).strip("-")
    joined = re.sub(r"[^a-z0-9]", "", normalized)
    return [slug for slug in dict.fromkeys([hyphenated, joined]) if slug]


def floor_price(payload: dict[str, Any]) -> Decimal | None:
    return _stat(payload, "floor_price")


def floor_symbol(payload: dict[str, Any]) -> str:
    symbol = (payload.get("total") or {}).get("floor_price_symbol") or payload.get("floor_price_symbol")
    return canonical_symbol(symbol) or DEFAULT_FLOOR_SYMBOL


def market_cap(payload: dict[str, Any]) -> Decimal | None:
    value = _stat(payload, "market_cap")
    return value if value is not None and value > 0 else None


def _stat(payload: dict[str, Any], key: str) -> Decimal | None:
    candidates = [
        ((payload.get("total") or {}).get(key)),
        payload.get(key),
        ((payload.get("stats") or {}).get(key)),
    ]
    for candidate in candidates:
        value = to_decimal(candidate)
        if value is not None:
            return value
    return None


def chain_name(collection: dict[str, Any]) -> str | None:
    chain = collection.get("chain") or collection.get("chain_identifier") or _primary_contract(collection).get("chain")
    return chain.lower() if isinstance(chain, str) else None


def _primary_contract(collection: dict[str, Any]) -> dict[str, Any]:
    contracts = collection.get("contracts") or collection.get("primary_asset_contracts")
    first = contracts[0] if isinstance(contracts, list) and contracts else None
    return first if isinstance(first, dict) else {}
