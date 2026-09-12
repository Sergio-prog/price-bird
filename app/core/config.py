from __future__ import annotations

import re
from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = Field(default="", alias="BOT_TOKEN")
    bot_mode: Literal["polling", "webhook"] = Field(default="polling", alias="BOT_MODE")
    webhook_base_url: str = Field(default="", alias="WEBHOOK_BASE_URL")
    webhook_path: str = Field(default="/telegram/webhook", alias="WEBHOOK_PATH")
    webhook_secret: str = Field(default="", alias="WEBHOOK_SECRET")
    web_server_host: str = Field(default="0.0.0.0", alias="WEB_SERVER_HOST")
    web_server_port: int = Field(default=8080, alias="WEB_SERVER_PORT")

    database_url: str = Field(
        default="postgresql+asyncpg://price_alerts:price_alerts@localhost:5432/price_alerts",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    price_refresh_interval_seconds: int = Field(default=45, alias="PRICE_REFRESH_INTERVAL_SECONDS")
    provider_timeout_seconds: int = Field(default=10, alias="PROVIDER_TIMEOUT_SECONDS")
    provider_max_attempts: int = Field(default=3, alias="PROVIDER_MAX_ATTEMPTS")
    notification_max_attempts: int = Field(default=5, alias="NOTIFICATION_MAX_ATTEMPTS")
    integration_secrets_key: str = Field(default="", alias="INTEGRATION_SECRETS_KEY")
    public_access_enabled: bool = Field(default=False, alias="PUBLIC_ACCESS_ENABLED")
    public_integrations_enabled: bool = Field(default=False, alias="PUBLIC_INTEGRATIONS_ENABLED")
    public_custom_webhooks_enabled: bool = Field(default=False, alias="PUBLIC_CUSTOM_WEBHOOKS_ENABLED")

    reservoir_base_url: str = Field(default="https://api.reservoir.tools", alias="RESERVOIR_BASE_URL")
    reservoir_api_key: str = Field(default="", alias="RESERVOIR_API_KEY")

    nft_providers: str = Field(default="opensea", alias="NFT_PROVIDERS")
    opensea_base_url: str = Field(default="https://api.opensea.io", alias="OPENSEA_BASE_URL")
    opensea_api_key: str = Field(default="", alias="OPENSEA_API_KEY")
    opensea_chain: str = Field(default="ethereum", alias="OPENSEA_CHAIN")

    @model_validator(mode="after")
    def validate_webhook_mode(self) -> Settings:
        if self.bot_mode != "webhook":
            return self

        parsed_url = urlsplit(self.webhook_base_url)
        if (
            parsed_url.scheme != "https"
            or not parsed_url.hostname
            or parsed_url.username
            or parsed_url.password
            or parsed_url.path not in {"", "/"}
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise ValueError("WEBHOOK_BASE_URL must be a public HTTPS origin in webhook mode")
        if not self.webhook_path.startswith("/"):
            raise ValueError("WEBHOOK_PATH must start with /")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", self.webhook_secret):
            raise ValueError("WEBHOOK_SECRET must contain 1-256 letters, numbers, underscores, or hyphens")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
