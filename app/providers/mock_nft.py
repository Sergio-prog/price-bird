from __future__ import annotations

from app.db.enums import AssetType
from app.db.models import Asset
from app.providers.base import AssetCandidate, PriceQuote


class NftPlaceholderProvider:
    name = "nft_placeholder"

    async def search_assets(self, query: str, *, nft: bool = False) -> list[AssetCandidate]:
        if not nft:
            return []
        # Replace with Reservoir/OpenSea/Magic Eden adapter when API keys are chosen.
        return [
            AssetCandidate(
                type=AssetType.NFT_COLLECTION,
                provider=self.name,
                provider_asset_id=f"manual:{query.lower()}",
                symbol=query.upper(),
                name=f"{query} floor",
                metadata={"note": "placeholder NFT provider"},
            )
        ]

    async def get_price(self, asset: Asset) -> PriceQuote:
        raise LookupError("NFT floor provider is not configured yet")
