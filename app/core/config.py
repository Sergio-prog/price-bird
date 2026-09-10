from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = Field(default="", alias="BOT_TOKEN")
    bot_mode: str = Field(default="polling", alias="BOT_MODE")
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

    reservoir_base_url: str = Field(default="https://api.reservoir.tools", alias="RESERVOIR_BASE_URL")
    reservoir_api_key: str = Field(default="", alias="RESERVOIR_API_KEY")

    nft_providers: str = Field(default="opensea,reservoir", alias="NFT_PROVIDERS")
    opensea_base_url: str = Field(default="https://api.opensea.io", alias="OPENSEA_BASE_URL")
    opensea_api_key: str = Field(default="", alias="OPENSEA_API_KEY")
    opensea_chain: str = Field(default="ethereum", alias="OPENSEA_CHAIN")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
