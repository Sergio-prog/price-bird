from __future__ import annotations

from datetime import UTC, datetime
from html import escape

from aiogram import Bot
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.formatting import format_decimal, format_direction, format_percent
from app.alerts.links import build_asset_links, format_links
from app.core.config import settings
from app.db.enums import AssetType, NotificationStatus
from app.db.models import AlertEvent


def render_alert_message(event: AlertEvent) -> str:
    alert = event.alert
    asset = alert.asset
    snapshot = event.snapshot
    links = format_links(build_asset_links(asset))
    current = _format_current_price(event)
    body = [
        f"Alert triggered for <b>{escape(asset.symbol)}</b>",
        f"Direction: {format_direction(event.direction)}",
        f"Current: {current}",
        f"Baseline: ${format_decimal(alert.baseline_price)}",
        f"Change: {format_percent(event.percent_change, signed=True)}",
        f"Source: {escape(snapshot.source)}",
    ]
    if links:
        body.append(f"Links: {links}")
    return "\n".join(body)


def _format_current_price(event: AlertEvent) -> str:
    asset = event.alert.asset
    snapshot = event.snapshot
    if (
        asset.type == AssetType.NFT_COLLECTION.value
        and snapshot.price_native is not None
        and snapshot.native_symbol is not None
    ):
        native_price = format_decimal(snapshot.price_native)
        usd_price = format_decimal(snapshot.price_usd)
        return f"{native_price} {escape(snapshot.native_symbol)} (${usd_price})"
    return f"${format_decimal(snapshot.price_usd)}"


async def send_alert_notification(session: AsyncSession, bot: Bot, event: AlertEvent) -> None:
    try:
        await bot.send_message(
            event.alert.user.telegram_id,
            render_alert_message(event),
            disable_web_page_preview=True,
            parse_mode="HTML",
        )
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
