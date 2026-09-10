from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ConnectedApp, IntegrationDefinition
from app.integrations.secrets import decrypt_secret, encrypt_secret, generate_signing_secret
from app.integrations.urls import validate_url

TRENCHBOOK_SLUG = "trenchbook"
TRENCHBOOK_NAME = "Trenchbook"
TRENCHBOOK_BASE_URL = "https://trenchbook.serhiifotex.dev"
TRENCHBOOK_WEBHOOK_PATH = "/integrations/pricebird/webhook"


async def configure_trenchbook(
    session: AsyncSession,
    *,
    base_url: str = TRENCHBOOK_BASE_URL,
    rotate_secret: bool = False,
) -> tuple[IntegrationDefinition, str | None]:
    base_url = validate_url(base_url).rstrip("/")
    definition = await session.scalar(
        select(IntegrationDefinition).where(IntegrationDefinition.slug == TRENCHBOOK_SLUG).with_for_update()
    )
    secret = None
    if definition is None:
        secret = generate_signing_secret()
        definition = IntegrationDefinition(
            id=str(uuid4()),
            slug=TRENCHBOOK_SLUG,
            name=TRENCHBOOK_NAME,
            base_url=base_url,
            webhook_path=TRENCHBOOK_WEBHOOK_PATH,
            secret_encrypted=encrypt_secret(secret),
        )
        session.add(definition)
        await session.flush()
    else:
        definition.name = TRENCHBOOK_NAME
        definition.base_url = base_url
        definition.webhook_path = TRENCHBOOK_WEBHOOK_PATH
        definition.enabled = True
        if rotate_secret:
            secret = generate_signing_secret()
            definition.secret_encrypted = encrypt_secret(secret)
            definition.secret_version += 1
            await _disable_connections(session, definition.id)
        else:
            decrypt_secret(definition.secret_encrypted)

    await _adopt_legacy_connections(session, definition)
    return definition, secret


async def _disable_connections(session: AsyncSession, definition_id: str) -> None:
    connections = await session.scalars(
        select(ConnectedApp).where(ConnectedApp.integration_definition_id == definition_id).with_for_update()
    )
    for connection in connections:
        connection.enabled = False


async def _adopt_legacy_connections(session: AsyncSession, definition: IntegrationDefinition) -> None:
    existing_user_ids = set(
        await session.scalars(select(ConnectedApp.user_id).where(ConnectedApp.integration_definition_id == definition.id))
    )
    legacy = await session.scalars(
        select(ConnectedApp)
        .where(ConnectedApp.kind == TRENCHBOOK_SLUG, ConnectedApp.integration_definition_id.is_(None))
        .order_by(ConnectedApp.user_id, ConnectedApp.deleted, ConnectedApp.created_at.desc())
        .with_for_update()
    )
    for connection in legacy:
        if connection.user_id in existing_user_ids:
            connection.enabled = False
            connection.deleted = True
            continue
        connection.integration_definition_id = definition.id
        connection.integration_definition = definition
        connection.name = definition.name
        connection.kind = "default"
        connection.url = None
        connection.enabled = False
        existing_user_ids.add(connection.user_id)
