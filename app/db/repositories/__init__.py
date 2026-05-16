from app.db.repositories.alerts import (
    active_alerts_for_asset,
    active_alerts_for_user,
    active_watched_assets,
    create_alert,
    delete_active_alert_for_user,
    mark_alert_triggered,
)
from app.db.repositories.assets import upsert_asset_from_candidate, upsert_provider_link
from app.db.repositories.events import create_alert_event, queued_alert_events
from app.db.repositories.snapshots import create_snapshot, latest_snapshot
from app.db.repositories.stats import get_stats
from app.db.repositories.users import (
    ensure_admin,
    get_user_by_id,
    get_user_by_telegram_id,
    has_bot_access,
    is_admin,
    list_users,
    set_user_access,
    upsert_telegram_user,
)

__all__ = [
    "active_alerts_for_asset",
    "active_alerts_for_user",
    "active_watched_assets",
    "create_alert",
    "create_alert_event",
    "create_snapshot",
    "delete_active_alert_for_user",
    "ensure_admin",
    "get_stats",
    "get_user_by_id",
    "get_user_by_telegram_id",
    "has_bot_access",
    "is_admin",
    "latest_snapshot",
    "list_users",
    "mark_alert_triggered",
    "queued_alert_events",
    "set_user_access",
    "upsert_asset_from_candidate",
    "upsert_provider_link",
    "upsert_telegram_user",
]
