from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.helpers import command_int_arg, ensure_admin
from app.db import repositories as repo
from app.db.enums import AccessStatus, UserRole

router = Router(name="admin")


@router.message(Command("whitelist"))
async def whitelist(message: Message, session: AsyncSession) -> None:
    if not await ensure_admin(message, session):
        return
    telegram_id = command_int_arg(message)
    if telegram_id is None:
        await message.answer("Usage: /whitelist 123456789")
        return
    await repo.set_user_access(session, telegram_id=telegram_id, access_status=AccessStatus.ACTIVE)
    await session.commit()
    await message.answer(f"Whitelisted {telegram_id}.")


@router.message(Command("suspend"))
async def suspend(message: Message, session: AsyncSession) -> None:
    if not await ensure_admin(message, session):
        return
    telegram_id = command_int_arg(message)
    if telegram_id is None:
        await message.answer("Usage: /suspend 123456789")
        return
    await repo.set_user_access(session, telegram_id=telegram_id, access_status=AccessStatus.SUSPENDED)
    await session.commit()
    await message.answer(f"Suspended {telegram_id}.")


@router.message(Command("promote"))
async def promote(message: Message, session: AsyncSession) -> None:
    if not await ensure_admin(message, session):
        return
    telegram_id = command_int_arg(message)
    if telegram_id is None:
        await message.answer("Usage: /promote 123456789")
        return
    await repo.set_user_access(
        session,
        telegram_id=telegram_id,
        access_status=AccessStatus.ACTIVE,
        role=UserRole.ADMIN,
    )
    await session.commit()
    await message.answer(f"Promoted {telegram_id}.")


@router.message(Command("users"))
async def users(message: Message, session: AsyncSession) -> None:
    if not await ensure_admin(message, session):
        return
    rows = await repo.list_users(session)
    text = "\n".join(f"{u.telegram_id} @{u.username or '-'} {u.role}/{u.access_status}" for u in rows)
    await message.answer(text or "No users.")


@router.message(Command("stats"))
async def stats(message: Message, session: AsyncSession) -> None:
    if not await ensure_admin(message, session):
        return
    data = await repo.get_stats(session)
    await message.answer(
        f"Users: {data['users']}\nActive alerts: {data['active_alerts']}\nWatched assets: {data['watched_assets']}"
    )
