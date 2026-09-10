from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol

from app.db.enums import AssetType
from app.db.models import Asset


@dataclass(frozen=True)
class AssetCandidate:
    type: AssetType
    provider: str
    provider_asset_id: str
    symbol: str
    name: str | None = None
    chain: str | None = None
    contract_address: str | None = None
    metadata: dict = field(default_factory=dict)
    links: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PriceQuote:
    price_usd: Decimal
    source: str
    raw: dict
    price_native: Decimal | None = None
    native_symbol: str | None = None
    market_cap_usd: Decimal | None = None


class ProviderConfigurationError(RuntimeError):
    pass


class PriceProvider(Protocol):
    name: str

    async def search_assets(self, query: str, *, nft: bool = False) -> list[AssetCandidate]: ...

    async def get_price(self, asset: Asset) -> PriceQuote: ...
