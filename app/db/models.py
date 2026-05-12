from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    language_code: Mapped[str | None] = mapped_column(String(16))
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
    price_usd: Mapped[Decimal] = mapped_column(Numeric(28, 10))
    price_native: Mapped[Decimal | None] = mapped_column(Numeric(28, 10))
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
    baseline_price: Mapped[Decimal] = mapped_column(Numeric(28, 10))
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(28, 10))
    direction: Mapped[str] = mapped_column(String(32), default=AlertDirection.BOTH.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

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
