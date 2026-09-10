from __future__ import annotations

import secrets

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def generate_encryption_key() -> str:
    return Fernet.generate_key().decode()


def generate_signing_secret() -> str:
    return secrets.token_urlsafe(32)


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_secret(encrypted: str) -> str:
    try:
        return _fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Integration secret cannot be decrypted with INTEGRATION_SECRETS_KEY.") from exc


def ensure_encryption_configured() -> None:
    _fernet()


def _fernet() -> Fernet:
    try:
        return Fernet(settings.integration_secrets_key.encode())
    except (TypeError, ValueError) as exc:
        raise ValueError("INTEGRATION_SECRETS_KEY must be a valid Fernet key.") from exc
