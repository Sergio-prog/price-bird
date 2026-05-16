from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PriceSnapshot


async def latest_snapshot(session: AsyncSession, asset_id: int) -> PriceSnapshot | None:
    return await session.scalar(
        select(PriceSnapshot).where(PriceSnapshot.asset_id == asset_id).order_by(PriceSnapshot.created_at.desc()).limit(1)
    )


async def create_snapshot(
    session: AsyncSession,
    *,
    asset_id: int,
    price_usd: Decimal,
    source: str,
    raw: dict,
    price_native: Decimal | None = None,
    native_symbol: str | None = None,
) -> PriceSnapshot:
    snapshot = PriceSnapshot(
        asset_id=asset_id,
        price_usd=price_usd,
        price_native=price_native,
        native_symbol=native_symbol,
        source=source,
        raw=raw,
    )
    session.add(snapshot)
    await session.flush()
    return snapshot
