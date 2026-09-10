from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.settings import ConnectionWizard, keyboard, owned_user
from app.db.models import Alert

router = Router(name="alert_settings")


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
    alert = await session.scalar(
        select(Alert)
        .where(Alert.id == int(parts[2]), Alert.user_id == user.id, Alert.status.in_(["active", "paused"]))
        .with_for_update()
    )
    if not alert:
        await callback.answer("Alert not found")
        return
    action = parts[1]
    if action in {"threshold", "note"}:
        await state.set_state(ConnectionWizard.alert_value)
        await state.update_data(alert_id=alert.id, field=action)
        await callback.message.answer(
            "Send a positive threshold." if action == "threshold" else "Send a note, up to 300 characters. Send - to clear it."
        )
        await callback.answer()
        return
    if action == "direction" and alert.type == "percent_change":
        values = ["both", "up", "down"]
        alert.direction = values[(values.index(alert.direction) + 1) % len(values)]
    elif action == "expiry":
        alert.expires_at = None if alert.expires_at else datetime.now(UTC) + timedelta(days=7)
    elif action == "pause":
        if alert.status == "paused" and alert.expires_at and alert.expires_at <= datetime.now(UTC):
            await callback.answer("Clear the expiry before resuming", show_alert=True)
            return
        alert.status = "paused" if alert.status == "active" else "active"
    elif action == "repeat":
        alert.repeat = not alert.repeat
    elif action == "cooldown":
        values = [60, 900, 3600, 86400]
        alert.cooldown_seconds = (
            values[(values.index(alert.cooldown_seconds) + 1) % len(values)] if alert.cooldown_seconds in values else 900
        )
    await session.commit()
    await callback.message.answer(
        f"Alert #{alert.id}: {alert.status}\nFrequency: {'repeating crossings' if alert.repeat else 'once'}\n"
        f"Cooldown: {alert.cooldown_seconds // 60} min\nThreshold: {alert.threshold_value}\n"
        f"Direction: {alert.direction}\nExpiry: {alert.expires_at or 'none'}\nNote: {alert.note or 'none'}\n"
        "Repeating alerts rearm after the condition stops being true.",
        reply_markup=keyboard(
            [
                [("Pause" if alert.status == "active" else "Resume", f"alert_config:pause:{alert.id}")],
                [("Toggle once / repeat", f"alert_config:repeat:{alert.id}")],
                [("Change cooldown", f"alert_config:cooldown:{alert.id}")],
                *([[("Change direction", f"alert_config:direction:{alert.id}")]] if alert.type == "percent_change" else []),
                [("Edit threshold", f"alert_config:threshold:{alert.id}"), ("Edit note", f"alert_config:note:{alert.id}")],
                [("Clear expiry" if alert.expires_at else "Expire in 7 days", f"alert_config:expiry:{alert.id}")],
                [("Back", "menu:alerts")],
            ]
        ),
    )
    await callback.answer()


@router.message(ConnectionWizard.alert_value, ~F.text.startswith("/"))
async def edit_alert_value(message: Message, state: FSMContext, session: AsyncSession):
    if message.chat.type != "private" or not message.from_user:
        return
    user = await owned_user(session, message.from_user.id)
    if not user:
        return
    data = await state.get_data()
    alert = await session.scalar(
        select(Alert)
        .where(Alert.id == data["alert_id"], Alert.user_id == user.id, Alert.status.in_(["active", "paused"]))
        .with_for_update()
    )
    if not alert:
        await state.clear()
        await message.answer("Alert no longer editable.")
        return
    text = (message.text or "").strip()
    if data["field"] == "threshold":
        try:
            value = Decimal(text)
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
    await message.answer("Alert updated.", reply_markup=keyboard([[("Alert settings", f"alert_config:view:{alert.id}")]]))
