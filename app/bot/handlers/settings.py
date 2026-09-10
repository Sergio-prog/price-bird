from __future__ import annotations

from datetime import UTC, datetime, timedelta
from html import escape
from urllib.parse import urlsplit
from uuid import uuid4

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.types import InlineKeyboardButton as Button
from aiogram.types import InlineKeyboardMarkup as Markup
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import ConnectedApp, Delivery, IntegrationDefinition
from app.db.repositories.users import get_user_by_telegram_id, has_bot_access
from app.delivery.events import queue_test
from app.integrations.secrets import decrypt_secret, ensure_encryption_configured
from app.integrations.service import connection_secret, connection_url, create_custom_connection, rotate_custom_secret
from app.integrations.urls import validate_url

router = Router(name="settings")
TRENCHBOOK_BOT_URL = "https://t.me/trenches_fotex_bot"


class ConnectionWizard(StatesGroup):
    url = State()


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
            .options(selectinload(ConnectedApp.integration_definition))
            .order_by(ConnectedApp.created_at)
        )
    )
    definitions = list(
        await session.scalars(
            select(IntegrationDefinition).where(IntegrationDefinition.enabled.is_(True)).order_by(IntegrationDefinition.name)
        )
    )
    rows = [[(f"Price Bird notifications: {'on' if user.bird_enabled else 'off'}", "settings:bird")]]
    rows += [[(f"{c.name}: {'on' if c.enabled else 'off'}", f"settings:view:{c.id}")] for c in connections]
    connected_definition_ids = {connection.integration_definition_id for connection in connections}
    rows += [
        [(f"Connect {definition.name}", f"settings:connect:{definition.id}")]
        for definition in definitions
        if definition.id not in connected_definition_ids
    ]
    rows += [[("Add custom webhook", "settings:add")], [("Back", "wizard:cancel")]]
    return (
        "Delivery settings\n\nChoose where all your alerts are sent. Turn on Price Bird, a connected app, or both. "
        "Turning off a destination cancels its pending deliveries. Alerts keep evaluating. "
        "Pause individual alerts from /alerts.\n\n"
        f'<a href="{TRENCHBOOK_BOT_URL}">Trenchbook</a> uses your same Telegram account; start its bot first.',
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
    await message.answer(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)


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
    connection_actions = {"view", "toggle", "disconnect", "rotate", "test", "retry"}
    if action in connection_actions:
        if len(parts) != 3:
            await callback.answer("Invalid connection action")
            return
        connection = await session.scalar(
            select(ConnectedApp)
            .where(
                ConnectedApp.id == parts[2],
                ConnectedApp.user_id == user.id,
                ConnectedApp.deleted.is_(False),
            )
            .options(selectinload(ConnectedApp.integration_definition))
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
        try:
            ensure_encryption_configured()
        except ValueError as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        await state.set_state(ConnectionWizard.url)
        await callback.message.edit_text(
            "Send a name and HTTPS webhook URL, for example:\nMy app https://example.com/webhook\n\n/cancel to stop."
        )
        await callback.answer()
        return
    elif action == "connect":
        if len(parts) != 3:
            await callback.answer("Integration not found")
            return
        definition = await session.scalar(
            select(IntegrationDefinition)
            .where(IntegrationDefinition.id == parts[2], IntegrationDefinition.enabled.is_(True))
            .with_for_update()
        )
        if definition is None:
            await callback.answer("Integration not found")
            return
        try:
            decrypt_secret(definition.secret_encrypted)
        except ValueError as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        existing = await session.scalar(
            select(ConnectedApp)
            .where(
                ConnectedApp.user_id == user.id,
                ConnectedApp.integration_definition_id == definition.id,
            )
            .options(selectinload(ConnectedApp.integration_definition))
            .with_for_update()
        )
        if existing is None:
            connected_count = await session.scalar(
                select(func.count())
                .select_from(ConnectedApp)
                .where(
                    ConnectedApp.user_id == user.id,
                    ConnectedApp.deleted.is_(False),
                )
            )
            if (connected_count or 0) >= 20:
                await callback.answer("You can connect up to 20 apps.", show_alert=True)
                return
            connection = ConnectedApp(
                id=str(uuid4()),
                user_id=user.id,
                integration_definition_id=definition.id,
                integration_definition=definition,
                kind="default",
                name=definition.name,
                url=None,
                enabled=True,
            )
            session.add(connection)
        else:
            connection = existing
            connection.integration_definition = definition
            connection.name = definition.name
            connection.kind = "default"
            connection.url = None
            connection.deleted = False
            connection.enabled = True
    elif connection:
        if action == "toggle":
            if not connection.enabled:
                try:
                    connection_url(connection)
                    connection_secret(connection)
                except ValueError as exc:
                    await callback.answer(str(exc), show_alert=True)
                    return
            connection.enabled = not connection.enabled
            if not connection.enabled:
                await cancel_pending(session, user.id, connection.id)
        elif action == "disconnect":
            connection.deleted = True
            connection.enabled = False
            await cancel_pending(session, user.id, connection.id)
        elif action == "rotate" and connection.kind == "custom":
            secret = rotate_custom_secret(connection)
            await callback.message.answer(
                f"New signing secret. Update your receiver before enabling delivery:\n{secret}",
                protect_content=True,
            )
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
        try:
            host = urlsplit(connection_url(connection)).hostname
        except ValueError:
            host = "unavailable"
        name = escape(connection.name)
        if connection.integration_definition and connection.integration_definition.slug == "trenchbook":
            name = f'<a href="{TRENCHBOOK_BOT_URL}">{name}</a>'
        text = f"{name}\nHost: {escape(host or 'unavailable')}\nNotifications: {'on' if connection.enabled else 'off'}"
        if last:
            text += f"\nLast delivery: {escape(last.status)}" + (f" ({escape(last.last_error)})" if last.last_error else "")
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
    try:
        await callback.message.edit_text(
            text,
            reply_markup=markup,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            raise
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
        url = validate_url(url)
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
    try:
        connection, secret = create_custom_connection(user_id=user.id, name=name, url=url)
    except ValueError as exc:
        await message.answer(str(exc))
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
