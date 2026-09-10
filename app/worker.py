from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.alerts.service import refresh_and_evaluate_asset
from app.core.config import settings
from app.db import repositories as repo
from app.db.models import Asset
from app.db.session import SessionLocal
from app.utils.queues import (
    dequeue_asset_refresh,
    enqueue_asset_refresh,
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
            lock = client.lock(f"lock:asset_refresh:{asset_id}", timeout=max(120, settings.price_refresh_interval_seconds))
            if not await lock.acquire(blocking=False):
                logger.debug("Skipped asset refresh because lock is held; asset_id=%s", asset_id)
                continue
            try:
                async with SessionLocal() as session:
                    asset = await session.scalar(
                        select(Asset).where(Asset.id == asset_id).with_for_update().options(selectinload(Asset.links))
                    )
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
            finally:
                try:
                    await lock.release()
                except Exception:
                    logger.warning("Asset refresh lease expired; database locks protected evaluation")
    finally:
        logger.info("Asset refresh worker stopped")
        await client.aclose()


async def process_notifications() -> None:
    from app.delivery.worker import run_deliveries

    bot = Bot(settings.bot_token)
    try:
        await asyncio.gather(*(run_deliveries(bot) for _ in range(4)))
    finally:
        await bot.session.close()


async def async_main() -> None:
    logging.basicConfig(level=logging.INFO)
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is required")
    await asyncio.gather(schedule_refreshes(), process_refreshes(), process_notifications())


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
