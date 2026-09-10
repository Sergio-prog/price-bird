from __future__ import annotations

import asyncio
import logging
import random
from datetime import UTC, datetime, timedelta
from html import escape
from uuid import uuid4

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import and_, or_, select, update

from app.db.models import ConnectedApp, Delivery, User
from app.db.repositories.users import has_bot_access
from app.db.session import SessionLocal
from app.delivery.legacy import route_legacy_events
from app.delivery.webhook import DeliveryError, send_webhook

logger = logging.getLogger(__name__)


def render_payload(payload: dict) -> str:
    if payload["type"] == "connection.test":
        return "Price Bird connection test. No alert was triggered."
    asset, observation, rule = payload["asset"], payload["observation"], payload["rule"]
    return "\n".join(
        [
            f"Alert for <b>{escape(asset['symbol'])}</b>",
            f"Rule: {escape(rule['type'])} {escape(rule['threshold'])}",
            f"Price: ${escape(observation['price_usd'])}",
            *(
                [f"Floor: {escape(observation['price_native'])} {escape(observation['native_symbol'] or '')}"]
                if observation.get("price_native")
                else []
            ),
            f"Change: {escape(payload['trigger']['percent_change'])}%",
            f"Source: {escape(observation['source'])}",
        ]
    )


async def claim_delivery():
    at = datetime.now(UTC)
    async with SessionLocal() as session, session.begin():
        delivery = await session.scalar(
            select(Delivery)
            .where(
                or_(
                    and_(Delivery.status == "pending", Delivery.next_attempt_at <= at),
                    and_(Delivery.status == "sending", Delivery.leased_until <= at),
                )
            )
            .order_by(Delivery.next_attempt_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if delivery is None:
            return None
        delivery.status = "sending"
        delivery.attempts += 1
        delivery.lease_token = str(uuid4())
        delivery.leased_until = at + timedelta(seconds=60)
        await session.flush()
        session.expunge(delivery)
        return delivery


async def process_delivery(delivery: Delivery, bot: Bot) -> None:
    status, error, delay = "sent", None, 0.0
    try:
        async with SessionLocal() as session:
            user = await session.get(User, delivery.user_id)
            connection = await session.get(ConnectedApp, delivery.connection_id) if delivery.connection_id else None
            if not has_bot_access(user) or (delivery.destination == "bird" and not user.bird_enabled):
                status = "cancelled"
            elif delivery.connection_id and (connection is None or not connection.enabled or connection.deleted):
                status = "cancelled"
            elif connection:
                await send_webhook(connection, delivery.id, delivery.payload)
            else:
                await bot.send_message(
                    user.telegram_id, render_payload(delivery.payload), parse_mode="HTML", request_timeout=10
                )
    except TelegramRetryAfter as exc:
        status, error, delay = "pending", "Telegram rate limit", exc.retry_after
    except (TelegramForbiddenError, TelegramBadRequest):
        status, error = "failed", "Telegram rejected delivery"
    except DeliveryError as exc:
        status, error, delay = "pending" if exc.retryable else "failed", str(exc), exc.retry_after
    except Exception:
        # Do not log exception messages: HTTP errors can contain secret URLs.
        status, error = "pending", "Network or delivery failure"
    if status == "pending":
        if delivery.attempts >= 12 or datetime.now(UTC) - delivery.created_at >= timedelta(hours=24):
            status = "failed"
        delay = max(delay, min(3600, 5 * 2 ** min(delivery.attempts, 10)) + random.uniform(0, 5))
    async with SessionLocal() as session, session.begin():
        await session.execute(
            update(Delivery)
            .where(
                Delivery.id == delivery.id,
                Delivery.lease_token == delivery.lease_token,
            )
            .values(
                status=status,
                last_error=error,
                lease_token=None,
                leased_until=None,
                completed_at=datetime.now(UTC) if status == "sent" else None,
                next_attempt_at=datetime.now(UTC) + timedelta(seconds=delay),
            )
        )


async def run_deliveries(bot: Bot) -> None:
    migrating = True
    while True:
        try:
            if migrating:
                async with SessionLocal() as session, session.begin():
                    migrating = await route_legacy_events(session) == 100
            delivery = await claim_delivery()
            if delivery:
                await process_delivery(delivery, bot)
            else:
                await asyncio.sleep(1)
        except Exception:
            logger.error("Delivery worker failed; pending work remains in the database")
            await asyncio.sleep(5)
