from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.evaluator import evaluate_alert
from app.alerts.formatting import format_percent, format_threshold, venue_label
from app.alerts.limits import ensure_alert_capacity
from app.alerts.parser import ParsedAlertCommand
from app.db import repositories as repo
from app.db.enums import AlertType, AssetType
from app.db.models import Alert, Asset
from app.delivery.events import queue_event
from app.i18n import LocalizedError, t
from app.providers.base import PriceQuote
from app.providers.registry import provider_registry
from app.utils.amounts import resolve_currency
from app.utils.currency import canonical_symbol

MOVE_ALERT_TYPES = {AlertType.PERCENT_CHANGE.value, AlertType.ABSOLUTE_CHANGE.value}
MIN_COOLDOWN_SECONDS = 10
DEFAULT_COOLDOWN_SECONDS = MIN_COOLDOWN_SECONDS
COOLDOWN_PRESETS = (10, 60, 300, 900, 3600)


async def create_alert_from_command(
    session: AsyncSession,
    *,
    user_id: int,
    parsed: ParsedAlertCommand,
    selected_asset: Asset,
    repeat: bool | None = None,
    cooldown_seconds: int | None = None,
) -> Alert:
    if (
        not parsed.threshold_value.is_finite()
        or parsed.threshold_value <= 0
        or parsed.threshold_value >= Decimal("1e42")
        or parsed.threshold_value.as_tuple().exponent < -36
    ):
        raise LocalizedError("error-threshold-range")
    quote = await provider_registry.get_price(selected_asset)
    if not quote.price_usd.is_finite() or quote.price_usd <= 0:
        raise LocalizedError("error-no-price")
    if parsed.alert_type in {AlertType.MCAP_ABOVE, AlertType.MCAP_BELOW} and (
        quote.market_cap_usd is None or quote.market_cap_usd <= 0
    ):
        raise LocalizedError("error-mcap-unavailable")
    threshold_currency = threshold_currency_for(parsed, selected_asset, quote)
    await ensure_alert_capacity(session, user_id=user_id, asset=selected_asset)
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
        repeat=repeat,
        threshold_currency=threshold_currency,
        cooldown_seconds=cooldown_seconds or DEFAULT_COOLDOWN_SECONDS,
    )


def threshold_currency_for(parsed: ParsedAlertCommand, asset: Asset, quote) -> str:
    if parsed.alert_type == AlertType.PERCENT_CHANGE:
        return "USD"
    native_symbol = canonical_symbol(quote.native_symbol) if quote.price_native else None
    default = native_symbol if native_symbol and asset.type == AssetType.NFT_COLLECTION.value else "USD"
    return resolve_currency(parsed.threshold_currency, default=default, native_symbol=native_symbol)


async def refresh_and_evaluate_asset(session: AsyncSession, asset: Asset) -> list[int]:
    quote = await provider_registry.get_price(asset)
    return await evaluate_asset_quote(session, asset, quote)


async def evaluate_asset_quote(session: AsyncSession, asset: Asset, quote: PriceQuote) -> list[int]:
    if not quote.price_usd.is_finite() or quote.price_usd <= 0:
        raise ValueError("No valid price available")
    snapshot = None
    event_ids: list[int] = []
    for alert in await repo.active_alerts_for_asset(session, asset.id):
        if alert.expires_at is not None and alert.expires_at <= datetime.now(UTC):
            alert.status = "paused"
            continue
        result = evaluate_alert(alert, quote.price_usd, quote.market_cap_usd, quote.price_native)
        if not repo.has_bot_access(alert.user):
            continue
        # Unavailable metrics cannot rearm an alert.
        if result.direction is None:
            continue
        if not result.triggered:
            alert.armed = True
            continue
        at = datetime.now(UTC)
        repeating_move = alert.repeat and alert.type in MOVE_ALERT_TYPES
        if (not repeating_move and not alert.armed) or (
            alert.last_triggered_at is not None and (at - alert.last_triggered_at).total_seconds() < alert.cooldown_seconds
        ):
            continue
        if snapshot is None:
            snapshot = await repo.create_snapshot(
                session,
                asset_id=asset.id,
                price_usd=quote.price_usd,
                price_native=quote.price_native,
                native_symbol=quote.native_symbol,
                source=quote.source,
                raw=quote.raw,
            )
        event = await repo.create_alert_event(
            session,
            alert_id=alert.id,
            snapshot_id=snapshot.id,
            direction=result.direction.value,
            percent_change=result.percent_change.quantize(Decimal("0.0001")),
        )
        alert.armed = repeating_move
        alert.last_triggered_at = at
        await queue_event(session, event, alert, asset, quote)
        if not alert.repeat:
            await repo.mark_alert_triggered(session, alert.id)
        elif alert.type in MOVE_ALERT_TYPES:
            alert.baseline_price = quote.price_usd
        event_ids.append(event.id)
    return event_ids


def describe_alert(alert: Alert) -> str:
    symbol = alert.asset.symbol if alert.asset else t("asset-fallback")
    if alert.type == AlertType.PERCENT_CHANGE.value:
        direction = alert.direction if alert.direction in {"up", "down"} else "both"
        return t(f"describe-percent-{direction}", symbol=symbol, threshold=format_percent(alert.threshold_value))
    threshold = format_threshold(alert.type, alert.threshold_value, alert_currency(alert))
    key = {
        AlertType.PRICE_ABOVE.value: "describe-price-above",
        AlertType.PRICE_BELOW.value: "describe-price-below",
        AlertType.MCAP_ABOVE.value: "describe-mcap-above",
        AlertType.MCAP_BELOW.value: "describe-mcap-below",
    }.get(alert.type, "describe-absolute")
    return t(key, symbol=symbol, threshold=threshold)


def alert_currency(alert: Alert) -> str:
    return getattr(alert, "threshold_currency", None) or "USD"


def asset_kind_label(asset: Asset) -> str:
    if asset.type == AssetType.NFT_COLLECTION.value:
        return t("market-nft")
    if asset.type == AssetType.CEX_SYMBOL.value:
        exchange = (asset.extra or {}).get("exchange")
        return venue_label(exchange) if exchange else t("market-cex")
    return asset.chain or t("market-token")
