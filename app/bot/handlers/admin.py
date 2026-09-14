from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.helpers import command_int_arg, ensure_admin
from app.db import repositories as repo
from app.db.enums import AccessStatus, UserRole
from app.delivery.events import queue_trenchbook_debug_alert
from app.i18n import t

router = Router(name="admin")


@router.message(Command("whitelist"))
async def whitelist(message: Message, session: AsyncSession) -> None:
    if not await ensure_admin(message, session):
        return
    telegram_id = command_int_arg(message)
    if telegram_id is None:
        await message.answer(t("admin-usage", command="whitelist"))
        return
    await repo.set_user_access(session, telegram_id=telegram_id, access_status=AccessStatus.ACTIVE)
    await session.commit()
    await message.answer(t("admin-whitelisted", telegram_id=str(telegram_id)))


@router.message(Command("suspend"))
async def suspend(message: Message, session: AsyncSession) -> None:
    if not await ensure_admin(message, session):
        return
    telegram_id = command_int_arg(message)
    if telegram_id is None:
        await message.answer(t("admin-usage", command="suspend"))
        return
    await repo.set_user_access(session, telegram_id=telegram_id, access_status=AccessStatus.SUSPENDED)
    await session.commit()
    await message.answer(t("admin-suspended", telegram_id=str(telegram_id)))


@router.message(Command("promote"))
async def promote(message: Message, session: AsyncSession) -> None:
    if not await ensure_admin(message, session):
        return
    telegram_id = command_int_arg(message)
    if telegram_id is None:
        await message.answer(t("admin-usage", command="promote"))
        return
    await repo.set_user_access(
        session,
        telegram_id=telegram_id,
        access_status=AccessStatus.ACTIVE,
        role=UserRole.ADMIN,
    )
    await session.commit()
    await message.answer(t("admin-promoted", telegram_id=str(telegram_id)))


@router.message(Command("users"))
async def users(message: Message, session: AsyncSession) -> None:
    if not await ensure_admin(message, session):
        return
    rows = await repo.list_users(session)
    text = "\n".join(f"{u.telegram_id} @{u.username or '-'} {u.role}/{u.access_status}" for u in rows)
    await message.answer(text or t("admin-no-users"))


@router.message(Command("stats"))
async def stats(message: Message, session: AsyncSession) -> None:
    if not await ensure_admin(message, session):
        return
    data = await repo.get_stats(session)
    await message.answer(
        t(
            "admin-stats",
            users=str(data["users"]),
            active_alerts=str(data["active_alerts"]),
            watched_assets=str(data["watched_assets"]),
        )
    )


@router.message(Command("debugalert"))
async def debug_alert(message: Message, session: AsyncSession) -> None:
    if not await ensure_admin(message, session) or message.from_user is None:
        return
    user = await repo.get_user_by_telegram_id(session, message.from_user.id)
    alert_id = await queue_trenchbook_debug_alert(session, user.id)
    if alert_id is None:
        await message.answer(t("admin-debug-connect-trenchbook"))
        return
    if not alert_id:
        await message.answer(t("admin-debug-no-alert"))
        return
    await session.commit()
    await message.answer(t("admin-debug-queued", alert_id=alert_id))
