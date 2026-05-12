from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.evaluator import evaluate_alert
from app.alerts.parser import ParsedAlertCommand
from app.db import repositories as repo
from app.db.enums import AssetType
from app.db.models import Alert, Asset
from app.providers.registry import provider_registry


async def create_alert_from_command(
    session: AsyncSession,
    *,
    user_id: int,
    parsed: ParsedAlertCommand,
    selected_asset: Asset,
) -> Alert:
    quote = await provider_registry.get_price(selected_asset)
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
        result = evaluate_alert(alert, quote.price_usd)
        if not result.triggered or result.direction is None:
            continue
        event = await repo.create_alert_event(
            session,
            alert_id=alert.id,
            snapshot_id=snapshot.id,
            direction=result.direction.value,
            percent_change=result.percent_change.quantize(Decimal("0.0001")),
        )
        await repo.mark_alert_triggered(session, alert.id)
        event_ids.append(event.id)
    return event_ids


def describe_alert(alert: Alert) -> str:
    symbol = alert.asset.symbol if alert.asset else "asset"
    if alert.type == "percent_change":
        return f"{symbol} +/-{alert.threshold_value.normalize()}%"
    if alert.type == "price_above":
        return f"{symbol} above ${alert.threshold_value.normalize()}"
    if alert.type == "price_below":
        return f"{symbol} below ${alert.threshold_value.normalize()}"
    return f"{symbol} alert"


def asset_kind_label(asset: Asset) -> str:
    if asset.type == AssetType.NFT_COLLECTION.value:
        return "NFT floor"
    if asset.type == AssetType.CEX_SYMBOL.value:
        return "CEX"
    return asset.chain or "token"
