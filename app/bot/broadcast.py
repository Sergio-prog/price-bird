from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from html import escape
from urllib.parse import urlsplit

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.i18n import LocalizedError, t

logger = logging.getLogger(__name__)

MAX_BUTTONS = 8
MAX_BUTTON_TEXT = 64
MAX_CALLBACK_BYTES = 64
MAX_URL_LENGTH = 2048
SEND_INTERVAL_SECONDS = 0.05
MAX_SEND_ATTEMPTS = 3
NETWORK_RETRY_SECONDS = 1.0
URL_SCHEMES = ("http", "https", "tg")
_REF_SPLIT_RE = re.compile(r"[\s,;]+")
_USERNAME_RE = re.compile(r"^@?(?P<name>[A-Za-z0-9_]{3,32})$")
_running: set[asyncio.Task[None]] = set()


@dataclass(frozen=True)
class BroadcastResult:
    sent: int
    failed: int


def parse_button_text(text: str) -> str:
    value = text.strip()
    if not value or len(value) > MAX_BUTTON_TEXT:
        raise LocalizedError("error-broadcast-button-text", max=MAX_BUTTON_TEXT)
    return value


def parse_button_action(text: str) -> dict[str, str]:
    value = text.strip()
    if value.lower().startswith("t.me/"):
        value = f"https://{value}"
    if "://" not in value:
        if not value or len(value.encode()) > MAX_CALLBACK_BYTES:
            raise LocalizedError("error-broadcast-button-data", max=MAX_CALLBACK_BYTES)
        return {"callback_data": value}
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise LocalizedError("error-broadcast-button-url") from exc
    if parsed.scheme.lower() not in URL_SCHEMES or not parsed.netloc or len(value) > MAX_URL_LENGTH or " " in value:
        raise LocalizedError("error-broadcast-button-url")
    return {"url": value}


def parse_recipient_refs(text: str) -> tuple[set[int], set[str]]:
    telegram_ids: set[int] = set()
    usernames: set[str] = set()
    for token in filter(None, _REF_SPLIT_RE.split(text.strip())):
        if token.isdigit():
            telegram_ids.add(int(token))
        elif match := _USERNAME_RE.match(token):
            usernames.add(match.group("name").lower())
        else:
            raise LocalizedError("error-broadcast-recipient", value=token)
    if not telegram_ids and not usernames:
        raise LocalizedError("error-broadcast-recipients-empty")
    return telegram_ids, usernames


def post_markup(buttons: Sequence[dict[str, str]]) -> InlineKeyboardMarkup | None:
    if not buttons:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(**button)] for button in buttons])


def describe_buttons(buttons: Sequence[dict[str, str]]) -> str:
    if not buttons:
        return t("broadcast-buttons-none")
    lines = []
    for index, button in enumerate(buttons, start=1):
        target = f"🔗 {escape(button['url'])}" if "url" in button else f"⚙️ <code>{escape(button['callback_data'])}</code>"
        lines.append(f"{index}. <b>{escape(button['text'])}</b> → {target}")
    return "\n" + "\n".join(lines)


async def send_broadcast(
    bot: Bot,
    *,
    recipients: Sequence[int],
    from_chat_id: int,
    message_id: int,
    markup: InlineKeyboardMarkup | None,
    interval: float = SEND_INTERVAL_SECONDS,
) -> BroadcastResult:
    sent = 0
    for chat_id in recipients:
        if await _copy(bot, chat_id, from_chat_id, message_id, markup):
            sent += 1
        await asyncio.sleep(interval)
    return BroadcastResult(sent=sent, failed=len(recipients) - sent)


def start_broadcast(
    bot: Bot,
    *,
    admin_chat_id: int,
    recipients: Sequence[int],
    from_chat_id: int,
    message_id: int,
    buttons: Sequence[dict[str, str]],
) -> None:
    task = asyncio.create_task(
        _run_broadcast(
            bot,
            admin_chat_id=admin_chat_id,
            recipients=list(recipients),
            from_chat_id=from_chat_id,
            message_id=message_id,
            markup=post_markup(buttons),
        )
    )
    _running.add(task)
    task.add_done_callback(_running.discard)


async def _run_broadcast(
    bot: Bot,
    *,
    admin_chat_id: int,
    recipients: list[int],
    from_chat_id: int,
    message_id: int,
    markup: InlineKeyboardMarkup | None,
) -> None:
    logger.info("Broadcast started; admin=%s recipients=%s", admin_chat_id, len(recipients))
    result = await send_broadcast(bot, recipients=recipients, from_chat_id=from_chat_id, message_id=message_id, markup=markup)
    logger.info("Broadcast finished; admin=%s sent=%s failed=%s", admin_chat_id, result.sent, result.failed)
    try:
        await bot.send_message(
            admin_chat_id,
            t("broadcast-finished", sent=result.sent, failed=result.failed, total=len(recipients)),
        )
    except Exception:
        logger.exception("Broadcast report failed; admin=%s", admin_chat_id)


async def _copy(
    bot: Bot,
    chat_id: int,
    from_chat_id: int,
    message_id: int,
    markup: InlineKeyboardMarkup | None,
) -> bool:
    for _ in range(MAX_SEND_ATTEMPTS):
        try:
            await bot.copy_message(
                chat_id=chat_id,
                from_chat_id=from_chat_id,
                message_id=message_id,
                reply_markup=markup,
            )
            return True
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
        except TelegramNetworkError:
            await asyncio.sleep(NETWORK_RETRY_SECONDS)
        except (TelegramForbiddenError, TelegramBadRequest) as exc:
            logger.info("Broadcast skipped; chat_id=%s error=%s", chat_id, exc.message)
            return False
        except Exception:
            logger.exception("Broadcast send failed; chat_id=%s", chat_id)
            return False
    logger.warning("Broadcast gave up; chat_id=%s", chat_id)
    return False
