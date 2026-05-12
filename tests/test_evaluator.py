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
