from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    USER = "user"
    ADMIN = "admin"


class AccessStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class AssetType(StrEnum):
    TOKEN = "token"
    NFT_COLLECTION = "nft_collection"
    CEX_SYMBOL = "cex_symbol"


class AlertLimitKind(StrEnum):
    TOKEN = "token"
    NFT = "nft"

    @classmethod
    def for_asset_type(cls, asset_type: str) -> AlertLimitKind:
        return cls.NFT if asset_type == AssetType.NFT_COLLECTION.value else cls.TOKEN

    @property
    def asset_types(self) -> tuple[str, ...]:
        if self is AlertLimitKind.NFT:
            return (AssetType.NFT_COLLECTION.value,)
        return (AssetType.TOKEN.value, AssetType.CEX_SYMBOL.value)


class AlertType(StrEnum):
    PERCENT_CHANGE = "percent_change"
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    ABSOLUTE_CHANGE = "absolute_change"
    MCAP_ABOVE = "mcap_above"
    MCAP_BELOW = "mcap_below"


class AlertDirection(StrEnum):
    BOTH = "both"
    UP = "up"
    DOWN = "down"


class AlertStatus(StrEnum):
    ACTIVE = "active"
    TRIGGERED = "triggered"
    PAUSED = "paused"
    DELETED = "deleted"


class NotificationStatus(StrEnum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
