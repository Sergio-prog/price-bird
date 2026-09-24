from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.bot.handlers.settings import TRENCHBOOK_BOT_URL, coin_link_view, quiet_hours_view, settings_view, timezone_view
from app.core.config import settings
from app.db.models import ConnectedApp, IntegrationDefinition
from app.integrations.access import can_use_connection, can_use_custom_webhooks, can_use_integrations
from app.integrations.catalog import TRENCHBOOK_BASE_URL, configure_trenchbook
from app.integrations.secrets import encrypt_secret, generate_encryption_key
from app.integrations.service import connection_secret, connection_url, create_custom_connection, rotate_custom_secret


@pytest.fixture(autouse=True)
def integration_key(monkeypatch):
    monkeypatch.setattr(settings, "integration_secrets_key", generate_encryption_key())


def test_custom_connection_has_unique_encrypted_secret():
    first, first_secret = create_custom_connection(user_id=1, name="First", url="https://one.example/webhook")
    second, second_secret = create_custom_connection(user_id=1, name="Second", url="https://two.example/webhook")

    assert first_secret != second_secret
    assert first.secret_encrypted != first_secret
    assert connection_secret(first) == first_secret
    assert first.enabled is False


def test_rotating_custom_secret_disables_connection():
    connection, old_secret = create_custom_connection(user_id=1, name="App", url="https://example.com/webhook")
    connection.enabled = True

    new_secret = rotate_custom_secret(connection)

    assert new_secret != old_secret
    assert connection_secret(connection) == new_secret
    assert connection.secret_version == 2
    assert connection.enabled is False


def test_wrong_master_key_cannot_decrypt_connection(monkeypatch):
    connection, _ = create_custom_connection(user_id=1, name="App", url="https://example.com/webhook")
    monkeypatch.setattr(settings, "integration_secrets_key", generate_encryption_key())

    with pytest.raises(ValueError, match="cannot be decrypted"):
        connection_secret(connection)


def test_default_connection_uses_catalog_url_and_secret():
    secret = "receiver-secret"
    definition = IntegrationDefinition(
        id="definition",
        slug="trenchbook",
        name="Trenchbook",
        base_url=TRENCHBOOK_BASE_URL,
        webhook_path="/integrations/pricebird/webhook",
        secret_encrypted=encrypt_secret(secret),
        enabled=True,
    )
    connection = ConnectedApp(
        id="connection",
        user_id=1,
        integration_definition_id=definition.id,
        integration_definition=definition,
        name="Trenchbook",
        kind="default",
        url=None,
    )

    assert connection_url(connection) == "https://trenches.serhiifotex.dev/integrations/pricebird/webhook"
    assert connection_secret(connection) == secret


@pytest.mark.asyncio
async def test_settings_links_to_trenchbook_bot():
    session = Mock()
    session.scalars = AsyncMock(side_effect=[[], []])
    user = SimpleNamespace(id=1, bird_enabled=True, role="admin", access_status="active")

    text, _ = await settings_view(session, user)

    assert f'<a href="{TRENCHBOOK_BOT_URL}">Trenchbook</a>' in text


@pytest.mark.asyncio
async def test_public_settings_hide_private_destinations(monkeypatch):
    monkeypatch.setattr(settings, "public_integrations_enabled", False)
    monkeypatch.setattr(settings, "public_custom_webhooks_enabled", False)
    session = Mock()
    user = SimpleNamespace(id=1, bird_enabled=True, role="user", access_status="active")

    text, markup = await settings_view(session, user)

    assert "Trenchbook" not in text
    assert "🔗 Coin links: <tg-emoji" in text
    assert [button.text for row in markup.inline_keyboard for button in row] == [
        "🔔 Notifications: on",
        "🌙 Quiet hours: off",
        "🔗 Coin links: DEX",
        "🌍 UTC+00:00",
        "🌐 English",
        "↩️ Back to menu",
    ]
    assert markup.inline_keyboard[0][0].style == "success"
    session.scalars.assert_not_called()


def test_private_destinations_are_admin_only_by_default(monkeypatch):
    monkeypatch.setattr(settings, "public_integrations_enabled", False)
    monkeypatch.setattr(settings, "public_custom_webhooks_enabled", False)
    admin = SimpleNamespace(role="admin", access_status="active")
    user = SimpleNamespace(role="user", access_status="active")
    integration = ConnectedApp(id="integration", integration_definition_id="definition")
    webhook = ConnectedApp(id="webhook", integration_definition_id=None)

    assert can_use_integrations(admin)
    assert can_use_custom_webhooks(admin)
    assert can_use_connection(admin, integration)
    assert can_use_connection(admin, webhook)
    assert not can_use_integrations(user)
    assert not can_use_custom_webhooks(user)
    assert not can_use_connection(user, integration)
    assert not can_use_connection(user, webhook)


