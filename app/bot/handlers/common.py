from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.commands import BOT_COMMANDS
from app.bot.keyboards import start_menu_keyboard
from app.bot.messages import help_message, start_message
from app.db import repositories as repo

router = Router(name="common")


@router.message(CommandStart())
async def start(message: Message, session: AsyncSession) -> None:
    tg_user = message.from_user
    if tg_user is None:
        return

    user = await repo.upsert_telegram_user(
        session,
        telegram_id=tg_user.id,
        username=tg_user.username,
        first_name=tg_user.first_name,
        last_name=tg_user.last_name,
        language_code=tg_user.language_code,
    )
    await session.commit()

    if repo.has_bot_access(user) and (message.text or "").split()[-1:] == ["alerts"]:
        from app.bot.handlers.alerts import alerts_message

        alerts = list(await repo.active_alerts_for_user(session, user.telegram_id))
        text, markup = alerts_message(alerts)
        await message.answer(text, reply_markup=markup, parse_mode="HTML")
        return

    if repo.has_bot_access(user):
        await message.answer(
            start_message(tg_user.first_name, tg_user.username),
            reply_markup=start_menu_keyboard(),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    else:
        await message.answer("Access pending. Ask an admin to whitelist your Telegram ID.")


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        help_message(BOT_COMMANDS),
        reply_markup=start_menu_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
