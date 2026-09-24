from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlsplit
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.links import build_asset_links
from app.db.enums import AssetType
from app.db.models import Alert, AlertEvent, Asset, ConnectedApp, Delivery
from app.integrations.access import can_use_connection
from app.integrations.catalog import TRENCHBOOK_SLUG
from app.preferences import coin_link_key


async def queue_event(session: AsyncSession, event: AlertEvent, alert: Alert, asset: Asset, quote) -> None:
    event.notification_status = "routed"
    available_links = build_asset_links(asset)
    preferred_link = coin_link_key(getattr(alert.user, "coin_link", None))
    if preferred_link not in available_links and asset.type != AssetType.NFT_COLLECTION.value:
        preferred_link = "tradingview"
    selected_links = {}
    for name in (quote.source, preferred_link):
        url = available_links.get(name)
        if url and len(url) <= 400 and urlsplit(url).scheme == "https":
            selected_links[name] = url
    payload = {
        "schema_version": 1,
        "type": "alert.triggered",
        "event_id": str(uuid4()),
        "occurred_at": (event.created_at or datetime.now(UTC)).isoformat(),
        "alert_id": str(alert.id),
        "note": alert.note,
        "links": selected_links,
        "recipient_telegram_id": str(alert.user.telegram_id),
        "asset": {
            "symbol": asset.symbol,
            "kind": asset.type,
            "chain": asset.chain,
            "address": asset.contract_address,
            "exchange": (asset.extra or {}).get("exchange"),
            "dex": (asset.extra or {}).get("dex_id"),
        },
        "rule": {
            "type": alert.type,
            "threshold": str(alert.threshold_value),
            "threshold_currency": getattr(alert, "threshold_currency", None) or "USD",
            "baseline": str(alert.baseline_price),
            "direction": alert.direction,
        },
        "observation": {
            "price_usd": str(quote.price_usd),
            "source": quote.source,
            "price_native": str(quote.price_native) if quote.price_native is not None else None,
            "native_symbol": quote.native_symbol,
            "market_cap_usd": str(quote.market_cap_usd) if quote.market_cap_usd is not None else None,
        },
        "trigger": {"direction": event.direction, "percent_change": str(event.percent_change)},
    }
    if alert.user.bird_enabled:
        session.add(Delivery(id=str(uuid4()), event_id=event.id, user_id=alert.user_id, destination="bird", payload=payload))
    connections = await session.scalars(
        select(ConnectedApp).where(
            ConnectedApp.user_id == alert.user_id,
            ConnectedApp.enabled.is_(True),
            ConnectedApp.deleted.is_(False),
        )
    )
    for connection in connections:
        if not can_use_connection(alert.user, connection):
            continue
        session.add(
            Delivery(
                id=str(uuid4()),
                event_id=event.id,
                user_id=alert.user_id,
                connection_id=connection.id,
                destination=connection.id,
                payload={**payload, "connection_id": connection.id},
            )
        )


async def queue_test(session: AsyncSession, connection: ConnectedApp, telegram_id: int) -> None:
    session.add(
        Delivery(
            id=str(uuid4()),
            user_id=connection.user_id,
            connection_id=connection.id,
            destination=connection.id,
            payload={
                "schema_version": 1,
                "type": "connection.test",
                "event_id": str(uuid4()),
                "occurred_at": datetime.now(UTC).isoformat(),
                "recipient_telegram_id": str(telegram_id),
                "connection_id": connection.id,
            },
        )
    )


async def queue_trenchbook_debug_alert(session: AsyncSession, user_id: int) -> str | None:
    connection = await session.scalar(
        select(ConnectedApp)
        .join(ConnectedApp.integration_definition)
        .where(
            ConnectedApp.user_id == user_id,
            ConnectedApp.enabled.is_(True),
            ConnectedApp.deleted.is_(False),
            ConnectedApp.integration_definition.has(slug=TRENCHBOOK_SLUG),
        )
        .limit(1)
    )
    if connection is None:
        return None

    previous = await session.scalar(
        select(Delivery)
        .where(Delivery.user_id == user_id, Delivery.event_id.is_not(None))
        .order_by(Delivery.created_at.desc())
        .limit(1)
    )
    if previous is None or previous.payload.get("type") != "alert.triggered":
        return ""

    payload = {
        **previous.payload,
        "event_id": str(uuid4()),
        "connection_id": connection.id,
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    session.add(
        Delivery(
            id=str(uuid4()),
            user_id=user_id,
            connection_id=connection.id,
            destination=connection.id,
            payload=payload,
        )
    )
    return str(payload["alert_id"])
