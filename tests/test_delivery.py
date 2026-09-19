from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.alerts import service
from app.db.models import Alert, Asset, ConnectedApp, User
from app.delivery.events import queue_event, queue_trenchbook_debug_alert
from app.delivery.webhook import DeliveryError, PublicResolver, signature, validate_url
from app.delivery.worker import render_payload
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
    user = User(id=1, telegram_id=42, bird_enabled=bird, role="admin", access_status="active")
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
async def test_user_coin_link_is_included_with_source() -> None:
    rows = []
    session = SimpleNamespace(add=rows.append, scalars=AsyncMock(return_value=[]))
    user = User(
        id=1,
        telegram_id=42,
        bird_enabled=True,
        role="admin",
        access_status="active",
        coin_link="gmgn",
    )
    alert = Alert(
        id=2,
        user_id=1,
        user=user,
        type="price_above",
        threshold_value=Decimal("2"),
        baseline_price=Decimal("1"),
        direction="up",
    )
    asset = Asset(symbol="TOKEN", type="token", chain="solana", contract_address="token")
    event = SimpleNamespace(id=3, created_at=datetime.now(UTC), direction="up", percent_change=Decimal("100"))

    await queue_event(session, event, alert, asset, PriceQuote(Decimal("2"), "dexscreener", {}))

    assert rows[0].payload["links"] == {
        "dexscreener": "https://dexscreener.com/solana/token",
        "gmgn": "https://gmgn.ai/sol/token/token",
    }


@pytest.mark.asyncio
async def test_repeating_move_alert_rebases_and_respects_cooldown(monkeypatch):
    alert = Alert(
        id=1,
        type="percent_change",
        baseline_price=Decimal("100"),
        threshold_value=Decimal("10"),
        direction="both",
        repeat=True,
        armed=False,
        cooldown_seconds=900,
        last_triggered_at=datetime(2020, 1, 1, tzinfo=UTC),
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
    assert alert.baseline_price == Decimal("120")
    assert alert.armed
    quote = PriceQuote(Decimal("150"), "provider", {})
    assert await service.refresh_and_evaluate_asset(None, asset) == []
    assert alert.baseline_price == Decimal("120")
    alert.last_triggered_at = datetime(2020, 1, 1, tzinfo=UTC)
    assert await service.refresh_and_evaluate_asset(None, asset) == [2]
    assert alert.baseline_price == Decimal("150")
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


@pytest.mark.asyncio
async def test_quiet_hours_send_telegram_alert_without_sound(monkeypatch):
    from app.delivery import worker

    class NoonUtc(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 1, 1, 12, 0, tzinfo=tz)

    monkeypatch.setattr(worker, "datetime", NoonUtc)

    statements = []

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def begin(self):
            return self

        async def get(self, model, key):
            return User(
                access_status="active",
                bird_enabled=True,
                telegram_id=42,
                quiet_hours_start=2,
                quiet_hours_end=23,
                timezone_offset_minutes=120,
            )

        async def execute(self, statement):
            statements.append(statement)

    monkeypatch.setattr(worker, "SessionLocal", Session)
    bot = SimpleNamespace(send_message=AsyncMock())
    delivery = SimpleNamespace(
        id="delivery",
        user_id=1,
        connection_id=None,
        destination="bird",
        lease_token="lease",
        payload={"type": "connection.test"},
    )

    await worker.process_delivery(delivery, bot)

    assert bot.send_message.await_args.kwargs["disable_notification"] is True
    assert statements[0].compile().params["status"] == "sent"


@pytest.mark.asyncio
async def test_private_integration_is_cancelled_for_non_admin(monkeypatch):
    from app.delivery import worker

    statements = []
    connection = ConnectedApp(
        id="private-integration",
        user_id=1,
        integration_definition_id="definition",
        enabled=True,
        deleted=False,
    )

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def begin(self):
            return self

        async def get(self, model, key):
            return User(access_status="active", role="user", telegram_id=42)

        async def scalar(self, statement):
            return connection

        async def execute(self, statement):
            statements.append(statement)

    monkeypatch.setattr(worker, "SessionLocal", Session)
    send_webhook = AsyncMock()
    monkeypatch.setattr(worker, "send_webhook", send_webhook)
    bot = SimpleNamespace(send_message=AsyncMock())
    delivery = SimpleNamespace(
        id="delivery",
        user_id=1,
        connection_id=connection.id,
        destination=connection.id,
        lease_token="lease",
    )

    await worker.process_delivery(delivery, bot)

    send_webhook.assert_not_awaited()
    assert statements[0].compile().params["status"] == "cancelled"


def test_render_payload_formats_percent_alert_and_links_source():
    message = render_payload(
        {
            "type": "alert.triggered",
            "note": None,
            "asset": {"symbol": "MEME", "kind": "token", "chain": "solana", "address": "token"},
            "rule": {
                "type": "percent_change",
                "threshold": "10.000000000000000000000000000000000000",
                "threshold_currency": "USD",
                "baseline": "0.0523",
                "direction": "both",
            },
            "observation": {
                "price_usd": "0.058290000000000000000000000000000000",
                "price_native": "0.05829",
                "native_symbol": "USDG",
                "source": "dexscreener",
                "market_cap_usd": "1000000",
            },
            "trigger": {"direction": "up", "percent_change": "11.4532"},
            "links": {
                "dexscreener": "https://dexscreener.com/solana/token",
                "tradingview": "https://www.tradingview.com/search/?query=MEME",
            },
        }
    )

    assert message.startswith("🔔 <b>MEME</b> ↑ +11.45%\n\n")
    assert "<b>Rule:</b> 10% move up or down" in message
    assert "<b>Price:</b> $0.05829\n<b>Market cap:</b> $1M\n\n" in message
    assert "Floor" not in message
    assert "Baseline" not in message
    assert '<b>Source:</b> <a href="https://dexscreener.com/solana/token">DexScreener</a>' in message
    assert '<b>Links:</b> <a href="https://www.tradingview.com/search/?query=MEME">TradingView</a>' in message


@pytest.mark.asyncio
async def test_debug_alert_replays_latest_real_payload_to_trenchbook():
    connection = ConnectedApp(id="trenchbook", user_id=1, name="Trenchbook", kind="default", enabled=True)
    previous = SimpleNamespace(
        event_id=9,
        payload={
            "type": "alert.triggered",
            "event_id": "old-event",
            "occurred_at": "2026-01-01T00:00:00+00:00",
            "alert_id": "42",
        },
    )
    added = []
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[connection, previous]), add=added.append)

    alert_id = await queue_trenchbook_debug_alert(session, 1)

    assert alert_id == "42"
    assert len(added) == 1
    assert added[0].connection_id == connection.id
    assert added[0].event_id is None
    assert added[0].payload["event_id"] != previous.payload["event_id"]
    assert added[0].payload["connection_id"] == connection.id


