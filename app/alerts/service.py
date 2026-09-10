from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.evaluator import evaluate_alert
from app.alerts.formatting import format_decimal, format_percent
from app.alerts.parser import ParsedAlertCommand
from app.db import repositories as repo
from app.db.enums import AlertType, AssetType
from app.db.models import Alert, Asset
from app.delivery.events import queue_event
from app.providers.registry import provider_registry


async def create_alert_from_command(
    session: AsyncSession,
    *,
    user_id: int,
    parsed: ParsedAlertCommand,
    selected_asset: Asset,
) -> Alert:
    if (
        not parsed.threshold_value.is_finite()
        or parsed.threshold_value <= 0
        or parsed.threshold_value >= Decimal("1e42")
        or parsed.threshold_value.as_tuple().exponent < -36
    ):
        raise ValueError("Threshold must be positive, finite and fit within 36 decimal places")
    quote = await provider_registry.get_price(selected_asset)
    if not quote.price_usd.is_finite() or quote.price_usd <= 0:
        raise ValueError("No valid price available")
    if parsed.alert_type in {AlertType.MCAP_ABOVE, AlertType.MCAP_BELOW} and (
        quote.market_cap_usd is None or quote.market_cap_usd <= 0
    ):
        raise ValueError("Actual market cap is unavailable for this asset")
    await repo.create_snapshot(
        session,
        asset_id=selected_asset.id,
        price_usd=quote.price_usd,
        price_native=quote.price_native,
        native_symbol=quote.native_symbol,
        source=quote.source,
        raw=quote.raw,
    )
    return await repo.create_alert(
        session,
        user_id=user_id,
        asset_id=selected_asset.id,
        alert_type=parsed.alert_type.value,
        baseline_price=quote.price_usd,
        threshold_value=parsed.threshold_value,
        direction=parsed.direction.value,
    )


async def refresh_and_evaluate_asset(session: AsyncSession, asset: Asset) -> list[int]:
    quote = await provider_registry.get_price(asset)
    if not quote.price_usd.is_finite() or quote.price_usd <= 0:
        raise ValueError("No valid price available")
    snapshot = await repo.create_snapshot(
        session,
        asset_id=asset.id,
        price_usd=quote.price_usd,
        price_native=quote.price_native,
        native_symbol=quote.native_symbol,
        source=quote.source,
        raw=quote.raw,
    )
    event_ids: list[int] = []
    for alert in await repo.active_alerts_for_asset(session, asset.id):
        if alert.expires_at is not None and alert.expires_at <= datetime.now(UTC):
            alert.status = "paused"
            continue
        result = evaluate_alert(alert, quote.price_usd, quote.market_cap_usd)
        if not repo.has_bot_access(alert.user):
            continue
        # Unavailable metrics cannot rearm an alert.
        if result.direction is None:
            continue
        if not result.triggered:
            alert.armed = True
            continue
        at = datetime.now(UTC)
        if not alert.armed or (
            alert.last_triggered_at is not None and (at - alert.last_triggered_at).total_seconds() < alert.cooldown_seconds
        ):
            continue
        event = await repo.create_alert_event(
            session,
            alert_id=alert.id,
            snapshot_id=snapshot.id,
            direction=result.direction.value,
            percent_change=result.percent_change.quantize(Decimal("0.0001")),
        )
        alert.armed = False
        alert.last_triggered_at = at
        await queue_event(session, event, alert, asset, quote)
        if not alert.repeat:
            await repo.mark_alert_triggered(session, alert.id)
        event_ids.append(event.id)
    return event_ids


def describe_alert(alert: Alert) -> str:
    symbol = alert.asset.symbol if alert.asset else "asset"
    if alert.type == "percent_change":
        return f"{symbol} moves {format_percent(alert.threshold_value)} up or down"
    if alert.type == "price_above":
        return f"{symbol} above ${format_decimal(alert.threshold_value)}"
    if alert.type == "price_below":
        return f"{symbol} below ${format_decimal(alert.threshold_value)}"
    if alert.type in {"mcap_above", "mcap_below"}:
        return (
            f"{symbol} market cap {'above' if alert.type == 'mcap_above' else 'below'} ${format_decimal(alert.threshold_value)}"
        )
    return f"{symbol} absolute change ${format_decimal(alert.threshold_value)}"


def asset_kind_label(asset: Asset) -> str:
    if asset.type == AssetType.NFT_COLLECTION.value:
        return "NFT floor"
    if asset.type == AssetType.CEX_SYMBOL.value:
        return "CEX"
    return asset.chain or "token"
