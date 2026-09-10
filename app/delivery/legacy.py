"""Move unsent legacy Telegram events onto the durable queue once."""

from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models import Alert, AlertEvent, Asset
from app.delivery.events import queue_event


async def route_legacy_events(session, limit=100):
    events = list(
        await session.scalars(
            select(AlertEvent)
            .where(AlertEvent.notification_status == "queued")
            .order_by(AlertEvent.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
            .options(
                selectinload(AlertEvent.alert).selectinload(Alert.user),
                selectinload(AlertEvent.alert).selectinload(Alert.asset).selectinload(Asset.links),
                selectinload(AlertEvent.snapshot),
            )
        )
    )
    for event in events:
        # An earlier failed attempt may have reached Telegram. Leave it for operator review.
        if event.notification_attempts:
            event.notification_status = "failed"
            continue
        snapshot = event.snapshot
        quote = SimpleNamespace(
            price_usd=snapshot.price_usd,
            price_native=snapshot.price_native,
            native_symbol=snapshot.native_symbol,
            source=snapshot.source,
            market_cap_usd=None,
        )
        await queue_event(session, event, event.alert, event.alert.asset, quote)

    return len(events)
