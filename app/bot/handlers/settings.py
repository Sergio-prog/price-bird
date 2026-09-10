from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit
from uuid import uuid4

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.types import InlineKeyboardButton as Button
from aiogram.types import InlineKeyboardMarkup as Markup
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import ConnectedApp, Delivery
from app.db.repositories.users import get_user_by_telegram_id, has_bot_access
from app.delivery.events import queue_test
from app.delivery.webhook import connection_secret, validate_url

router = Router(name="settings")


class ConnectionWizard(StatesGroup):
    url = State()
    alert_value = State()


def keyboard(rows):
    return Markup(inline_keyboard=[[Button(text=text, callback_data=data) for text, data in row] for row in rows])


async def owned_user(session, telegram_id):
    user = await get_user_by_telegram_id(session, telegram_id)
    return user if has_bot_access(user) else None


async def settings_view(session, user):
    connections = list(
        await session.scalars(
            select(ConnectedApp)
            .where(
                ConnectedApp.user_id == user.id,
                ConnectedApp.deleted.is_(False),
            )
            .order_by(ConnectedApp.created_at)
        )
    )
    rows = [[(f"Price Bird notifications: {'on' if user.bird_enabled else 'off'}", "settings:bird")]]
    rows += [[(f"{c.name}: {'on' if c.enabled else 'off'}", f"settings:view:{c.id}")] for c in connections]
    if settings.trenchbook_webhook_url and len(settings.trenchbook_webhook_secret) >= 32:
        if not any(c.kind == "trenchbook" for c in connections):
            rows.append([("Connect Trenchbook", "settings:trenchbook")])
    rows += [[("Add custom webhook", "settings:add")], [("Back", "wizard:cancel")]]
    return (
        "Delivery settings\n\nChoose where all your alerts are sent. Turn on Price Bird, a connected app, or both. "
        "Turning off a destination cancels its pending deliveries. Alerts keep evaluating. "
        "Pause individual alerts from /alerts.\n\nTrenchbook uses your same Telegram account; start its bot first.",
        keyboard(rows),
    )


@router.message(Command("settings"))
async def open_settings(message: Message, state: FSMContext, session: AsyncSession):
    if message.chat.type != "private":
        await message.answer("Open a private chat with Price Bird to manage settings.")
        return
    user = await owned_user(session, message.from_user.id) if message.from_user else None
    if not user:
        await message.answer("Access denied.")
        return
    await state.clear()
    text, markup = await settings_view(session, user)
    await message.answer(text, reply_markup=markup)


async def cancel_pending(session, user_id, connection_id=None):
    query = update(Delivery).where(Delivery.user_id == user_id, Delivery.status.in_(["pending", "sending"]))
    query = (
        query.where(Delivery.connection_id == connection_id) if connection_id else query.where(Delivery.destination == "bird")
    )
    await session.execute(query.values(status="cancelled", lease_token=None, leased_until=None))


