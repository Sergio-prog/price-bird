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

from app.db.models import ConnectedApp, Delivery, IntegrationDefinition, User
from app.db.repositories.users import get_user_by_telegram_id, has_bot_access
from app.delivery.events import queue_test
from app.i18n import LOCALE_NAMES, SUPPORTED_LOCALES, current_locale, t, use_locale
from app.integrations.access import can_use_connection, can_use_custom_webhooks, can_use_integrations
from app.integrations.secrets import decrypt_secret, ensure_encryption_configured
from app.integrations.service import connection_secret, connection_url, create_custom_connection, rotate_custom_secret
from app.integrations.urls import validate_url

router = Router(name="settings")
TRENCHBOOK_BOT_URL = "https://t.me/trenches_fotex_bot"
MAX_CONNECTIONS = 20


class ConnectionWizard(StatesGroup):
    url = State()


def keyboard(rows):
    return Markup(inline_keyboard=[[Button(text=text, callback_data=data) for text, data in row] for row in rows])


async def owned_user(session, telegram_id):
    user = await get_user_by_telegram_id(session, telegram_id)
    return user if has_bot_access(user) else None


def _state_label(enabled: bool) -> str:
    return t("state-on" if enabled else "state-off")


async def settings_view(session, user):
    connections = []
    if can_use_integrations(user) or can_use_custom_webhooks(user):
        connections = [
            connection
            for connection in await session.scalars(
                select(ConnectedApp)
                .where(
                    ConnectedApp.user_id == user.id,
                    ConnectedApp.deleted.is_(False),
                )
                .options(selectinload(ConnectedApp.integration_definition))
                .order_by(ConnectedApp.created_at)
            )
            if can_use_connection(user, connection)
        ]
    definitions = []
    if can_use_integrations(user):
        definitions = list(
            await session.scalars(
                select(IntegrationDefinition)
                .where(IntegrationDefinition.enabled.is_(True))
                .order_by(IntegrationDefinition.name)
            )
        )
    rows = [
        [(t("settings-bird", state=_state_label(user.bird_enabled)), "settings:bird")],
        [(t("settings-language", language=LOCALE_NAMES[current_locale()]), "settings:language")],
    ]
    rows += [
        [(t("settings-connection", name=c.name, state=_state_label(c.enabled)), f"settings:view:{c.id}")] for c in connections
    ]
    connected_definition_ids = {connection.integration_definition_id for connection in connections}
    rows += [
        [(t("settings-connect", name=definition.name), f"settings:connect:{definition.id}")]
        for definition in definitions
        if definition.id not in connected_definition_ids
    ]
    if can_use_custom_webhooks(user):
        rows.append([(t("settings-add-webhook"), "settings:add")])
    rows.append([(t("button-back"), "wizard:cancel")])

    text = t("settings-text")
    if can_use_integrations(user) or can_use_custom_webhooks(user):
        text = t("settings-text-connections")
    if can_use_integrations(user):
        text += "\n\n" + t("settings-trenchbook-hint", url=TRENCHBOOK_BOT_URL)
    return text, keyboard(rows)


def language_view() -> tuple[str, Markup]:
    rows = [
        [(f"{'✅ ' if locale == current_locale() else ''}{LOCALE_NAMES[locale]}", f"settings:language:{locale}")]
        for locale in SUPPORTED_LOCALES
    ]
    rows.append([(t("button-back"), "settings:open")])
    return t("language-prompt"), keyboard(rows)


@router.message(Command("settings"))
async def open_settings(message: Message, state: FSMContext, session: AsyncSession):
    user = await _private_user(message, session)
    if not user:
        return
    await state.clear()
    text, markup = await settings_view(session, user)
    await message.answer(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)


@router.message(Command("language"))
async def open_language(message: Message, state: FSMContext, session: AsyncSession):
    if not await _private_user(message, session):
        return
    await state.clear()
    text, markup = language_view()
    await message.answer(text, reply_markup=markup)


