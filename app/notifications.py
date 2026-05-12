from __future__ import annotations

from datetime import UTC, datetime

from aiogram import Bot
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.links import build_asset_links, format_links
from app.core.config import settings
from app.db.enums import NotificationStatus
from app.db.models import AlertEvent


def render_alert_message(event: AlertEvent) -> str:
    alert = event.alert
    asset = alert.asset
    snapshot = event.snapshot
    direction_icon = "UP" if event.direction == "up" else "DOWN"
    links = format_links(build_asset_links(asset))
    body = [
        f"Price alert triggered: {asset.symbol}",
        f"Direction: {direction_icon}",
        f"Current: ${snapshot.price_usd.normalize()}",
        f"Baseline: ${alert.baseline_price.normalize()}",
        f"Change: {event.percent_change.normalize()}%",
    ]
    if links:
        body.extend(["", links])
    return "\n".join(body)


async def send_alert_notification(session: AsyncSession, bot: Bot, event: AlertEvent) -> None:
    try:
        await bot.send_message(event.alert.user.telegram_id, render_alert_message(event), disable_web_page_preview=True)
    except Exception:
        attempts = event.notification_attempts + 1
        status = (
            NotificationStatus.FAILED.value
            if attempts >= settings.notification_max_attempts
            else NotificationStatus.QUEUED.value
        )
        await session.execute(
            update(AlertEvent)
            .where(AlertEvent.id == event.id)
            .values(notification_attempts=attempts, notification_status=status)
        )
        raise
    else:
        await session.execute(
            update(AlertEvent)
            .where(AlertEvent.id == event.id)
            .values(
                notification_status=NotificationStatus.SENT.value,
                notification_attempts=event.notification_attempts + 1,
                notified_at=datetime.now(UTC),
            )
        )
