from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.alerts.service import refresh_and_evaluate_asset
from app.core.config import settings
from app.db import repositories as repo
from app.db.models import Alert, AlertEvent, Asset
from app.db.session import SessionLocal
from app.notifications import send_alert_notification
from app.utils.queues import (
    dequeue_asset_refresh,
    dequeue_notification,
    enqueue_asset_refresh,
    enqueue_notification,
)
from app.utils.redis import get_redis

logger = logging.getLogger(__name__)


async def schedule_refreshes() -> None:
    client = get_redis()
    logger.info("Asset refresh scheduler started; interval=%ss", settings.price_refresh_interval_seconds)
    try:
        while True:
            async with SessionLocal() as session:
                assets = await repo.active_watched_assets(session)
                logger.info("Scheduling refreshes for %s active watched assets", len(assets))
                for asset in assets:
                    await enqueue_asset_refresh(client, asset.id)
                    logger.debug(
                        "Queued asset refresh; asset_id=%s symbol=%s provider=%s",
                        asset.id,
                        asset.symbol,
                        asset.provider,
                    )
            await asyncio.sleep(settings.price_refresh_interval_seconds)
    finally:
        logger.info("Asset refresh scheduler stopped")
        await client.aclose()


async def process_refreshes() -> None:
    client = get_redis()
    logger.info("Asset refresh worker started")
    try:
        while True:
            asset_id = await dequeue_asset_refresh(client)
            if asset_id is None:
                await asyncio.sleep(1)
                continue
            lock = client.lock(f"lock:asset_refresh:{asset_id}", timeout=settings.price_refresh_interval_seconds)
            if not await lock.acquire(blocking=False):
                logger.debug("Skipped asset refresh because lock is held; asset_id=%s", asset_id)
                continue
            try:
                async with SessionLocal() as session:
                    asset = await session.scalar(select(Asset).where(Asset.id == asset_id).options(selectinload(Asset.links)))
                    if asset is None:
                        logger.warning("Skipped asset refresh because asset no longer exists; asset_id=%s", asset_id)
                        continue
                    logger.info(
                        "Refreshing asset; asset_id=%s symbol=%s provider=%s chain=%s",
                        asset.id,
                        asset.symbol,
                        asset.provider,
                        asset.chain,
                    )
                    try:
                        event_ids = await refresh_and_evaluate_asset(session, asset)
                    except Exception:
                        logger.exception("Failed to refresh asset %s", asset_id)
                        await session.rollback()
                        continue
                    await session.commit()
                    logger.info(
                        "Refreshed asset; asset_id=%s symbol=%s triggered_events=%s",
                        asset.id,
                        asset.symbol,
                        len(event_ids),
                    )
                for event_id in event_ids:
                    await enqueue_notification(client, event_id)
                    logger.info("Queued alert notification; event_id=%s asset_id=%s", event_id, asset_id)
            finally:
                await lock.release()
    finally:
        logger.info("Asset refresh worker stopped")
        await client.aclose()


async def process_notifications() -> None:
    client = get_redis()
    bot = Bot(settings.bot_token)
    logger.info("Notification worker started")
    try:
        while True:
            event_id = await dequeue_notification(client)
            if event_id is None:
                await asyncio.sleep(1)
                continue
            async with SessionLocal() as session:
                event = await session.scalar(
                    select(AlertEvent)
                    .where(AlertEvent.id == event_id)
                    .options(
                        selectinload(AlertEvent.alert).selectinload(Alert.user),
                        selectinload(AlertEvent.alert).selectinload(Alert.asset).selectinload(Asset.links),
                        selectinload(AlertEvent.snapshot),
                    )
                )
                if event is None:
                    logger.warning("Skipped notification because event no longer exists; event_id=%s", event_id)
                    continue
                try:
                    logger.info("Sending alert notification; event_id=%s alert_id=%s", event.id, event.alert_id)
                    await send_alert_notification(session, bot, event)
                except Exception:
                    logger.exception("Failed to send notification for event %s", event_id)
                await session.commit()
                logger.info("Notification processed; event_id=%s", event_id)
    finally:
        logger.info("Notification worker stopped")
        await bot.session.close()
        await client.aclose()


async def async_main() -> None:
    logging.basicConfig(level=logging.INFO)
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is required")
    await asyncio.gather(schedule_refreshes(), process_refreshes(), process_notifications())


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
