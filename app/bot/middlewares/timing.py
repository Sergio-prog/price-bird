from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

logger = logging.getLogger(__name__)

SLOW_UPDATE_SECONDS = 1.0


class TimingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        started = time.perf_counter()
        try:
            return await handler(event, data)
        finally:
            elapsed = time.perf_counter() - started
            if elapsed >= SLOW_UPDATE_SECONDS:
                logger.warning("Slow update; type=%s action=%s seconds=%.2f", _update_type(event), _action(event), elapsed)


def _update_type(event: TelegramObject) -> str:
    return event.event_type if isinstance(event, Update) else type(event).__name__


def _action(event: TelegramObject) -> str:
    if not isinstance(event, Update):
        return "-"
    if event.callback_query is not None:
        return (event.callback_query.data or "-").split(":", 1)[0]
    if event.message is not None and (event.message.text or "").startswith("/"):
        return event.message.text.split()[0]
    return "-"