@router.callback_query(F.data.startswith("settings:"))
async def settings_callback(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    user = await owned_user(session, callback.from_user.id)
    if not user or not isinstance(callback.message, Message):
        await callback.answer("Access denied", show_alert=True)
        return
    if callback.message.chat.type != "private":
        await callback.answer("Open Price Bird in a private chat", show_alert=True)
        return
    parts = callback.data.split(":")
    action = parts[1]
    await state.clear()
    connection = None
    if len(parts) == 3:
        connection = await session.scalar(
            select(ConnectedApp)
            .where(
                ConnectedApp.id == parts[2],
                ConnectedApp.user_id == user.id,
                ConnectedApp.deleted.is_(False),
            )
            .with_for_update()
        )
        if not connection:
            await callback.answer("Connection not found")
            return
    if action == "bird":
        await session.refresh(user, with_for_update=True)
        user.bird_enabled = not user.bird_enabled
        if not user.bird_enabled:
            await cancel_pending(session, user.id)
    elif action == "add":
        if len(settings.webhook_signing_key) < 32:
            await callback.answer("Custom webhooks are not configured by the operator", show_alert=True)
            return
        await state.set_state(ConnectionWizard.url)
        await callback.message.edit_text(
            "Send a name and HTTPS webhook URL, for example:\nMy app https://example.com/webhook\n\n/cancel to stop."
        )
        await callback.answer()
        return
    elif action == "trenchbook":
        try:
            url = validate_url(settings.trenchbook_webhook_url)
            if len(settings.trenchbook_webhook_secret) < 32:
                raise ValueError("Trenchbook is not configured")
        except ValueError as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        await session.refresh(user, with_for_update=True)
        existing = await session.scalar(
            select(ConnectedApp).where(
                ConnectedApp.user_id == user.id,
                ConnectedApp.kind == "trenchbook",
                ConnectedApp.deleted.is_(False),
            )
        )
        if not existing:
            session.add(ConnectedApp(id=str(uuid4()), user_id=user.id, kind="trenchbook", name="Trenchbook", url=url))
    elif connection:
        if action == "toggle":
            connection.enabled = not connection.enabled
            if not connection.enabled:
                await cancel_pending(session, user.id, connection.id)
        elif action == "disconnect":
            connection.deleted = True
            connection.enabled = False
            await cancel_pending(session, user.id, connection.id)
        elif action == "rotate" and connection.kind == "custom":
            connection.secret_version += 1
            await session.flush()
            await callback.message.answer(
                f"New signing secret. Update your receiver before enabling delivery:\n{connection_secret(connection)}",
                protect_content=True,
            )
            connection.enabled = False
            await cancel_pending(session, user.id, connection.id)
        elif action in {"test", "retry"}:
            if not connection.enabled:
                await callback.answer("Enable this connection first")
                return
            pending = await session.scalar(
                select(Delivery.id)
                .where(
                    Delivery.connection_id == connection.id,
                    Delivery.status.in_(["pending", "sending"]),
                )
                .limit(1)
            )
            if pending:
                await callback.answer("Delivery already pending")
                return
            if action == "test":
                await queue_test(session, connection, user.telegram_id)
            else:
                failed = await session.scalar(
                    select(Delivery)
                    .where(
                        Delivery.connection_id == connection.id,
                        Delivery.status == "failed",
                        Delivery.created_at > datetime.now(UTC) - timedelta(days=7),
                    )
                    .order_by(Delivery.created_at.desc())
                    .limit(1)
                    .with_for_update()
                )
                if failed:
                    failed.status, failed.attempts, failed.next_attempt_at = "pending", 0, datetime.now(UTC)
    await session.commit()
    if connection and not connection.deleted:
        last = await session.scalar(
            select(Delivery).where(Delivery.connection_id == connection.id).order_by(Delivery.created_at.desc()).limit(1)
        )
        text = (
            f"{connection.name}\nHost: {urlsplit(connection.url).hostname}\n"
            f"Notifications: {'on' if connection.enabled else 'off'}"
        )
        if last:
            text += f"\nLast delivery: {last.status}" + (f" ({last.last_error})" if last.last_error else "")
        rows = [
            [("Disable" if connection.enabled else "Enable", f"settings:toggle:{connection.id}")],
            [("Send test", f"settings:test:{connection.id}"), ("Retry last failure", f"settings:retry:{connection.id}")],
        ]
        if connection.kind == "custom":
            rows.append([("Rotate signing secret", f"settings:rotate:{connection.id}")])
        rows += [[("Disconnect", f"settings:disconnect:{connection.id}")], [("Back", "settings:open")]]
        markup = keyboard(rows)
    else:
        text, markup = await settings_view(session, user)
    # Sending a new message also avoids Telegram's 'message is not modified' on test/retry.
    await callback.message.answer(text, reply_markup=markup)
    await callback.answer()


@router.message(ConnectionWizard.url, ~F.text.startswith("/"))
async def add_custom(message: Message, state: FSMContext, session: AsyncSession):
    if message.chat.type != "private":
        await message.answer("Open a private chat with Price Bird to manage settings.")
        return
    user = await owned_user(session, message.from_user.id) if message.from_user else None
    if not user:
        return
    text = (message.text or "").strip()
    try:
        name, url = text.rsplit(" ", 1)
        if not name or len(name) > 80:
            raise ValueError("Use a name with at most 80 characters.")
        validate_url(url)
        connection = ConnectedApp(
            id=str(uuid4()), user_id=user.id, name=name, kind="custom", url=url, secret_version=1, enabled=False
        )
        secret = connection_secret(connection)
    except ValueError as exc:
        await message.answer(str(exc) if " " in text else "Send a name followed by the HTTPS URL.")
        return
    await session.refresh(user, with_for_update=True)
    connections = list(
        await session.scalars(
            select(ConnectedApp.id).where(
                ConnectedApp.user_id == user.id,
                ConnectedApp.deleted.is_(False),
            )
        )
    )
    if len(connections) >= 20:
        await message.answer("You can connect up to 20 apps.")
        return
    session.add(connection)
    await session.commit()
    await state.clear()
    await message.answer(
        f"Connected {name}. Store this signing secret in your receiver:\n{secret}\n\n"
        "Requests use HMAC-SHA256. Configure your receiver, then enable the connection in Settings.",
        protect_content=True,
    )
    text, markup = await settings_view(session, user)
    await message.answer(text, reply_markup=markup)
