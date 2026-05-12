from __future__ import annotations

import json

import redis.asyncio as redis

REFRESH_QUEUE = "queue:asset_refresh"
NOTIFICATION_QUEUE = "queue:notifications"


async def enqueue_asset_refresh(client: redis.Redis, asset_id: int) -> None:
    await client.lpush(REFRESH_QUEUE, json.dumps({"asset_id": asset_id}))


async def dequeue_asset_refresh(client: redis.Redis) -> int | None:
    payload = await client.rpop(REFRESH_QUEUE)
    if payload is None:
        return None
    return int(json.loads(payload)["asset_id"])


async def enqueue_notification(client: redis.Redis, event_id: int) -> None:
    await client.lpush(NOTIFICATION_QUEUE, json.dumps({"event_id": event_id}))


async def dequeue_notification(client: redis.Redis) -> int | None:
    payload = await client.rpop(NOTIFICATION_QUEUE)
    if payload is None:
        return None
    return int(json.loads(payload)["event_id"])
