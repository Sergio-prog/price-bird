from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.alerts import service
from app.db.enums import AlertDirection, AlertType
from app.providers.base import PriceQuote


@pytest.mark.asyncio
async def test_percent_alert_stays_active_after_trigger(monkeypatch: pytest.MonkeyPatch) -> None:
    alert = SimpleNamespace(
        id=10,
        type=AlertType.PERCENT_CHANGE.value,
        baseline_price=Decimal("100"),
        threshold_value=Decimal("10"),
        direction=AlertDirection.BOTH.value,
    )
    calls = []

    await _run_refresh(monkeypatch, alert, calls)

    assert "event" in calls
    assert "mark_triggered" not in calls


@pytest.mark.asyncio
async def test_limit_alert_is_marked_triggered_after_trigger(monkeypatch: pytest.MonkeyPatch) -> None:
    alert = SimpleNamespace(
        id=11,
        type=AlertType.PRICE_ABOVE.value,
        baseline_price=Decimal("100"),
        threshold_value=Decimal("110"),
        direction=AlertDirection.UP.value,
    )
    calls = []

    await _run_refresh(monkeypatch, alert, calls)

    assert calls == ["snapshot", "event", "mark_triggered:11"]


async def _run_refresh(monkeypatch: pytest.MonkeyPatch, alert, calls: list[str]) -> None:
    asset = SimpleNamespace(id=1)

    async def fake_get_price(asset):
        return PriceQuote(price_usd=Decimal("120"), source="test", raw={})

    async def fake_create_snapshot(session, **kwargs):
        calls.append("snapshot")
        return SimpleNamespace(id=20)

    async def fake_active_alerts_for_asset(session, asset_id):
        return [alert]

    async def fake_create_alert_event(session, **kwargs):
        calls.append("event")
        return SimpleNamespace(id=30)

    async def fake_mark_alert_triggered(session, alert_id):
        calls.append(f"mark_triggered:{alert_id}")

    monkeypatch.setattr(service.provider_registry, "get_price", fake_get_price)
    monkeypatch.setattr(service.repo, "create_snapshot", fake_create_snapshot)
    monkeypatch.setattr(service.repo, "active_alerts_for_asset", fake_active_alerts_for_asset)
    monkeypatch.setattr(service.repo, "create_alert_event", fake_create_alert_event)
    monkeypatch.setattr(service.repo, "mark_alert_triggered", fake_mark_alert_triggered)

    event_ids = await service.refresh_and_evaluate_asset(object(), asset)

    assert event_ids == [30]
