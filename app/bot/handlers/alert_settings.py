from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from html import escape

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.alerts.formatting import (
    format_cooldown,
    format_decimal,
    format_direction,
    format_direction_arrows,
    format_threshold,
)
from app.alerts.service import asset_kind_label, describe_alert
from app.bot.handlers.alerts import alerts_message
from app.bot.handlers.settings import keyboard, owned_user
from app.bot.keyboards import one_time_label
from app.bot.states import AlertEdit
from app.db import repositories as repo
from app.db.enums import AlertStatus, AlertType
from app.db.models import Alert

router = Router(name="alert_settings")

COOLDOWN_OPTIONS = [60, 900, 3600, 86400]
DIRECTION_OPTIONS = ["both", "up", "down"]
EDITABLE_STATUSES = [AlertStatus.ACTIVE.value, AlertStatus.PAUSED.value]


@router.callback_query(F.data.startswith("alert_config:"))
async def configure_alert(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    user = await owned_user(session, callback.from_user.id)
    if not user or not isinstance(callback.message, Message):
        await callback.answer("Access denied")
        return
    if callback.message.chat.type != "private":
        await callback.answer("Open Price Bird in a private chat", show_alert=True)
        return
    await state.clear()
    parts = callback.data.split(":")
    if len(parts) != 3 or not parts[2].isdigit():
        await callback.answer("Invalid alert")
        return
    alert = await _load_alert(session, user.id, int(parts[2]))
    if not alert:
        await callback.answer("Alert not found")
        return
    action = parts[1]
    if action in {"threshold", "note"}:
        await state.set_state(AlertEdit.waiting_value)
        await state.update_data(alert_id=alert.id, field=action)
        await callback.message.answer(_value_prompt(alert, action))
        await callback.answer()
        return
    if action == "delete":
        await _edit(callback.message, _confirm_delete_text(alert), _confirm_delete_keyboard(alert))
        await callback.answer()
        return
    if action == "confirm_delete":
        alert.status = AlertStatus.DELETED.value
        await session.commit()
        alerts = list(await repo.active_alerts_for_user(session, user.telegram_id))
        text, markup = alerts_message(alerts)
        await _edit(callback.message, text, markup)
        await callback.answer("Deleted")
        return
    if action == "direction" and alert.type == AlertType.PERCENT_CHANGE.value:
        alert.direction = _next_option(DIRECTION_OPTIONS, alert.direction)
    elif action == "expiry":
        alert.expires_at = None if alert.expires_at else datetime.now(UTC) + timedelta(days=7)
    elif action == "pause":
        if alert.status == AlertStatus.PAUSED.value and alert.expires_at and alert.expires_at <= datetime.now(UTC):
            await callback.answer("Clear the expiry before resuming", show_alert=True)
            return
        alert.status = AlertStatus.PAUSED.value if alert.status == AlertStatus.ACTIVE.value else AlertStatus.ACTIVE.value
    elif action == "repeat":
        alert.repeat = not alert.repeat
    elif action == "cooldown":
        alert.cooldown_seconds = _next_option(COOLDOWN_OPTIONS, alert.cooldown_seconds)
    await session.commit()
    text, markup = alert_settings_view(alert)
    await _edit(callback.message, text, markup)
    await callback.answer()


@router.message(AlertEdit.waiting_value, ~F.text.startswith("/"))
async def edit_alert_value(message: Message, state: FSMContext, session: AsyncSession):
    if message.chat.type != "private" or not message.from_user:
        return
    user = await owned_user(session, message.from_user.id)
    if not user:
        return
    data = await state.get_data()
    alert = await _load_alert(session, user.id, data["alert_id"])
    if not alert:
        await state.clear()
        await message.answer("Alert no longer editable.")
        return
    text = (message.text or "").strip()
    if data["field"] == "threshold":
        try:
            value = Decimal(text.removesuffix("%"))
            if not value.is_finite() or value <= 0 or value >= Decimal("1e42") or value.as_tuple().exponent < -36:
                raise ValueError
        except (ValueError, InvalidOperation):
            await message.answer("Send a positive finite number with at most 36 decimal places.")
            return
        alert.threshold_value = value
        alert.armed = True
    else:
        if not text or len(text) > 300:
            await message.answer("Use 1 to 300 characters, or - to clear the note.")
            return
        alert.note = None if text == "-" else text
    await session.commit()
    await state.clear()
    view_text, markup = alert_settings_view(alert)
    await message.answer(view_text, reply_markup=markup, parse_mode="HTML")


def alert_settings_view(alert: Alert) -> tuple[str, InlineKeyboardMarkup]:
    asset = alert.asset
    is_percent = alert.type == AlertType.PERCENT_CHANGE.value
    lines = [
        f"⚙️ <b>{escape(describe_alert(alert))}</b>",
        f"Market: {escape(asset_kind_label(asset))}" if asset else None,
        "",
        f"Status: {'▶️ active' if alert.status == AlertStatus.ACTIVE.value else '⏸ paused'}",
        f"Mode: {'one time, removed after it fires' if not alert.repeat else 'repeats after the condition resets'}",
        f"Threshold: {format_threshold(alert.type, alert.threshold_value)}",
        f"Baseline: ${format_decimal(alert.baseline_price)}",
        f"Cooldown: {format_cooldown(alert.cooldown_seconds)}",
        *([f"Direction: {format_direction(alert.direction)}"] if is_percent else []),
        f"Expires: {alert.expires_at.strftime('%Y-%m-%d %H:%M UTC') if alert.expires_at else 'never'}",
        f"Note: {escape(alert.note) if alert.note else 'none'}",
    ]
    rows = [
        [("⏸ Pause" if alert.status == AlertStatus.ACTIVE.value else "▶️ Resume", f"alert_config:pause:{alert.id}")],
        [(one_time_label(not alert.repeat), f"alert_config:repeat:{alert.id}")],
        [(f"Cooldown: {format_cooldown(alert.cooldown_seconds)}", f"alert_config:cooldown:{alert.id}")],
    ]
    if is_percent:
        rows.append([(f"Direction: {format_direction_arrows(alert.direction)}", f"alert_config:direction:{alert.id}")])
    rows += [
        [("✏️ Threshold", f"alert_config:threshold:{alert.id}"), ("📝 Note", f"alert_config:note:{alert.id}")],
        [("⏳ Clear expiry" if alert.expires_at else "⏳ Expire in 7 days", f"alert_config:expiry:{alert.id}")],
        [("🗑 Delete", f"alert_config:delete:{alert.id}")],
        [("↩️ Back to alerts", "menu:alerts")],
    ]
    return "\n".join(line for line in lines if line is not None), keyboard(rows)


async def _load_alert(session: AsyncSession, user_id: int, alert_id: int) -> Alert | None:
    return await session.scalar(
        select(Alert)
        .where(Alert.id == alert_id, Alert.user_id == user_id, Alert.status.in_(EDITABLE_STATUSES))
        .options(selectinload(Alert.asset))
        .with_for_update(of=Alert)
    )


async def _edit(message: Message, text: str, markup: InlineKeyboardMarkup) -> None:
    try:
        await message.edit_text(text, reply_markup=markup, parse_mode="HTML", disable_web_page_preview=True)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            raise


def _value_prompt(alert: Alert, field: str) -> str:
    if field == "note":
        return "Send a note, up to 300 characters. Send - to clear it."
    if alert.type == AlertType.PERCENT_CHANGE.value:
        return f"Send a new threshold in %. Current: {format_threshold(alert.type, alert.threshold_value)}"
    if alert.type in {AlertType.MCAP_ABOVE.value, AlertType.MCAP_BELOW.value}:
        return f"Send a new market cap in USD. Current: {format_threshold(alert.type, alert.threshold_value)}"
    return f"Send a new price in USD. Current: {format_threshold(alert.type, alert.threshold_value)}"


def _confirm_delete_text(alert: Alert) -> str:
    return f"🗑 Delete <b>{escape(describe_alert(alert))}</b>?"


def _confirm_delete_keyboard(alert: Alert) -> InlineKeyboardMarkup:
    return keyboard(
        [
            [("✅ Yes, delete", f"alert_config:confirm_delete:{alert.id}")],
            [("↩️ Back", f"alert_config:view:{alert.id}")],
        ]
    )


def _next_option(options: list, current):
    if current not in options:
        return options[1] if len(options) > 1 else options[0]
    return options[(options.index(current) + 1) % len(options)]
