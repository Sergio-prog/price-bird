from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.db.repositories.users import get_user_language
from app.i18n import resolve_locale, use_locale


class LocaleMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        telegram_user = data.get("event_from_user")
        if telegram_user is None:
            return await handler(event, data)
        language = await get_user_language(data["session"], telegram_user.id)
        with use_locale(resolve_locale(language, telegram_user.language_code)):
            return await handler(event, data)