def test_notification_preference_views() -> None:
    user = SimpleNamespace(
        quiet_hours_start=23,
        quiet_hours_end=8,
        timezone_offset_minutes=120,
        coin_links=["gmgn"],
    )

    quiet_text, quiet_markup = quiet_hours_view(user)
    timezone_text, timezone_markup = timezone_view(user)
    link_text, link_markup = coin_link_view(user)

    assert "23:00-08:00 (UTC+02:00)" in quiet_text
    assert [button.text for button in quiet_markup.inline_keyboard[0]] == ["-1h", "from 23:00", "+1h"]
    assert timezone_text.startswith("🌍 <b>Timezone:</b> UTC+02:00")
    assert [button.text for button in timezone_markup.inline_keyboard[0]] == ["-1h", "UTC+02:00", "+1h"]
    assert link_text.startswith("🔗 <b>Coin links:</b> 🐸 GMGN")
    selected = [button.text for row in link_markup.inline_keyboard for button in row if button.style == "success"]
    assert selected == ["✅ 🐸 GMGN"]


@pytest.mark.asyncio
async def test_coin_link_callback_updates_user_and_edits_message(monkeypatch) -> None:
    from app.bot.handlers import settings as settings_handler

    class FakeMessage:
        chat = SimpleNamespace(type="private")

        def __init__(self):
            self.edits = []

        async def edit_text(self, text, **kwargs):
            self.edits.append((text, kwargs))

    user = SimpleNamespace(
        id=1,
        bird_enabled=True,
        role="user",
        access_status="active",
        coin_links=["dexscreener"],
        quiet_hours_start=None,
        quiet_hours_end=None,
        timezone_offset_minutes=0,
    )
    message = FakeMessage()
    callback = SimpleNamespace(
        data="settings:coinlink:gmgn",
        from_user=SimpleNamespace(id=42),
        message=message,
        answer=AsyncMock(),
    )
    session = SimpleNamespace(refresh=AsyncMock(), commit=AsyncMock())
    state = SimpleNamespace(clear=AsyncMock())
    monkeypatch.setattr(settings_handler, "Message", FakeMessage)
    monkeypatch.setattr(settings_handler, "owned_user", AsyncMock(return_value=user))

    await settings_handler.settings_callback(callback, state, session)

    assert user.coin_links == ["dexscreener", "gmgn"]
    assert message.edits[0][0].startswith("🔗 <b>Coin links:</b> ")

    callback.data = "settings:coinlink:none"
    await settings_handler.settings_callback(callback, state, session)

    assert user.coin_links == []
    assert "Coin links:</b> hidden" in message.edits[1][0]
    assert session.commit.await_count == 2


@pytest.mark.asyncio
async def test_timezone_callback_updates_user_and_edits_message(monkeypatch) -> None:
    from app.bot.handlers import settings as settings_handler

    class FakeMessage:
        chat = SimpleNamespace(type="private")

        def __init__(self):
            self.edits = []

        async def edit_text(self, text, **kwargs):
            self.edits.append((text, kwargs))

    user = SimpleNamespace(
        id=1,
        role="user",
        access_status="active",
        timezone_offset_minutes=120,
    )
    message = FakeMessage()
    callback = SimpleNamespace(
        data="settings:timezone:60",
        from_user=SimpleNamespace(id=42),
        message=message,
        answer=AsyncMock(),
    )
    session = SimpleNamespace(refresh=AsyncMock(), commit=AsyncMock())
    state = SimpleNamespace(clear=AsyncMock())
    monkeypatch.setattr(settings_handler, "Message", FakeMessage)
    monkeypatch.setattr(settings_handler, "owned_user", AsyncMock(return_value=user))

    await settings_handler.settings_callback(callback, state, session)

    assert user.timezone_offset_minutes == 180
    assert message.edits[0][0].startswith("🌍 <b>Timezone:</b> UTC+03:00")
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_configure_trenchbook_creates_database_definition():
    session = Mock()
    session.scalar = AsyncMock(return_value=None)
    session.scalars = AsyncMock(side_effect=[[], []])
    session.flush = AsyncMock()

    definition, secret = await configure_trenchbook(session)

    assert definition.slug == "trenchbook"
    assert definition.base_url == TRENCHBOOK_BASE_URL
    assert (
        connection_secret(
            ConnectedApp(
                id="connection",
                user_id=1,
                integration_definition_id=definition.id,
                integration_definition=definition,
                name="Trenchbook",
                kind="default",
            )
        )
        == secret
    )
    session.add.assert_called_once_with(definition)
    session.flush.assert_awaited_once()
