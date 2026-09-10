from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.enums import AlertStatus
from app.db.models import Alert, Asset, User


async def create_alert(
    session: AsyncSession,
    *,
    user_id: int,
    asset_id: int,
    alert_type: str,
    baseline_price: Decimal,
    threshold_value: Decimal,
    direction: str,
    repeat: bool | None = None,
) -> Alert:
    alert = Alert(
        user_id=user_id,
        asset_id=asset_id,
        type=alert_type,
        baseline_price=baseline_price,
        threshold_value=threshold_value,
        direction=direction,
        repeat=alert_type == "percent_change" if repeat is None else repeat,
    )
    session.add(alert)
    await session.flush()
    return alert


async def active_alerts_for_user(session: AsyncSession, telegram_id: int) -> Sequence[Alert]:
    result = await session.scalars(
        select(Alert)
        .join(User)
        .options(selectinload(Alert.asset).selectinload(Asset.links))
        .where(
            User.telegram_id == telegram_id,
            Alert.status.in_([AlertStatus.ACTIVE.value, AlertStatus.PAUSED.value]),
        )
        .order_by(Alert.created_at.desc())
    )
    return result.all()


async def delete_active_alert_for_user(session: AsyncSession, *, telegram_id: int, alert_id: int) -> bool:
    alert = await session.scalar(
        select(Alert)
        .join(User)
        .where(
            Alert.id == alert_id,
            User.telegram_id == telegram_id,
            Alert.status.in_([AlertStatus.ACTIVE.value, AlertStatus.PAUSED.value]),
        )
    )
    if alert is None:
        return False

    alert.status = AlertStatus.DELETED.value
    await session.flush()
    return True


async def active_alerts_for_asset(session: AsyncSession, asset_id: int) -> Sequence[Alert]:
    result = await session.scalars(
        select(Alert)
        .options(selectinload(Alert.user), selectinload(Alert.asset).selectinload(Asset.links))
        .with_for_update()
        .where(Alert.asset_id == asset_id, Alert.status == AlertStatus.ACTIVE.value)
    )
    return result.all()


async def active_watched_assets(session: AsyncSession) -> Sequence[Asset]:
    result = await session.scalars(
        select(Asset).join(Alert).options(selectinload(Asset.links)).where(Alert.status == AlertStatus.ACTIVE.value).distinct()
    )
    return result.all()


async def mark_alert_triggered(session: AsyncSession, alert_id: int) -> None:
    await session.execute(
        update(Alert)
        .where(Alert.id == alert_id, Alert.status == AlertStatus.ACTIVE.value)
        .values(status=AlertStatus.TRIGGERED.value, triggered_at=datetime.now(UTC))
    )
