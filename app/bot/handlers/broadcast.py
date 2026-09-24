from __future__ import annotations

from html import escape
from typing import Any

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.types import InlineKeyboardButton as Button
from aiogram.types import InlineKeyboardMarkup as Markup
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.broadcast import (
    MAX_BUTTON_TEXT,
    MAX_BUTTONS,
    MAX_CALLBACK_BYTES,
    describe_buttons,
    parse_button_action,
    parse_button_text,
    parse_recipient_refs,
    post_markup,
    start_broadcast,
)
from app.bot.handlers.helpers import ensure_admin
from app.bot.states import Broadcast
from app.db import repositories as repo
from app.i18n import LocalizedError, t

router = Router(name="broadcast")

AUDIENCE_ALL = "all"
AUDIENCE_SPECIFIC = "specific"


def audience_keyboard(count: int) -> Markup:
    return Markup(
        inline_keyboard=[
            [Button(text=t("button-broadcast-all", count=count), callback_data="broadcast:audience:all")],
            [Button(text=t("button-broadcast-specific"), callback_data="broadcast:audience:specific")],
            [_cancel_button()],
        ]
    )


def confirmation_keyboard(buttons: list[dict[str, str]], count: int) -> Markup:
    edit_row = []
    if len(buttons) < MAX_BUTTONS:
        edit_row.append(Button(text=t("button-broadcast-add"), callback_data="broadcast:add", style="primary"))
    if buttons:
        edit_row.append(Button(text=t("button-broadcast-remove"), callback_data="broadcast:remove"))
    rows = [edit_row] if edit_row else []
    if count:
        rows.append([Button(text=t("button-broadcast-send", count=count), callback_data="broadcast:send", style="success")])
    rows.append([_cancel_button()])
    return Markup(inline_keyboard=rows)


def confirmation_text(data: dict[str, Any], count: int) -> str:
    audience = t("broadcast-audience-specific" if data.get("recipient_ids") is not None else "broadcast-audience-all")
    return t("broadcast-confirm", count=count, audience=audience, buttons=describe_buttons(data.get("buttons", [])))


def _back_keyboard() -> Markup:
    return Markup(inline_keyboard=[[Button(text=t("button-back"), callback_data="broadcast:back")]])


def _cancel_button() -> Button:
    return Button(text=t("button-broadcast-cancel"), callback_data="broadcast:cancel", style="danger")


