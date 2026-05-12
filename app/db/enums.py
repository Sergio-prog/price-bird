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


class AlertType(StrEnum):
    PERCENT_CHANGE = "percent_change"
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    ABSOLUTE_CHANGE = "absolute_change"


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
