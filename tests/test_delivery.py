from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.alerts import service
from app.db.models import Alert, Asset, ConnectedApp, User
from app.delivery.events import queue_event
from app.delivery.webhook import DeliveryError, PublicResolver, signature, validate_url
from app.providers.base import PriceQuote


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "https://127.0.0.1",
        "https://[::1]",
        "https://169.254.169.254",
        "https://user:pass@example.com",
        "https://example.com:8080",
        "https://224.0.0.1",
    ],
)
def test_reject_unsafe_webhook_urls(url):
    with pytest.raises(ValueError):
        validate_url(url)


@pytest.mark.asyncio
async def test_dns_blocks_mixed_public_and_private_answers():
    resolver = PublicResolver()
    resolver.resolver.resolve = AsyncMock(return_value=[{"host": "8.8.8.8"}, {"host": "127.0.0.1"}])
    with pytest.raises(DeliveryError):
        await resolver.resolve("example.com", 443)
    await resolver.close()


def test_signature_contract():
    assert signature("s" * 32, "1700000000", "11111111-1111-4111-8111-111111111111", b'{"test":true}') == (
        "v1=ed39e8748c0aa1bda205bacd990751a629d74dc5bf376b2dce9cce65975b0e32"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bird,apps,expected", [(True, [], ["bird"]), (False, ["app"], ["app"]), (True, ["app"], ["bird", "app"]), (False, [], [])]
)
async def test_independent_destinations(bird, apps, expected):
    rows = []
    session = SimpleNamespace(add=rows.append, scalars=AsyncMock(return_value=[ConnectedApp(id=id) for id in apps]))
    user = User(id=1, telegram_id=42, bird_enabled=bird)
    alert = Alert(
        id=2,
        user_id=1,
        user=user,
        type="price_above",
        threshold_value=Decimal("2"),
        baseline_price=Decimal("1"),
        direction="up",
    )
    asset = Asset(symbol="TOKEN", type="token", chain="solana")
    event = SimpleNamespace(id=3, created_at=datetime.now(UTC), direction="up", percent_change=Decimal("100"))
    await queue_event(session, event, alert, asset, PriceQuote(Decimal("2"), "provider", {}))
    assert [row.destination for row in rows] == expected
    assert len({row.payload["event_id"] for row in rows}) <= 1


@pytest.mark.asyncio
async def test_repeating_alert_requires_rearm_and_cooldown(monkeypatch):
    alert = Alert(
        id=1,
        type="percent_change",
        baseline_price=Decimal("100"),
        threshold_value=Decimal("10"),
        direction="both",
        repeat=True,
        armed=True,
        cooldown_seconds=0,
        user=User(access_status="active"),
    )
    quote = PriceQuote(Decimal("120"), "provider", {})
    monkeypatch.setattr(service.provider_registry, "get_price", AsyncMock(side_effect=lambda _: quote))
    monkeypatch.setattr(service.repo, "create_snapshot", AsyncMock(return_value=SimpleNamespace(id=1)))
    monkeypatch.setattr(service.repo, "active_alerts_for_asset", AsyncMock(return_value=[alert]))
    event = SimpleNamespace(id=2, direction="up", percent_change=Decimal("20"))
    monkeypatch.setattr(service.repo, "create_alert_event", AsyncMock(return_value=event))
    queued = AsyncMock()
    monkeypatch.setattr(service, "queue_event", queued)
    asset = SimpleNamespace(id=1)
    assert await service.refresh_and_evaluate_asset(None, asset) == [2]
    assert await service.refresh_and_evaluate_asset(None, asset) == []
    quote = PriceQuote(Decimal("105"), "provider", {})
    assert await service.refresh_and_evaluate_asset(None, asset) == []
    assert alert.armed
    alert.cooldown_seconds = 900
    quote = PriceQuote(Decimal("120"), "provider", {})
    assert await service.refresh_and_evaluate_asset(None, asset) == []
    alert.last_triggered_at = datetime(2020, 1, 1, tzinfo=UTC)
    assert await service.refresh_and_evaluate_asset(None, asset) == [2]
    assert queued.await_count == 2


@pytest.mark.asyncio
async def test_disabled_destination_is_cancelled_before_send(monkeypatch):
    from app.delivery import worker

    statements = []

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def begin(self):
            return self

        async def get(self, model, key):
            return User(access_status="active", bird_enabled=False, telegram_id=42)

        async def execute(self, statement):
            statements.append(statement)

    monkeypatch.setattr(worker, "SessionLocal", Session)
    bot = SimpleNamespace(send_message=AsyncMock())
    delivery = SimpleNamespace(id="delivery", user_id=1, connection_id=None, destination="bird", lease_token="lease")
    await worker.process_delivery(delivery, bot)
    bot.send_message.assert_not_awaited()
    assert statements[0].compile().params["status"] == "cancelled"
