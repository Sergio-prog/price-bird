from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.db.enums import AssetType
from app.providers.base import AssetCandidate
from app.utils.parsing import to_decimal


def candidate_from_collection(collection: dict[str, Any], *, provider_name: str) -> AssetCandidate:
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
        provider=provider_name,
        provider_asset_id=collection_id,
        symbol=symbol.upper()[:64],
        name=name,
        chain=chain_name(collection),
        contract_address=contract,
        metadata={
            "slug": slug,
            "image": collection.get("image"),
            "token_count": collection.get("tokenCount"),
            "chain": chain_name(collection),
            "source": provider_name,
        },
        links=links,
    )


def floor_price(collection: dict[str, Any]) -> dict[str, Decimal | str] | None:
    amount = ((collection.get("floorAsk") or {}).get("price") or {}).get("amount") or {}
    usd = to_decimal(amount.get("usd"))
    native = to_decimal(amount.get("native") or amount.get("decimal"))
    if usd is None or native is None:
        return None

    currency = ((collection.get("floorAsk") or {}).get("price") or {}).get("currency") or {}
    native_symbol = str(currency.get("symbol") or collection.get("currency") or "ETH")
    return {"usd": usd, "native": native, "native_symbol": native_symbol}


def chain_name(collection: dict[str, Any]) -> str:
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
