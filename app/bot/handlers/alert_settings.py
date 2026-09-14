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

from app.alerts.formatting import format_decimal, format_direction, format_direction_arrows, format_threshold
from app.alerts.service import MOVE_ALERT_TYPES, alert_currency, asset_kind_label, describe_alert
from app.bot.handlers.alerts import alerts_message
from app.bot.handlers.settings import keyboard, owned_user
from app.bot.keyboards import one_time_label
from app.bot.states import AlertEdit
from app.db import repositories as repo
from app.db.enums import AlertStatus, AlertType
from app.db.models import Alert
from app.i18n import LocalizedError, t
from app.utils.amounts import parse_amount, resolve_currency
from app.utils.currency import native_symbol_or_none
from app.utils.durations import format_duration, parse_duration

router = Router(name="alert_settings")

DIRECTION_OPTIONS = ["both", "up", "down"]
EDITABLE_STATUSES = [AlertStatus.ACTIVE.value, AlertStatus.PAUSED.value]
INPUT_FIELDS = {"threshold", "note", "cooldown", "expiry"}
MIN_DURATION = timedelta(minutes=1)
MAX_COOLDOWN = timedelta(days=365)
MAX_EXPIRY = timedelta(days=5 * 365)


@router.callback_query(F.data.startswith("alert_config:"))
async def configure_alert(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    user = await owned_user(session, callback.from_user.id)
    if not user or not isinstance(callback.message, Message):
        await callback.answer(t("access-denied"))
        return
    if callback.message.chat.type != "private":
        await callback.answer(t("private-chat-required"), show_alert=True)
        return
    await state.clear()
    parts = callback.data.split(":")
    if len(parts) != 3 or not parts[2].isdigit():
        await callback.answer(t("invalid-alert"))
        return
    alert = await _load_alert(session, user.id, int(parts[2]))
    if not alert:
        await callback.answer(t("alert-not-found"))
        return
    action = parts[1]
    if action in INPUT_FIELDS:
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
        await callback.answer(t("alert-deleted-toast"))
        return
    if action == "direction" and alert.type == AlertType.PERCENT_CHANGE.value:
        alert.direction = _next_option(DIRECTION_OPTIONS, alert.direction)
    elif action == "pause":
        if alert.status == AlertStatus.PAUSED.value and alert.expires_at and alert.expires_at <= datetime.now(UTC):
            await callback.answer(t("clear-expiry-before-resume"), show_alert=True)
            return
        alert.status = AlertStatus.PAUSED.value if alert.status == AlertStatus.ACTIVE.value else AlertStatus.ACTIVE.value
    elif action == "repeat":
        alert.repeat = not alert.repeat
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
        await message.answer(t("alert-not-editable"))
        return
    text = (message.text or "").strip()
    if data["field"] == "threshold":
        try:
            if alert.type == AlertType.PERCENT_CHANGE.value:
                value, currency = Decimal(text.removesuffix("%").strip()), "USD"
            else:
                value, unit = parse_amount(text)
                currency = resolve_currency(unit, default=alert_currency(alert), native_symbol=_native_symbol(alert))
            if not value.is_finite() or value <= 0 or value >= Decimal("1e42") or value.as_tuple().exponent < -36:
                raise LocalizedError("error-threshold-format")
        except LocalizedError as exc:
            await message.answer(str(exc))
            return
        except (ValueError, InvalidOperation):
            await message.answer(t("error-threshold-format"))
            return
        alert.threshold_value = value
        alert.threshold_currency = currency
        alert.armed = True
    elif data["field"] == "cooldown":
        try:
            alert.cooldown_seconds = int(_parse_bounded_duration(text, MAX_COOLDOWN).total_seconds())
        except ValueError as exc:
            await message.answer(str(exc))
            return
    elif data["field"] == "expiry":
        if text == "-":
            alert.expires_at = None
        else:
            try:
                alert.expires_at = datetime.now(UTC) + _parse_bounded_duration(text, MAX_EXPIRY)
            except ValueError as exc:
                await message.answer(str(exc))
                return
    else:
        if not text or len(text) > 300:
            await message.answer(t("error-note-length"))
            return
        alert.note = None if text == "-" else text
    await session.commit()
    await state.clear()
    view_text, markup = alert_settings_view(alert)
    await message.answer(view_text, reply_markup=markup, parse_mode="HTML")


def _mode_label(alert: Alert) -> str:
    if not alert.repeat:
        return t("mode-one-time-removed")
    if alert.type in MOVE_ALERT_TYPES:
        return t("mode-repeat-rebase")
    return t("mode-repeat-reset")


def alert_settings_view(alert: Alert) -> tuple[str, InlineKeyboardMarkup]:
    asset = alert.asset
    is_percent = alert.type == AlertType.PERCENT_CHANGE.value
    active = alert.status == AlertStatus.ACTIVE.value
    lines = [
        f"⚙️ <b>{escape(describe_alert(alert))}</b>",
        t("field-market", value=escape(asset_kind_label(asset))) if asset else None,
        "",
        t("field-status", value=t("status-active" if active else "status-paused")),
        t("field-mode", value=_mode_label(alert)),
        t("field-threshold", value=format_threshold(alert.type, alert.threshold_value, alert_currency(alert))),
        t("field-baseline", value=f"${format_decimal(alert.baseline_price)}"),
        t("field-cooldown", value=format_duration(alert.cooldown_seconds)),
        t("field-direction", value=format_direction(alert.direction)) if is_percent else None,
        t("field-expires", value=_expiry_label(alert)),
        t("field-note", value=escape(alert.note) if alert.note else t("note-none")),
    ]
    rows = [
        [(t("button-pause" if active else "button-resume"), f"alert_config:pause:{alert.id}")],
        [(one_time_label(not alert.repeat), f"alert_config:repeat:{alert.id}")],
        [(t("button-cooldown", value=format_duration(alert.cooldown_seconds)), f"alert_config:cooldown:{alert.id}")],
    ]
    if is_percent:
        rows.append(
            [(t("button-direction", value=format_direction_arrows(alert.direction)), f"alert_config:direction:{alert.id}")]
        )
    rows += [
        [(t("button-threshold"), f"alert_config:threshold:{alert.id}"), (t("button-note"), f"alert_config:note:{alert.id}")],
        [(t("button-expires", value=_expiry_label(alert, compact=True)), f"alert_config:expiry:{alert.id}")],
        [(t("button-delete"), f"alert_config:delete:{alert.id}")],
        [(t("button-back-to-alerts"), "menu:alerts")],
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
        return t("prompt-note")
    if field == "cooldown":
        return t("prompt-cooldown", current=format_duration(alert.cooldown_seconds))
    if field == "expiry":
        return t("prompt-expiry", current=_expiry_label(alert))
    current = format_threshold(alert.type, alert.threshold_value, alert_currency(alert))
    if alert.type == AlertType.PERCENT_CHANGE.value:
        return t("prompt-threshold-percent", current=current)
    native_symbol = _native_symbol(alert)
    units = t("units-native", symbol=native_symbol) if native_symbol else t("units-usd")
    if alert.type in {AlertType.MCAP_ABOVE.value, AlertType.MCAP_BELOW.value}:
        return t("prompt-threshold-mcap", units=units, current=current)
    return t("prompt-threshold-price", units=units, current=current)


def _confirm_delete_text(alert: Alert) -> str:
    return t("confirm-delete", description=escape(describe_alert(alert)))


def _confirm_delete_keyboard(alert: Alert) -> InlineKeyboardMarkup:
    return keyboard(
        [
            [(t("button-confirm-delete"), f"alert_config:confirm_delete:{alert.id}")],
            [(t("button-back"), f"alert_config:view:{alert.id}")],
        ]
    )


def _native_symbol(alert: Alert) -> str | None:
    if alert.asset is None:
        return None
    return native_symbol_or_none((alert.asset.extra or {}).get("native_symbol"))


def _expiry_label(alert: Alert, *, compact: bool = False) -> str:
    if not alert.expires_at:
        return t("expiry-never")
    remaining = int((alert.expires_at - datetime.now(UTC)).total_seconds())
    if remaining <= 0:
        return t("expiry-expired")
    remaining = max(remaining - remaining % 60, 60)
    if compact:
        return t("expiry-in", duration=format_duration(remaining))
    return t("expiry-at", date=alert.expires_at.strftime("%Y-%m-%d %H:%M UTC"), duration=format_duration(remaining))


def _parse_bounded_duration(text: str, maximum: timedelta) -> timedelta:
    duration = parse_duration(text)
    if duration < MIN_DURATION:
        raise LocalizedError("error-duration-too-short")
    if duration > maximum:
        raise LocalizedError("error-duration-too-long", max=format_duration(int(maximum.total_seconds())))
    return duration


def _next_option(options: list, current):
    if current not in options:
        return options[1] if len(options) > 1 else options[0]
    return options[(options.index(current) + 1) % len(options)]