@router.message(Command("broadcast"))
async def broadcast(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if message.chat.type != "private" or not await ensure_admin(message, session):
        return
    await state.clear()
    await state.set_state(Broadcast.audience)
    count = await repo.count_broadcast_recipients(session)
    await message.answer(t("broadcast-audience-prompt"), reply_markup=audience_keyboard(count), parse_mode="HTML")


@router.callback_query(Broadcast.audience, F.data.startswith("broadcast:audience:"))
async def choose_audience(callback: CallbackQuery, state: FSMContext) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return
    if (callback.data or "").endswith(AUDIENCE_SPECIFIC):
        await state.set_state(Broadcast.recipients)
        await callback.message.edit_text(t("broadcast-recipients-prompt"), reply_markup=_cancel_markup())
    else:
        await state.update_data(recipient_ids=None)
        await state.set_state(Broadcast.content)
        await callback.message.edit_text(t("broadcast-content-prompt"), reply_markup=_cancel_markup())
    await callback.answer()


@router.message(Broadcast.recipients, ~F.text.startswith("/"))
async def enter_recipients(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        telegram_ids, usernames = parse_recipient_refs(message.text or "")
    except LocalizedError as exc:
        await message.answer(str(exc), reply_markup=_cancel_markup())
        return
    users = await repo.find_users_by_refs(session, telegram_ids=telegram_ids, usernames=usernames)
    found_ids = {user.telegram_id for user in users}
    found_names = {(user.username or "").lower() for user in users}
    missing = [str(value) for value in sorted(telegram_ids - found_ids)]
    missing += [f"@{name}" for name in sorted(usernames - found_names)]
    if not users:
        await message.answer(t("broadcast-recipients-none"), reply_markup=_cancel_markup())
        return
    await state.update_data(recipient_ids=[user.telegram_id for user in users])
    await state.set_state(Broadcast.content)
    lines = [t("broadcast-recipients-found", count=len(users))]
    if missing:
        lines.append(t("broadcast-recipients-missing", refs=", ".join(missing)))
    lines.append(t("broadcast-content-prompt"))
    await message.answer("\n\n".join(lines), reply_markup=_cancel_markup())


@router.message(Broadcast.content, ~F.text.startswith("/"))
async def enter_content(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    await state.update_data(source_chat_id=message.chat.id, source_message_id=message.message_id, buttons=[])
    await _show_confirmation(bot, message.chat.id, state, session)


@router.callback_query(Broadcast.confirm, F.data == "broadcast:add")
async def add_button(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Broadcast.button_text)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(t("broadcast-button-text-prompt", max=MAX_BUTTON_TEXT), reply_markup=_back_keyboard())
    await callback.answer()


@router.message(Broadcast.button_text, ~F.text.startswith("/"))
async def enter_button_text(message: Message, state: FSMContext) -> None:
    try:
        text = parse_button_text(message.text or "")
    except LocalizedError as exc:
        await message.answer(str(exc), reply_markup=_back_keyboard())
        return
    await state.update_data(pending_button_text=text)
    await state.set_state(Broadcast.button_action)
    await message.answer(
        t("broadcast-button-action-prompt", text=escape(text), max=MAX_CALLBACK_BYTES),
        reply_markup=_back_keyboard(),
        parse_mode="HTML",
    )


@router.message(Broadcast.button_action, ~F.text.startswith("/"))
async def enter_button_action(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    try:
        action = parse_button_action(message.text or "")
    except LocalizedError as exc:
        await message.answer(str(exc), reply_markup=_back_keyboard())
        return
    data = await state.get_data()
    buttons = [*data.get("buttons", []), {"text": data["pending_button_text"], **action}]
    await state.update_data(buttons=buttons, pending_button_text=None)
    await _show_confirmation(bot, message.chat.id, state, session)


@router.callback_query(Broadcast.button_text, F.data == "broadcast:back")
@router.callback_query(Broadcast.button_action, F.data == "broadcast:back")
async def back_to_confirmation(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.set_state(Broadcast.confirm)
    await state.update_data(pending_button_text=None)
    await _edit_confirmation(callback, state, session)


@router.callback_query(Broadcast.confirm, F.data == "broadcast:remove")
async def remove_button(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    data = await state.get_data()
    buttons = data.get("buttons", [])[:-1]
    await state.update_data(buttons=buttons)
    if isinstance(callback.message, Message) and data.get("preview_message_id"):
        try:
            await bot.edit_message_reply_markup(
                chat_id=callback.message.chat.id,
                message_id=data["preview_message_id"],
                reply_markup=post_markup(buttons),
            )
        except TelegramBadRequest:
            await _show_confirmation(bot, callback.message.chat.id, state, session)
            await callback.answer()
            return
    await _edit_confirmation(callback, state, session)


@router.callback_query(Broadcast.confirm, F.data == "broadcast:send")
async def send(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return
    if not repo.is_admin(await repo.get_user_by_telegram_id(session, callback.from_user.id)):
        await state.clear()
        await callback.answer(t("admin-required"), show_alert=True)
        return
    data = await state.get_data()
    await state.clear()
    recipients = await _recipient_ids(session, data)
    if not recipients:
        await callback.message.edit_text(t("broadcast-no-recipients"))
        await callback.answer()
        return
    await callback.message.edit_text(t("broadcast-started", count=len(recipients)))
    await callback.answer()
    start_broadcast(
        bot,
        admin_chat_id=callback.message.chat.id,
        recipients=recipients,
        from_chat_id=data["source_chat_id"],
        message_id=data["source_message_id"],
        buttons=data.get("buttons", []),
    )


@router.callback_query(F.data == "broadcast:cancel")
async def cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(t("broadcast-cancelled"))
    await callback.answer()


@router.callback_query(F.data.startswith("broadcast:"))
async def expired(callback: CallbackQuery) -> None:
    await callback.answer(t("broadcast-expired"), show_alert=True)


def _cancel_markup() -> Markup:
    return Markup(inline_keyboard=[[_cancel_button()]])


async def _recipient_ids(session: AsyncSession, data: dict[str, Any]) -> list[int]:
    if data.get("recipient_ids") is not None:
        return list(data["recipient_ids"])
    return await repo.broadcast_recipient_ids(session)


async def _recipient_count(session: AsyncSession, data: dict[str, Any]) -> int:
    if data.get("recipient_ids") is not None:
        return len(data["recipient_ids"])
    return await repo.count_broadcast_recipients(session)


async def _show_confirmation(bot: Bot, chat_id: int, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    buttons = data.get("buttons", [])
    preview = await bot.copy_message(
        chat_id=chat_id,
        from_chat_id=data["source_chat_id"],
        message_id=data["source_message_id"],
        reply_markup=post_markup(buttons),
    )
    count = await _recipient_count(session, data)
    await bot.send_message(
        chat_id,
        confirmation_text(data, count),
        reply_markup=confirmation_keyboard(buttons, count),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await state.update_data(preview_message_id=preview.message_id)
    await state.set_state(Broadcast.confirm)


async def _edit_confirmation(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    count = await _recipient_count(session, data)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            confirmation_text(data, count),
            reply_markup=confirmation_keyboard(data.get("buttons", []), count),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    await callback.answer()
