from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import (
    AccessStatus,
    AlertDirection,
    AlertStatus,
    NotificationStatus,
    UserRole,
)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "quiet_hours_start IS NULL OR quiet_hours_start BETWEEN 0 AND 23",
            name="ck_users_quiet_hours_start",
        ),
        CheckConstraint(
            "quiet_hours_end IS NULL OR quiet_hours_end BETWEEN 0 AND 23",
            name="ck_users_quiet_hours_end",
        ),
        CheckConstraint(
            "timezone_offset_minutes BETWEEN -720 AND 840",
            name="ck_users_timezone_offset_minutes",
        ),
        CheckConstraint(
            "coin_link IN ('tradingview', 'dexscreener', 'gmgn', 'fomo', 'coinmarketcap')",
            name="ck_users_coin_link",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    bird_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    quiet_hours_start: Mapped[int | None] = mapped_column()
    quiet_hours_end: Mapped[int | None] = mapped_column()
    timezone_offset_minutes: Mapped[int] = mapped_column(default=0, server_default="0")
    coin_link: Mapped[str] = mapped_column(String(32), default="dexscreener", server_default="dexscreener")
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    language_code: Mapped[str | None] = mapped_column(String(16))
    language: Mapped[str | None] = mapped_column(String(8))
    role: Mapped[str] = mapped_column(String(32), default=UserRole.USER.value, server_default=UserRole.USER.value)
    access_status: Mapped[str] = mapped_column(
        String(32), default=AccessStatus.PENDING.value, server_default=AccessStatus.PENDING.value
    )

    alerts: Mapped[list[Alert]] = relationship(back_populates="user")


class Asset(Base, TimestampMixin):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("provider", "provider_asset_id", name="uq_assets_provider_asset"),
        Index("ix_assets_lookup", "type", "chain", "symbol"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    type: Mapped[str] = mapped_column(String(32))
    chain: Mapped[str | None] = mapped_column(String(64))
    symbol: Mapped[str] = mapped_column(String(64))
    name: Mapped[str | None] = mapped_column(String(255))
    contract_address: Mapped[str | None] = mapped_column(String(255))
    provider: Mapped[str] = mapped_column(String(64))
    provider_asset_id: Mapped[str] = mapped_column(String(255))
    extra: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, server_default="{}")

    aliases: Mapped[list[AssetAlias]] = relationship(back_populates="asset", cascade="all, delete-orphan")
    links: Mapped[list[ProviderLink]] = relationship(back_populates="asset", cascade="all, delete-orphan")
    snapshots: Mapped[list[PriceSnapshot]] = relationship(back_populates="asset")
    alerts: Mapped[list[Alert]] = relationship(back_populates="asset")


class AssetAlias(Base):
    __tablename__ = "asset_aliases"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"))
    alias: Mapped[str] = mapped_column(String(255), index=True)
    kind: Mapped[str] = mapped_column(String(32))

    asset: Mapped[Asset] = relationship(back_populates="aliases")


class ProviderLink(Base):
    __tablename__ = "provider_links"
    __table_args__ = (UniqueConstraint("asset_id", "kind", name="uq_provider_links_asset_kind"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(64))
    url: Mapped[str] = mapped_column(Text)

    asset: Mapped[Asset] = relationship(back_populates="links")


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    price_usd: Mapped[Decimal] = mapped_column(Numeric(78, 36))
    price_native: Mapped[Decimal | None] = mapped_column(Numeric(78, 36))
    native_symbol: Mapped[str | None] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(64))
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    asset: Mapped[Asset] = relationship(back_populates="snapshots")


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alerts_active_asset", "status", "asset_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default=AlertStatus.ACTIVE.value, server_default=AlertStatus.ACTIVE.value)
    baseline_price: Mapped[Decimal] = mapped_column(Numeric(78, 36))
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(78, 36))
    threshold_currency: Mapped[str] = mapped_column(String(16), default="USD", server_default="USD")
    direction: Mapped[str] = mapped_column(String(32), default=AlertDirection.BOTH.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    repeat: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    armed: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    cooldown_seconds: Mapped[int] = mapped_column(default=10, server_default="10")
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    note: Mapped[str | None] = mapped_column(String(300))

    user: Mapped[User] = relationship(back_populates="alerts")
    asset: Mapped[Asset] = relationship(back_populates="alerts")
    events: Mapped[list[AlertEvent]] = relationship(back_populates="alert")


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id", ondelete="CASCADE"), index=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("price_snapshots.id", ondelete="CASCADE"))
    direction: Mapped[str] = mapped_column(String(32))
    percent_change: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    notification_status: Mapped[str] = mapped_column(
        String(32), default=NotificationStatus.QUEUED.value, server_default=NotificationStatus.QUEUED.value
    )
    notification_attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    alert: Mapped[Alert] = relationship(back_populates="events")
    snapshot: Mapped[PriceSnapshot] = relationship()


class AlertLimit(Base, TimestampMixin):
    __tablename__ = "alert_limits"
    __table_args__ = (
        CheckConstraint(
            "max_watched_assets >= 0 AND max_active_alerts >= 0 AND default_user_max_alerts >= 0",
            name="ck_alert_limits_non_negative",
        ),
    )

    asset_kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    max_watched_assets: Mapped[int]
    max_active_alerts: Mapped[int]
    default_user_max_alerts: Mapped[int]


class UserAlertLimit(Base, TimestampMixin):
    __tablename__ = "user_alert_limits"
    __table_args__ = (CheckConstraint("max_alerts >= 0", name="ck_user_alert_limits_non_negative"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    asset_kind: Mapped[str] = mapped_column(ForeignKey("alert_limits.asset_kind", ondelete="CASCADE"), primary_key=True)
    max_alerts: Mapped[int]


class ConnectedApp(Base, TimestampMixin):
    __tablename__ = "connected_apps"
    __table_args__ = (UniqueConstraint("user_id", "integration_definition_id", name="uq_connected_apps_user_integration"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    integration_definition_id: Mapped[str | None] = mapped_column(ForeignKey("integration_definitions.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(32))
    url: Mapped[str | None] = mapped_column(Text)
    secret_encrypted: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    secret_version: Mapped[int] = mapped_column(default=1, server_default="1")

    integration_definition: Mapped[IntegrationDefinition | None] = relationship(back_populates="connections", lazy="raise")


class IntegrationDefinition(Base, TimestampMixin):
    __tablename__ = "integration_definitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    base_url: Mapped[str] = mapped_column(Text)
    webhook_path: Mapped[str] = mapped_column(String(255))
    secret_encrypted: Mapped[str] = mapped_column(Text)
    secret_version: Mapped[int] = mapped_column(default=1, server_default="1")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    connections: Mapped[list[ConnectedApp]] = relationship(back_populates="integration_definition")


class Delivery(Base):
    __tablename__ = "deliveries"
    __table_args__ = (
        UniqueConstraint("event_id", "destination", name="uq_delivery_event_destination"),
        Index("ix_delivery_due", "status", "next_attempt_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("alert_events.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    connection_id: Mapped[str | None] = mapped_column(ForeignKey("connected_apps.id"))
    destination: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    lease_token: Mapped[str | None] = mapped_column(String(36))
    leased_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
