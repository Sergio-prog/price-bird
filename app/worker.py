from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Sequence

import redis.asyncio as redis
from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.alerts.service import evaluate_asset_quote
from app.core.config import settings
from app.db import repositories as repo
from app.db.enums import AssetType
from app.db.models import Asset
from app.db.session import SessionLocal
from app.providers.base import PriceQuote
from app.providers.registry import provider_registry
from app.utils.redis import get_redis

logger = logging.getLogger(__name__)

REFRESH_CHUNK_SIZE = 30
PROVIDER_LOCK_SECONDS = 900


def refresh_interval_for(asset: Asset) -> int:
    if asset.type == AssetType.NFT_COLLECTION.value:
        return settings.nft_refresh_interval_seconds
    return settings.price_refresh_interval_seconds


def refreshed_key(asset_id: int) -> str:
    return f"asset_refresh:done:{asset_id}"


async def due_assets(client: redis.Redis, assets: Sequence[Asset]) -> list[Asset]:
    slow = [asset for asset in assets if refresh_interval_for(asset) > settings.price_refresh_interval_seconds]
    if not slow:
        return list(assets)
    marks = await client.mget([refreshed_key(asset.id) for asset in slow])
    fresh = {asset.id for asset, mark in zip(slow, marks, strict=True) if mark is not None}
    return [asset for asset in assets if asset.id not in fresh]


async def mark_refreshed(client: redis.Redis, asset: Asset) -> None:
    interval = refresh_interval_for(asset)
    if interval <= settings.price_refresh_interval_seconds:
        return
    await client.set(refreshed_key(asset.id), "1", ex=max(1, interval - settings.price_refresh_interval_seconds // 2))


class RefreshScheduler:
    def __init__(self, client: redis.Redis) -> None:
        self.client = client
        self.tasks: dict[str, asyncio.Task[None]] = {}

    async def run(self) -> None:
        logger.info(
            "Asset refresh scheduler started; interval=%ss nft_interval=%ss",
            settings.price_refresh_interval_seconds,
            settings.nft_refresh_interval_seconds,
        )
        try:
            while True:
                try:
                    await self.tick()
                except Exception:
                    logger.exception("Asset refresh tick failed")
                await asyncio.sleep(settings.price_refresh_interval_seconds)
        finally:
            for task in self.tasks.values():
                task.cancel()
            logger.info("Asset refresh scheduler stopped")

    async def tick(self) -> None:
        async with SessionLocal() as session:
            assets = await repo.active_watched_assets(session)
        due = await due_assets(self.client, assets)
        grouped: dict[str, list[Asset]] = defaultdict(list)
        for asset in due:
            grouped[asset.provider].append(asset)
        logger.info("Scheduling refreshes; active=%s due=%s providers=%s", len(assets), len(due), sorted(grouped))
        for provider_name, items in grouped.items():
            task = self.tasks.get(provider_name)
            if task is not None and not task.done():
                logger.info("Provider refresh still running; provider=%s pending=%s", provider_name, len(items))
                continue
            self.tasks[provider_name] = asyncio.create_task(
                self.refresh_provider(provider_name, items), name=f"refresh:{provider_name}"
            )

    async def refresh_provider(self, provider_name: str, assets: list[Asset]) -> None:
        lock = self.client.lock(f"lock:provider_refresh:{provider_name}", timeout=PROVIDER_LOCK_SECONDS)
        if not await lock.acquire(blocking=False):
            logger.info("Skipped provider refresh because another worker holds the lock; provider=%s", provider_name)
            return
        try:
            provider = provider_registry.provider_for(provider_name)
            for start in range(0, len(assets), REFRESH_CHUNK_SIZE):
                chunk = assets[start : start + REFRESH_CHUNK_SIZE]
                quotes = await provider.get_prices(chunk)
                for asset in chunk:
                    quote = quotes.get(asset.id)
                    if quote is None:
                        logger.warning(
                            "No quote for asset; asset_id=%s symbol=%s provider=%s", asset.id, asset.symbol, provider_name
                        )
                        continue
                    if await evaluate_asset(asset.id, quote):
                        await mark_refreshed(self.client, asset)
        except Exception:
            logger.exception("Provider refresh failed; provider=%s", provider_name)
        finally:
            try:
                await lock.release()
            except Exception:
                logger.warning("Provider refresh lease expired; provider=%s", provider_name)


async def evaluate_asset(asset_id: int, quote: PriceQuote) -> bool:
    async with SessionLocal() as session:
        asset = await session.scalar(
            select(Asset).where(Asset.id == asset_id).with_for_update().options(selectinload(Asset.links))
        )
        if asset is None:
            logger.warning("Skipped asset evaluation because asset no longer exists; asset_id=%s", asset_id)
            return False
        try:
            event_ids = await evaluate_asset_quote(session, asset, quote)
        except Exception:
            logger.exception("Failed to evaluate asset %s", asset_id)
            await session.rollback()
            return False
        await session.commit()
        logger.info(
            "Refreshed asset; asset_id=%s symbol=%s provider=%s triggered_events=%s",
            asset.id,
            asset.symbol,
            asset.provider,
            len(event_ids),
        )
        return True


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
    client = get_redis()
    try:
        await asyncio.gather(RefreshScheduler(client).run(), process_notifications())
    finally:
        await provider_registry.close()
        await client.aclose()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
