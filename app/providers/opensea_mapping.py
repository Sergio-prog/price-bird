from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from app.core.config import settings
from app.db.enums import AssetType
from app.providers.base import AssetCandidate
from app.utils.parsing import to_decimal


def candidate_from_collection(collection: dict[str, Any], *, provider_name: str) -> AssetCandidate:
    slug = collection.get("collection") or collection.get("slug") or collection.get("collection_slug")
    if not slug:
        raise ValueError("OpenSea collection is missing slug")

    name = collection.get("name") or slug
    image = collection.get("image_url") or collection.get("image")
    contract = collection.get("contract") or collection.get("primary_asset_contracts")
    if isinstance(contract, list):
        contract = (contract[0] or {}).get("address") if contract else None

    links = {"opensea": f"https://opensea.io/collection/{slug}"}
    if collection.get("external_url"):
        links["website"] = collection["external_url"]

    return AssetCandidate(
        type=AssetType.NFT_COLLECTION,
        provider=provider_name,
        provider_asset_id=str(slug),
        symbol=str(slug).upper()[:64],
        name=name,
        chain=chain_name(collection),
        contract_address=contract,
        metadata={
            "image": image,
            "description": collection.get("description"),
            "chain": chain_name(collection),
            "source": provider_name,
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
    candidates = [
        ((payload.get("total") or {}).get("floor_price")),
        payload.get("floor_price"),
        ((payload.get("stats") or {}).get("floor_price")),
    ]
    for candidate in candidates:
        value = to_decimal(candidate)
        if value is not None:
            return value
    return None


def chain_name(collection: dict[str, Any]) -> str:
    chain = collection.get("chain") or collection.get("chain_identifier") or settings.opensea_chain
    if isinstance(chain, str):
        return chain.lower()
    return "ethereum"
