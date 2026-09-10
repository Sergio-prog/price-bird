from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlsplit
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.links import build_asset_links
from app.db.models import Alert, AlertEvent, Asset, ConnectedApp, Delivery


async def queue_event(session: AsyncSession, event: AlertEvent, alert: Alert, asset: Asset, quote) -> None:
    event.notification_status = "routed"
    payload = {
        "schema_version": 1,
        "type": "alert.triggered",
        "event_id": str(uuid4()),
        "occurred_at": (event.created_at or datetime.now(UTC)).isoformat(),
        "alert_id": str(alert.id),
        "note": alert.note,
        "links": {
            name: url
            for name, url in list(build_asset_links(asset).items())[:2]
            if len(url) <= 400 and urlsplit(url).scheme == "https"
        },
        "recipient_telegram_id": str(alert.user.telegram_id),
        "asset": {"symbol": asset.symbol, "kind": asset.type, "chain": asset.chain, "address": asset.contract_address},
        "rule": {
            "type": alert.type,
            "threshold": str(alert.threshold_value),
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
