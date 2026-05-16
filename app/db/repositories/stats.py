from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import AlertStatus
from app.db.models import Alert, User


async def get_stats(session: AsyncSession) -> dict[str, int]:
    users = await session.scalar(select(func.count()).select_from(User))
    active_alerts = await session.scalar(
        select(func.count()).select_from(Alert).where(Alert.status == AlertStatus.ACTIVE.value)
    )
    watched_assets = await session.scalar(
        select(func.count(func.distinct(Alert.asset_id))).where(Alert.status == AlertStatus.ACTIVE.value)
    )
    return {
        "users": int(users or 0),
        "active_alerts": int(active_alerts or 0),
        "watched_assets": int(watched_assets or 0),
    }
