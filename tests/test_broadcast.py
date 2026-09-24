from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.methods import CopyMessage

from app.bot.broadcast import parse_button_action, parse_button_text, parse_recipient_refs, post_markup, send_broadcast
from app.bot.handlers.broadcast import confirmation_keyboard, confirmation_text
from app.i18n import LocalizedError


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("https://example.com/a?b=1", {"url": "https://example.com/a?b=1"}),
        ("t.me/price_bird_bot", {"url": "https://t.me/price_bird_bot"}),
        ("tg://resolve?domain=durov", {"url": "tg://resolve?domain=durov"}),
        ("menu:newalert", {"callback_data": "menu:newalert"}),
    ],
)
def test_parse_button_action(text, expected):
    assert parse_button_action(text) == expected


@pytest.mark.parametrize("text", ["", "x" * 65, "ftp://example.com", "https://", "javascript://alert"])
def test_parse_button_action_rejects_invalid(text):
    with pytest.raises(LocalizedError):
        parse_button_action(text)


def test_parse_button_text_limits_length():
    assert parse_button_text("  Open  ") == "Open"
    with pytest.raises(LocalizedError):
        parse_button_text("x" * 65)


def test_parse_recipient_refs():
    assert parse_recipient_refs("123, @Alice\nbob_42;456") == ({123, 456}, {"alice", "bob_42"})
    with pytest.raises(LocalizedError):
        parse_recipient_refs("@a-b")


def test_confirmation_shows_count_buttons_and_send():
    buttons = [{"text": "Open <app>", "url": "https://example.com"}, {"text": "Go", "callback_data": "menu:alerts"}]
    text = confirmation_text({"recipient_ids": None, "buttons": buttons}, 42)
    markup = confirmation_keyboard(buttons, 42)

    assert "Recipients: <b>42</b> (all users)" in text
    assert "1. <b>Open &lt;app&gt;</b> → 🔗 https://example.com" in text
    assert "2. <b>Go</b> → ⚙️ <code>menu:alerts</code>" in text
    assert [button.callback_data for row in markup.inline_keyboard for button in row] == [
        "broadcast:add",
        "broadcast:remove",
        "broadcast:send",
        "broadcast:cancel",
    ]
    assert "broadcast:send" not in {b.callback_data for row in confirmation_keyboard([], 0).inline_keyboard for b in row}


@pytest.mark.asyncio
async def test_send_broadcast_retries_rate_limit_and_counts_failures():
    method = CopyMessage(chat_id=1, from_chat_id=9, message_id=5)
    bot = AsyncMock()
    bot.copy_message.side_effect = [
        TelegramRetryAfter(method=method, message="flood", retry_after=0),
        None,
        TelegramForbiddenError(method=method, message="blocked"),
        None,
    ]
    markup = post_markup([{"text": "Go", "url": "https://example.com"}])

    result = await send_broadcast(bot, recipients=[1, 2, 3], from_chat_id=9, message_id=5, markup=markup, interval=0)

    assert (result.sent, result.failed) == (2, 1)
    assert bot.copy_message.await_count == 4
    assert bot.copy_message.await_args.kwargs["reply_markup"] is markup
