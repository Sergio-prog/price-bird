from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.enums import NotificationStatus
from app.db.models import Alert, AlertEvent, Asset


async def create_alert_event(
    session: AsyncSession,
    *,
    alert_id: int,
    snapshot_id: int,
    direction: str,
    percent_change: Decimal,
) -> AlertEvent:
    event = AlertEvent(
        alert_id=alert_id,
        snapshot_id=snapshot_id,
        direction=direction,
        percent_change=percent_change,
        notification_status=NotificationStatus.QUEUED.value,
    )
    session.add(event)
    await session.flush()
    return event


async def queued_alert_events(session: AsyncSession, limit: int = 25) -> Sequence[AlertEvent]:
    stmt: Select[tuple[AlertEvent]] = (
        select(AlertEvent)
        .options(
            selectinload(AlertEvent.alert).selectinload(Alert.user),
            selectinload(AlertEvent.alert).selectinload(Alert.asset).selectinload(Asset.links),
            selectinload(AlertEvent.snapshot),
        )
        .where(AlertEvent.notification_status == NotificationStatus.QUEUED.value)
        .order_by(AlertEvent.created_at.asc())
        .limit(limit)
    )
    result = await session.scalars(stmt)
    return result.all()
