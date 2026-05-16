from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Asset, ProviderLink


async def upsert_asset_from_candidate(session: AsyncSession, candidate) -> Asset:
    stmt = (
        insert(Asset)
        .values(
            type=candidate.type.value,
            chain=candidate.chain,
            symbol=candidate.symbol.upper(),
            name=candidate.name,
            contract_address=candidate.contract_address,
            provider=candidate.provider,
            provider_asset_id=candidate.provider_asset_id,
            extra=candidate.metadata,
        )
        .on_conflict_do_update(
            constraint="uq_assets_provider_asset",
            set_={
                "chain": candidate.chain,
                "symbol": candidate.symbol.upper(),
                "name": candidate.name,
                "contract_address": candidate.contract_address,
                Asset.extra: candidate.metadata,
                "updated_at": func.now(),
            },
        )
        .returning(Asset.id)
    )
    asset_id = await session.scalar(stmt)
    asset = await session.get(Asset, asset_id)
    if asset is None:
        raise LookupError(f"asset {asset_id} not found")
    for kind, url in candidate.links.items():
        await upsert_provider_link(session, asset_id=asset.id, kind=kind, url=url)
    return asset


async def upsert_provider_link(session: AsyncSession, *, asset_id: int, kind: str, url: str) -> None:
    stmt = (
        insert(ProviderLink)
        .values(asset_id=asset_id, kind=kind, url=url)
        .on_conflict_do_update(
            constraint="uq_provider_links_asset_kind",
            set_={"url": url},
        )
    )
    await session.execute(stmt)
