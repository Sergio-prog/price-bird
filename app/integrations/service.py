from __future__ import annotations

from urllib.parse import urljoin
from uuid import uuid4

from app.db.models import ConnectedApp
from app.integrations.secrets import decrypt_secret, encrypt_secret, generate_signing_secret
from app.integrations.urls import validate_url


def create_custom_connection(*, user_id: int, name: str, url: str) -> tuple[ConnectedApp, str]:
    secret = generate_signing_secret()
    connection = ConnectedApp(
        id=str(uuid4()),
        user_id=user_id,
        name=name,
        kind="custom",
        url=validate_url(url),
        secret_encrypted=encrypt_secret(secret),
        secret_version=1,
        enabled=False,
    )
    return connection, secret


def rotate_custom_secret(connection: ConnectedApp) -> str:
    if connection.kind != "custom":
        raise ValueError("Only custom webhook secrets can be rotated by the user.")
    secret = generate_signing_secret()
    connection.secret_encrypted = encrypt_secret(secret)
    connection.secret_version += 1
    connection.enabled = False
    return secret


def connection_secret(connection: ConnectedApp) -> str:
    definition = connection.integration_definition if connection.integration_definition_id else None
    encrypted = definition.secret_encrypted if definition is not None else connection.secret_encrypted
    if not encrypted:
        raise ValueError("Connection signing secret is missing.")
    return decrypt_secret(encrypted)


def connection_url(connection: ConnectedApp) -> str:
    if connection.integration_definition_id:
        definition = connection.integration_definition
        if definition is None or not definition.enabled:
            raise ValueError("Integration is disabled by the operator.")
        return validate_url(urljoin(f"{definition.base_url.rstrip('/')}/", definition.webhook_path.lstrip("/")))
    if not connection.url:
        raise ValueError("Connection URL is missing.")
    return validate_url(connection.url)
