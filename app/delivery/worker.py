from __future__ import annotations

import asyncio
import logging
import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from html import escape
from urllib.parse import urlsplit
from uuid import uuid4

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import selectinload

from app.alerts.formatting import (
    format_amount,
    format_change,
    format_decimal,
    format_percent,
    format_threshold,
    venue_label,
)
from app.alerts.icons import asset_icon, dex_label, icon, with_icon
from app.alerts.links import format_links
from app.bot.keyboards import notification_keyboard
from app.db.enums import AlertStatus, AlertType, AssetType
from app.db.models import Alert, ConnectedApp, Delivery, User
from app.db.repositories.users import has_bot_access
from app.db.session import SessionLocal
from app.delivery.legacy import route_legacy_events
from app.delivery.webhook import DeliveryError, send_webhook
from app.i18n import resolve_locale, t, use_locale
from app.integrations.access import can_use_connection
from app.preferences import in_quiet_hours, quiet_hours, timezone_offset_minutes

logger = logging.getLogger(__name__)


def render_payload(payload: dict) -> str:
    if payload["type"] == "connection.test":
        return t("notification-test")
    asset, observation, rule, trigger = payload["asset"], payload["observation"], payload["rule"], payload["trigger"]
    links = _safe_links(payload.get("links") or {})
    source = observation["source"]
    source_link = links.pop(source, None)
    source_text = format_links({source: source_link}) if source_link else escape(_source_label(source, asset))
    heading = with_icon(
        asset_icon(asset.get("kind"), asset.get("chain"), asset.get("exchange")), f"<b>{escape(asset['symbol'])}</b>"
    )
    lines = [
        f"{_trigger_emoji(trigger)} {heading} {_format_change(trigger)}",
        "",
        t("notification-rule", rule=_format_rule(rule)),
        _format_observation(asset, observation),
        *_format_market_cap(observation),
        *_format_dex(asset),
        "",
        t("notification-source", source=source_text),
    ]
    if links:
        lines.append(t("notification-links", links=format_links(links)))
    if payload.get("note"):
        lines.append(t("notification-note", note=escape(payload["note"])))
    return "\n".join(lines)


def _format_rule(rule: dict) -> str:
    alert_type = rule["type"]
    try:
        threshold = Decimal(rule["threshold"])
    except (InvalidOperation, TypeError, ValueError):
        return f"{escape(alert_type.replace('_', ' ').capitalize())} {escape(str(rule['threshold']))}"

    if alert_type == AlertType.PERCENT_CHANGE.value:
        direction = rule.get("direction") if rule.get("direction") in {"up", "down"} else "both"
        return t(f"rule-percent-{direction}", threshold=format_percent(threshold))

    compact = alert_type in {AlertType.MCAP_ABOVE.value, AlertType.MCAP_BELOW.value}
    formatted = escape(format_threshold(alert_type, threshold, rule.get("threshold_currency") or "USD", compact=compact))
    keys = {
        AlertType.PRICE_ABOVE.value: "rule-price-above",
        AlertType.PRICE_BELOW.value: "rule-price-below",
        AlertType.MCAP_ABOVE.value: "rule-mcap-above",
        AlertType.MCAP_BELOW.value: "rule-mcap-below",
        AlertType.ABSOLUTE_CHANGE.value: "rule-absolute",
    }
    if alert_type not in keys:
        return f"{escape(alert_type.replace('_', ' ').capitalize())} {formatted}"
    return t(keys[alert_type], threshold=formatted)


def _format_observation(asset: dict, observation: dict) -> str:
    usd = _format_usd(observation["price_usd"])
    if asset.get("kind") == AssetType.NFT_COLLECTION.value and observation.get("price_native"):
        native = _format_decimal_value(observation["price_native"])
        symbol = escape(observation.get("native_symbol") or "")
        return t("notification-floor", native=native, symbol=symbol, usd=usd)
    return t("notification-price", price=usd)


def _format_market_cap(observation: dict) -> list[str]:
    try:
        market_cap = Decimal(observation.get("market_cap_usd") or "")
    except (InvalidOperation, TypeError, ValueError):
        return []
    return [t("notification-market-cap", value=format_amount(market_cap, compact=True))]


def _format_change(trigger: dict) -> str:
    try:
        return format_change(Decimal(trigger["percent_change"]), trigger.get("direction"))
    except (InvalidOperation, TypeError, ValueError, KeyError):
        return f"{escape(str(trigger.get('percent_change')))}%"


def _format_usd(value) -> str:
    try:
        return format_amount(Decimal(value))
    except (InvalidOperation, TypeError, ValueError):
        return escape(str(value))


def _format_decimal_value(value: str) -> str:
    try:
        return format_decimal(Decimal(value))
    except (InvalidOperation, TypeError, ValueError):
        return escape(str(value))


def _safe_links(links: dict) -> dict[str, str]:
    return {str(name): str(url) for name, url in links.items() if isinstance(url, str) and urlsplit(url).scheme == "https"}


def _source_label(source: str, asset: dict) -> str:
    if source == "ccxt" and asset.get("exchange"):
        return venue_label(asset["exchange"])
    return {"dexscreener": "DexScreener", "opensea": "OpenSea"}.get(
        source,
        source.replace("_", " ").title(),
    )


def _trigger_emoji(trigger: dict) -> str:
    return "🩸" if trigger.get("direction") == "down" else "🚀"


def _format_dex(asset: dict) -> list[str]:
    dex = asset.get("dex")
    if not dex or not isinstance(dex, str):
        return []
    return [t("notification-dex", dex=with_icon(icon(dex), escape(dex_label(dex))))]


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
            connection = (
                await session.scalar(
                    select(ConnectedApp)
                    .where(ConnectedApp.id == delivery.connection_id)
                    .options(selectinload(ConnectedApp.integration_definition))
                )
                if delivery.connection_id
                else None
            )
            if not has_bot_access(user) or (delivery.destination == "bird" and not user.bird_enabled):
                status = "cancelled"
            elif delivery.connection_id and (
                connection is None or not connection.enabled or connection.deleted or not can_use_connection(user, connection)
            ):
                status = "cancelled"
            elif connection:
                await send_webhook(connection, delivery.id, delivery.payload)
            else:
                with use_locale(resolve_locale(user.language, user.language_code)):
                    text = render_payload(delivery.payload)
                    reply_markup = await _notification_markup(session, delivery)
                await bot.send_message(
                    user.telegram_id,
                    text,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                    disable_web_page_preview=True,
                    disable_notification=in_quiet_hours(
                        datetime.now(UTC),
                        quiet_hours(user),
                        timezone_offset_minutes(user),
                    ),
                    request_timeout=10,
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


async def _notification_markup(session, delivery: Delivery):
    alert_id = delivery.payload.get("alert_id")
    if not str(alert_id or "").isdigit():
        return None
    alert = await session.get(Alert, int(alert_id))
    if alert is None or alert.user_id != delivery.user_id:
        return None
    if alert.status not in {AlertStatus.ACTIVE.value, AlertStatus.PAUSED.value}:
        return None
    return notification_keyboard(alert.id)


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