async def _private_user(message: Message, session: AsyncSession) -> User | None:
    if message.chat.type != "private":
        await message.answer(t("settings-private-only"))
        return None
    user = await owned_user(session, message.from_user.id) if message.from_user else None
    if not user:
        await message.answer(t("access-denied"))
    return user


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
        await callback.answer(t("access-denied"), show_alert=True)
        return
    if callback.message.chat.type != "private":
        await callback.answer(t("private-chat-required"), show_alert=True)
        return
    parts = callback.data.split(":")
    action = parts[1]
    await state.clear()
    if action == "language":
        await _language_callback(callback, session, user, parts)
        return
    connection = None
    connection_actions = {"view", "toggle", "disconnect", "rotate", "test", "retry"}
    if action in connection_actions:
        if len(parts) != 3:
            await callback.answer(t("invalid-connection-action"))
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
            await callback.answer(t("connection-not-found"))
            return
        if not can_use_connection(user, connection):
            await callback.answer(t("admin-only-destination"), show_alert=True)
            return
    if action == "bird":
        await session.refresh(user, with_for_update=True)
        user.bird_enabled = not user.bird_enabled
        if not user.bird_enabled:
            await cancel_pending(session, user.id)
    elif action == "add":
        if not can_use_custom_webhooks(user):
            await callback.answer(t("admin-only-custom-webhooks"), show_alert=True)
            return
        try:
            ensure_encryption_configured()
        except ValueError as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        await state.set_state(ConnectionWizard.url)
        await callback.message.edit_text(t("custom-webhook-prompt"))
        await callback.answer()
        return
    elif action == "connect":
        if not can_use_integrations(user):
            await callback.answer(t("admin-only-integrations"), show_alert=True)
            return
        if len(parts) != 3:
            await callback.answer(t("integration-not-found"))
            return
        definition = await session.scalar(
            select(IntegrationDefinition)
            .where(IntegrationDefinition.id == parts[2], IntegrationDefinition.enabled.is_(True))
            .with_for_update()
        )
        if definition is None:
            await callback.answer(t("integration-not-found"))
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
            if (connected_count or 0) >= MAX_CONNECTIONS:
                await callback.answer(t("connections-limit", limit=MAX_CONNECTIONS), show_alert=True)
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
            await callback.message.answer(t("new-signing-secret", secret=secret), protect_content=True)
            await cancel_pending(session, user.id, connection.id)
        elif action in {"test", "retry"}:
            if not connection.enabled:
                await callback.answer(t("enable-connection-first"))
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
                await callback.answer(t("delivery-already-pending"))
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
        text, markup = await _connection_view(session, connection)
    else:
        text, markup = await settings_view(session, user)
    await _edit(callback.message, text, markup)
    await callback.answer()


async def _language_callback(callback: CallbackQuery, session: AsyncSession, user: User, parts: list[str]) -> None:
    if len(parts) == 3 and parts[2] in SUPPORTED_LOCALES:
        user.language = parts[2]
        await session.commit()
        with use_locale(user.language):
            text, markup = await settings_view(session, user)
            await _edit(callback.message, text, markup)
            await callback.answer()
        return
    text, markup = language_view()
    await _edit(callback.message, text, markup)
    await callback.answer()


async def _connection_view(session: AsyncSession, connection: ConnectedApp) -> tuple[str, Markup]:
    last = await session.scalar(
        select(Delivery).where(Delivery.connection_id == connection.id).order_by(Delivery.created_at.desc()).limit(1)
    )
    try:
        host = urlsplit(connection_url(connection)).hostname
    except ValueError:
        host = None
    name = escape(connection.name)
    if connection.integration_definition and connection.integration_definition.slug == "trenchbook":
        name = f'<a href="{TRENCHBOOK_BOT_URL}">{name}</a>'
    lines = [
        name,
        t("connection-host", host=escape(host or t("host-unavailable"))),
        t("connection-notifications", state=_state_label(connection.enabled)),
    ]
    if last:
        status = escape(last.status) + (f" ({escape(last.last_error)})" if last.last_error else "")
        lines.append(t("connection-last-delivery", status=status))
    rows = [
        [(t("button-disable" if connection.enabled else "button-enable"), f"settings:toggle:{connection.id}")],
        [
            (t("button-send-test"), f"settings:test:{connection.id}"),
            (t("button-retry-failure"), f"settings:retry:{connection.id}"),
        ],
    ]
    if connection.kind == "custom":
        rows.append([(t("button-rotate-secret"), f"settings:rotate:{connection.id}")])
    rows += [[(t("button-disconnect"), f"settings:disconnect:{connection.id}")], [(t("button-back"), "settings:open")]]
    return "\n".join(lines), keyboard(rows)


async def _edit(message: Message, text: str, markup: Markup) -> None:
    try:
        await message.edit_text(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            raise


@router.message(ConnectionWizard.url, ~F.text.startswith("/"))
async def add_custom(message: Message, state: FSMContext, session: AsyncSession):
    if message.chat.type != "private":
        await message.answer(t("settings-private-only"))
        return
    user = await owned_user(session, message.from_user.id) if message.from_user else None
    if not user:
        return
    if not can_use_custom_webhooks(user):
        await state.clear()
        await message.answer(t("admin-only-custom-webhooks"))
        return
    text = (message.text or "").strip()
    try:
        name, url = text.rsplit(" ", 1)
        if not name or len(name) > 80:
            raise ValueError(t("webhook-name-too-long"))
        url = validate_url(url)
    except ValueError as exc:
        await message.answer(str(exc) if " " in text else t("webhook-name-and-url"))
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
    if len(connections) >= MAX_CONNECTIONS:
        await message.answer(t("connections-limit", limit=MAX_CONNECTIONS))
        return
    try:
        connection, secret = create_custom_connection(user_id=user.id, name=name, url=url)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    session.add(connection)
    await session.commit()
    await state.clear()
    await message.answer(t("custom-webhook-connected", name=name, secret=secret), protect_content=True)
    text, markup = await settings_view(session, user)
    await message.answer(text, reply_markup=markup)
