from app.core.config import settings
from app.db.models import ConnectedApp, User
from app.db.repositories.users import has_bot_access, is_admin


def can_use_integrations(user: User | None) -> bool:
    return has_bot_access(user) and (is_admin(user) or settings.public_integrations_enabled)


def can_use_custom_webhooks(user: User | None) -> bool:
    return has_bot_access(user) and (is_admin(user) or settings.public_custom_webhooks_enabled)


def can_use_connection(user: User | None, connection: ConnectedApp) -> bool:
    if connection.integration_definition_id is not None:
        return can_use_integrations(user)
    return can_use_custom_webhooks(user)
