from decimal import Decimal

from app.alerts.evaluator import evaluate_alert
from app.db.enums import AlertDirection, AlertType


class DummyAlert:
    baseline_price = Decimal("100")
    threshold_value = Decimal("10")
    direction = AlertDirection.BOTH.value
    type = AlertType.PERCENT_CHANGE.value


def test_bidirectional_percent_triggers_on_pump() -> None:
    result = evaluate_alert(DummyAlert(), Decimal("111"))

    assert result.triggered is True
    assert result.direction == AlertDirection.UP


def test_bidirectional_percent_triggers_on_dump() -> None:
    result = evaluate_alert(DummyAlert(), Decimal("89"))

    assert result.triggered is True
    assert result.direction == AlertDirection.DOWN


def test_bidirectional_percent_ignores_small_move() -> None:
    result = evaluate_alert(DummyAlert(), Decimal("95"))

    assert result.triggered is False


def test_market_cap_uses_actual_metric_and_missing_data_does_not_rearm():
    alert = DummyAlert()
    alert.type = AlertType.MCAP_ABOVE.value
    alert.threshold_value = Decimal("5000000")
    assert evaluate_alert(alert, Decimal("1"), Decimal("6000000")).triggered
    assert not evaluate_alert(alert, Decimal("1"), Decimal("4000000")).triggered
    result = evaluate_alert(alert, Decimal("1"), None)
    assert not result.triggered
    assert result.direction is None


def test_native_price_threshold_uses_native_quote():
    alert = DummyAlert()
    alert.type = AlertType.PRICE_BELOW.value
    alert.threshold_value = Decimal("0.8")
    alert.threshold_currency = "ETH"
    assert evaluate_alert(alert, Decimal("3000"), None, Decimal("0.75")).triggered
    assert not evaluate_alert(alert, Decimal("3000"), None, Decimal("0.9")).triggered
    result = evaluate_alert(alert, Decimal("3000"), None, None)
    assert not result.triggered
    assert result.direction is None


def test_native_market_cap_converts_from_usd():
    alert = DummyAlert()
    alert.type = AlertType.MCAP_ABOVE.value
    alert.threshold_value = Decimal("1000")
    alert.threshold_currency = "SOL"
    assert evaluate_alert(alert, Decimal("100"), Decimal("200000"), Decimal("0.5")).triggered
    assert not evaluate_alert(alert, Decimal("100"), Decimal("100000"), Decimal("0.5")).triggered