def test_render_payload_rounds_noisy_nft_floor_and_marks_direction():
    message = render_payload(
        {
            "type": "alert.triggered",
            "note": None,
            "asset": {"symbol": "MILADY", "kind": "nft_collection", "chain": "ethereum", "address": None},
            "rule": {
                "type": "percent_change",
                "threshold": "5.000000000000000000000000000000000000",
                "threshold_currency": "USD",
                "baseline": "2352.103400000000000000000000000000000",
                "direction": "both",
            },
            "observation": {
                "price_usd": "2477.031065599995305492",
                "price_native": "0.9497599999999982",
                "native_symbol": "ETH",
                "source": "opensea",
                "market_cap_usd": "1234567890.12",
            },
            "trigger": {"direction": "down", "percent_change": "-5.3100"},
            "links": {"opensea": "https://opensea.io/collection/milady"},
        }
    )

    assert message.startswith("🔔 <b>MILADY</b> ↓ -5.31%\n\n")
    assert "<b>Rule:</b> 5% move up or down" in message
    assert "<b>Floor price:</b> 0.9498 ETH ($2,477.03)\n<b>Market cap:</b> $1.23B\n\n" in message
    assert "Baseline" not in message
    assert "Links:" not in message


def test_render_payload_shows_compact_market_cap():
    message = render_payload(
        {
            "type": "alert.triggered",
            "note": None,
            "asset": {"symbol": "PEPE", "kind": "token", "chain": "ethereum", "address": "0x1"},
            "rule": {"type": "mcap_above", "threshold": "5000000000", "baseline": "0.00001101", "direction": "up"},
            "observation": {"price_usd": "0.0000121345", "source": "dexscreener", "market_cap_usd": "5100000000.5"},
            "trigger": {"direction": "up", "percent_change": "10.2"},
            "links": {},
        }
    )

    assert "<b>Rule:</b> Market cap above $5B" in message
    assert "<b>Price:</b> $0.00001213" in message
    assert "<b>Market cap:</b> $5.1B" in message
