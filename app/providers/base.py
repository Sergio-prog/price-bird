from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol

from app.db.enums import AssetType
from app.db.models import Asset
from app.utils.ratelimit import RateLimited

logger = logging.getLogger(__name__)


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

    async def get_prices(self, assets: Sequence[Asset]) -> dict[int, PriceQuote]: ...

    async def close(self) -> None: ...


async def sequential_prices(
    provider_name: str,
    assets: Sequence[Asset],
    fetch: Callable[[Asset], Awaitable[PriceQuote]],
) -> dict[int, PriceQuote]:
    quotes: dict[int, PriceQuote] = {}
    for asset in assets:
        try:
            quotes[asset.id] = await fetch(asset)
        except RateLimited as exc:
            logger.warning("Stopped provider batch early; provider=%s reason=%s", provider_name, exc)
            break
        except Exception:
            logger.exception("Failed to fetch price; provider=%s asset_id=%s symbol=%s", provider_name, asset.id, asset.symbol)
    return quotes
