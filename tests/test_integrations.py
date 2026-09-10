from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.bot.handlers.settings import TRENCHBOOK_BOT_URL, settings_view
from app.core.config import settings
from app.db.models import ConnectedApp, IntegrationDefinition
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
    user = SimpleNamespace(id=1, bird_enabled=True)

    text, _ = await settings_view(session, user)

    assert f'<a href="{TRENCHBOOK_BOT_URL}">Trenchbook</a>' in text


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
