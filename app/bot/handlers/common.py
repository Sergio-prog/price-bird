from __future__ import annotations

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards import start_menu_keyboard
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

    if repo.has_bot_access(user):
        await message.answer(
            "Welcome. Create a price alert, review active alerts, or use /alert BTC 10%.",
            reply_markup=start_menu_keyboard(),
        )
    else:
        await message.answer("Access pending. Ask an admin to whitelist your Telegram ID.")
