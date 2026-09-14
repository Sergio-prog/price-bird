from __future__ import annotations

from sqlalchemy import delete, exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.enums import AlertLimitKind, AlertStatus
from app.db.models import Alert, AlertLimit, Asset, UserAlertLimit

LIMITED_ALERT_STATUSES = (AlertStatus.ACTIVE.value, AlertStatus.PAUSED.value)


async def get_alert_limit(session: AsyncSession, kind: AlertLimitKind, *, lock: bool = False) -> AlertLimit:
    query = select(AlertLimit).where(AlertLimit.asset_kind == kind.value)
    limit = await session.scalar(query.with_for_update() if lock else query)
    if limit is None:
        raise LookupError(f"alert limit for {kind.value} is not configured")
    return limit


async def user_max_alerts(session: AsyncSession, *, user_id: int, limit: AlertLimit) -> int:
    override = await session.scalar(
        select(UserAlertLimit.max_alerts).where(
            UserAlertLimit.user_id == user_id,
            UserAlertLimit.asset_kind == limit.asset_kind,
        )
    )
    return limit.default_user_max_alerts if override is None else override


async def count_limited_alerts(session: AsyncSession, kind: AlertLimitKind, *, user_id: int | None = None) -> int:
    query = (
        select(func.count())
        .select_from(Alert)
        .join(Asset)
        .where(Asset.type.in_(kind.asset_types), Alert.status.in_(LIMITED_ALERT_STATUSES))
    )
    if user_id is not None:
        query = query.where(Alert.user_id == user_id)
    return await session.scalar(query) or 0


async def count_watched_assets(session: AsyncSession, kind: AlertLimitKind) -> int:
    return (
        await session.scalar(
            select(func.count(func.distinct(Alert.asset_id)))
            .join(Asset)
            .where(Asset.type.in_(kind.asset_types), Alert.status.in_(LIMITED_ALERT_STATUSES))
        )
        or 0
    )


async def is_asset_watched(session: AsyncSession, asset_id: int) -> bool:
    return bool(
        await session.scalar(select(exists().where(Alert.asset_id == asset_id, Alert.status.in_(LIMITED_ALERT_STATUSES))))
    )


async def update_alert_limit(
    session: AsyncSession,
    kind: AlertLimitKind,
    *,
    max_watched_assets: int | None = None,
    max_active_alerts: int | None = None,
    default_user_max_alerts: int | None = None,
) -> AlertLimit:
    limit = await get_alert_limit(session, kind, lock=True)
    if max_watched_assets is not None:
        limit.max_watched_assets = max_watched_assets
    if max_active_alerts is not None:
        limit.max_active_alerts = max_active_alerts
    if default_user_max_alerts is not None:
        limit.default_user_max_alerts = default_user_max_alerts
    await session.flush()
    return limit


async def set_user_alert_limit(session: AsyncSession, *, user_id: int, kind: AlertLimitKind, max_alerts: int | None) -> None:
    if max_alerts is None:
        await session.execute(
            delete(UserAlertLimit).where(UserAlertLimit.user_id == user_id, UserAlertLimit.asset_kind == kind.value)
        )
        return
    await session.execute(
        insert(UserAlertLimit)
        .values(user_id=user_id, asset_kind=kind.value, max_alerts=max_alerts)
        .on_conflict_do_update(
            index_elements=[UserAlertLimit.user_id, UserAlertLimit.asset_kind],
            set_={"max_alerts": max_alerts, "updated_at": func.now()},
        )
    )
