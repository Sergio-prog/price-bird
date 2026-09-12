import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_webhook_mode_requires_https_origin_and_secret() -> None:
    with pytest.raises(ValidationError, match="WEBHOOK_BASE_URL"):
        Settings(_env_file=None, BOT_MODE="webhook", WEBHOOK_BASE_URL="http://example.com", WEBHOOK_SECRET="secret")

    with pytest.raises(ValidationError, match="WEBHOOK_SECRET"):
        Settings(_env_file=None, BOT_MODE="webhook", WEBHOOK_BASE_URL="https://example.com")


def test_webhook_mode_accepts_production_configuration() -> None:
    configured = Settings(
        _env_file=None,
        BOT_MODE="webhook",
        WEBHOOK_BASE_URL="https://alerts.example.com",
        WEBHOOK_PATH="/telegram/webhook",
        WEBHOOK_SECRET="long_random-secret_123",
    )

    assert configured.bot_mode == "webhook"
