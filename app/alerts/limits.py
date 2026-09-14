from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import repositories as repo
from app.db.enums import AlertLimitKind
from app.db.models import Asset
from app.i18n import LocalizedError


class AlertLimitReached(LocalizedError):
    pass


async def ensure_alert_capacity(session: AsyncSession, *, user_id: int, asset: Asset) -> None:
    kind = AlertLimitKind.for_asset_type(asset.type)
    limit = await repo.get_alert_limit(session, kind, lock=True)
    user_limit = await repo.user_max_alerts(session, user_id=user_id, limit=limit)
    if await repo.count_limited_alerts(session, kind, user_id=user_id) >= user_limit:
        raise AlertLimitReached(f"limit-user-{kind.value}", limit=user_limit)
    if await repo.count_limited_alerts(session, kind) >= limit.max_active_alerts:
        raise AlertLimitReached(f"limit-global-alerts-{kind.value}")
    if not await repo.is_asset_watched(session, asset.id) and await repo.count_watched_assets(session, kind) >= (
        limit.max_watched_assets
    ):
        raise AlertLimitReached(f"limit-global-assets-{kind.value}")
