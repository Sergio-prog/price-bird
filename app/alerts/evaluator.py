from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.db.enums import AlertDirection, AlertType
from app.db.models import Alert


@dataclass(frozen=True)
class EvaluationResult:
    triggered: bool
    direction: AlertDirection | None
    percent_change: Decimal


def evaluate_alert(
    alert: Alert,
    current_price: Decimal,
    market_cap: Decimal | None = None,
    price_native: Decimal | None = None,
) -> EvaluationResult:
    if not current_price.is_finite() or current_price <= 0 or alert.baseline_price <= 0:
        return EvaluationResult(False, None, Decimal("0"))

    percent_change = ((current_price - alert.baseline_price) / alert.baseline_price) * Decimal("100")
    direction = AlertDirection.UP if percent_change >= 0 else AlertDirection.DOWN
    native = getattr(alert, "threshold_currency", "USD") != "USD"
    if native and (price_native is None or not price_native.is_finite() or price_native <= 0):
        price_native = None

    if alert.type in {AlertType.MCAP_ABOVE.value, AlertType.MCAP_BELOW.value}:
        if market_cap is None or not market_cap.is_finite() or market_cap <= 0:
            return EvaluationResult(False, None, percent_change)
        if native:
            if price_native is None:
                return EvaluationResult(False, None, percent_change)
            market_cap = market_cap * price_native / current_price
        above = alert.type == AlertType.MCAP_ABOVE.value
        return EvaluationResult(
            market_cap >= alert.threshold_value if above else market_cap <= alert.threshold_value,
            AlertDirection.UP if above else AlertDirection.DOWN,
            percent_change,
        )

    if native and alert.type in {AlertType.PRICE_ABOVE.value, AlertType.PRICE_BELOW.value}:
        if price_native is None:
            return EvaluationResult(False, None, percent_change)
        current_price = price_native

    if alert.type == AlertType.PERCENT_CHANGE.value:
        threshold = abs(alert.threshold_value)
        wanted_direction = AlertDirection(alert.direction)
        direction_allowed = wanted_direction in {AlertDirection.BOTH, direction}
        return EvaluationResult(abs(percent_change) >= threshold and direction_allowed, direction, percent_change)

    if alert.type == AlertType.PRICE_ABOVE.value:
        return EvaluationResult(current_price >= alert.threshold_value, AlertDirection.UP, percent_change)

    if alert.type == AlertType.PRICE_BELOW.value:
        return EvaluationResult(current_price <= alert.threshold_value, AlertDirection.DOWN, percent_change)

    if alert.type == AlertType.ABSOLUTE_CHANGE.value:
        absolute_change = abs(current_price - alert.baseline_price)
        return EvaluationResult(absolute_change >= alert.threshold_value, direction, percent_change)

    return EvaluationResult(False, None, percent_change)
