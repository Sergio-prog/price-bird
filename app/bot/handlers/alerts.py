from __future__ import annotations

from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.parser import ParsedAlertCommand, parse_alert_command
from app.alerts.service import describe_alert
from app.bot.handlers.helpers import (
    candidate_from_dict,
    command_int_arg,
    create_alert_from_candidate,
    ensure_access,
    parsed_from_dict,
    parsed_to_dict,
)
from app.bot.keyboards import alert_list_keyboard, alert_type_keyboard, asset_candidates_keyboard, start_menu_keyboard
from app.bot.states import AlertWizard
from app.db import repositories as repo
from app.db.enums import AlertDirection, AlertType, AssetType
from app.providers.registry import provider_registry

router = Router(name="alerts")


@router.callback_query(F.data == "menu:newalert")
async def new_alert_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await _ensure_callback_access(callback, session):
        return
    await state.set_state(AlertWizard.waiting_query)
    if isinstance(callback.message, Message):
        await state.update_data(wizard_chat_id=callback.message.chat.id, wizard_message_id=callback.message.message_id)
        await callback.message.edit_text(
            "Send token ticker/name/contract or NFT collection name.",
            reply_markup=None,
        )
    await callback.answer()


@router.callback_query(F.data == "menu:alerts")
async def list_alerts_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _ensure_callback_access(callback, session):
        return
    if callback.from_user is None:
        await callback.answer()
        return

    alerts = list(await repo.active_alerts_for_user(session, callback.from_user.id))
    if isinstance(callback.message, Message):
        text, reply_markup = _alerts_message(alerts)
        await callback.message.edit_text(text, reply_markup=reply_markup)
    await callback.answer()


@router.callback_query(F.data == "menu:examples")
async def examples_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _ensure_callback_access(callback, session):
        return
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Examples:\n/alert BTC 10%\n/alert ETH above 4000\n/alert SOL below 120\n/newalert",
            reply_markup=start_menu_keyboard(),
        )
    await callback.answer()


@router.message(Command("alerts"))
async def list_alerts(message: Message, session: AsyncSession) -> None:
    if not await ensure_access(message, session):
        return
    if message.from_user is None:
        return

    alerts = list(await repo.active_alerts_for_user(session, message.from_user.id))
    text, reply_markup = _alerts_message(alerts)
    await message.answer(text, reply_markup=reply_markup)


@router.message(Command("deletealert"))
async def delete_alert(message: Message, session: AsyncSession) -> None:
    if not await ensure_access(message, session):
        return
    if message.from_user is None:
        return

    alert_id = command_int_arg(message)
    if alert_id is None:
        await message.answer("Usage: /deletealert 123")
        return

    deleted = await repo.delete_active_alert_for_user(session, telegram_id=message.from_user.id, alert_id=alert_id)
    await session.commit()
    if not deleted:
        await message.answer("Active alert not found.")
        return
    await message.answer(f"Deleted alert #{alert_id}.")


@router.message(Command("cancel"))
async def cancel_alert_wizard(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer("Nothing to cancel.")
        return
    await state.clear()
    await message.answer("Cancelled.")


@router.message(Command("newalert"))
async def new_alert(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await ensure_access(message, session):
        return
    await state.set_state(AlertWizard.waiting_query)
    prompt = await message.answer("Send token ticker/name/contract or NFT collection name. Use /cancel to stop.")
    await state.update_data(wizard_chat_id=prompt.chat.id, wizard_message_id=prompt.message_id)


@router.message(Command("alert"))
async def alert_shortcut(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await ensure_access(message, session):
        return
    try:
        parsed = parse_alert_command(message.text or "")
    except ValueError as exc:
        await message.answer(str(exc))
        return

    nft = parsed.asset_type_hint == AssetType.NFT_COLLECTION
    try:
        candidates = await provider_registry.search_assets(parsed.query, nft=nft)
    except Exception as exc:
        await message.answer(f"Asset provider failed: {exc}")
        return
    if not candidates:
        await message.answer("No matching asset found.")
        return
    if len(candidates) > 1:
        await state.update_data(parsed=parsed_to_dict(parsed), candidates=[candidate.__dict__ for candidate in candidates])
        await state.set_state(AlertWizard.waiting_asset)
        await message.answer("Select asset:", reply_markup=asset_candidates_keyboard(candidates))
        return

    await create_alert_from_candidate(message, session, parsed, candidates[0])


@router.message(AlertWizard.waiting_query)
async def wizard_query(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await ensure_access(message, session):
        return
    query = (message.text or "").strip()
    nft = "floor" in query.lower()
    query = query.replace("floor", "").strip()
    try:
        candidates = await provider_registry.search_assets(query, nft=nft)
    except Exception as exc:
        await _edit_wizard_message(message, state, f"Asset provider failed: {exc}")
        return
    if not candidates:
        await _edit_wizard_message(message, state, "No matching asset found.")
        return
    await state.update_data(candidates=[candidate.__dict__ for candidate in candidates])
    await state.set_state(AlertWizard.waiting_asset)
    await _edit_wizard_message(message, state, "Select asset:", reply_markup=asset_candidates_keyboard(candidates))


@router.callback_query(AlertWizard.waiting_asset, F.data.startswith("asset:"))
async def wizard_asset(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    index = int((callback.data or "").split(":", 1)[1])
    data = await state.get_data()
    raw_candidates = data["candidates"]
    candidate = candidate_from_dict(raw_candidates[index])
    await state.update_data(selected_candidate=candidate.__dict__)

    if data.get("parsed"):
        parsed = parsed_from_dict(data["parsed"])
        if isinstance(callback.message, Message) and callback.from_user is not None:
            await create_alert_from_candidate(
                callback.message,
                session,
                parsed,
                candidate,
                edit_message=True,
                telegram_id=callback.from_user.id,
            )
        await state.clear()
    else:
        await state.set_state(AlertWizard.waiting_type)
        if isinstance(callback.message, Message):
            await callback.message.edit_text("Choose alert type:", reply_markup=alert_type_keyboard())
    await callback.answer()


@router.callback_query(F.data == "wizard:cancel")
async def wizard_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text("Cancelled.", reply_markup=start_menu_keyboard())
    await callback.answer()


@router.callback_query(F.data.startswith("alert_delete:"))
async def delete_alert_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.from_user is None:
        await callback.answer()
        return

    alert_id = int((callback.data or "").split(":", 1)[1])
    deleted = await repo.delete_active_alert_for_user(session, telegram_id=callback.from_user.id, alert_id=alert_id)
    await session.commit()
    if isinstance(callback.message, Message):
        if deleted:
            alerts = list(await repo.active_alerts_for_user(session, callback.from_user.id))
            text, reply_markup = _alerts_message(alerts, prefix=f"Deleted alert #{alert_id}.\n\n")
            await callback.message.edit_text(text, reply_markup=reply_markup)
        else:
            await callback.message.edit_text("Active alert not found.", reply_markup=start_menu_keyboard())
    await callback.answer("Deleted" if deleted else "Not found")


@router.callback_query(AlertWizard.waiting_type, F.data.startswith("alert_type:"))
async def wizard_type(callback: CallbackQuery, state: FSMContext) -> None:
    value = (callback.data or "").split(":", 1)[1]
    await state.update_data(alert_type=value)
    await state.set_state(AlertWizard.waiting_threshold)
    if isinstance(callback.message, Message):
        if value == "percent":
            await callback.message.edit_text("Send percent threshold, for example: 10")
        else:
            await callback.message.edit_text("Send exact USD price.")
    await callback.answer()


@router.message(AlertWizard.waiting_threshold)
async def wizard_threshold(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    try:
        threshold = Decimal((message.text or "").strip().removesuffix("%"))
    except Exception:
        await message.answer("Send a valid positive number.")
        return
    if threshold <= 0:
        await message.answer("Send a valid positive number.")
        return

    alert_type = data["alert_type"]
    parsed = ParsedAlertCommand(
        query="",
        asset_type_hint=None,
        alert_type={
            "percent": AlertType.PERCENT_CHANGE,
            "above": AlertType.PRICE_ABOVE,
            "below": AlertType.PRICE_BELOW,
        }[alert_type],
        threshold_value=threshold,
        direction={
            "percent": AlertDirection.BOTH,
            "above": AlertDirection.UP,
            "below": AlertDirection.DOWN,
        }[alert_type],
    )
    candidate = candidate_from_dict(data["selected_candidate"])
    await create_alert_from_candidate(
        message,
        session,
        parsed,
        candidate,
        edit_chat_id=data.get("wizard_chat_id"),
        edit_message_id=data.get("wizard_message_id"),
    )
    await state.clear()


async def _ensure_callback_access(callback: CallbackQuery, session: AsyncSession) -> bool:
    if callback.from_user is None:
        await callback.answer()
        return False

    user = await repo.get_user_by_telegram_id(session, callback.from_user.id)
    if not repo.has_bot_access(user):
        await callback.answer("Access denied", show_alert=True)
        return False
    return True


def _alerts_message(alerts: list, *, prefix: str = "") -> tuple[str, object | None]:
    if not alerts:
        return f"{prefix}No active alerts. Use /alert BTC 10% or /newalert.", start_menu_keyboard()

    lines = [f"{prefix}Active alerts:"]
    for alert in alerts:
        lines.append(f"#{alert.id}: {describe_alert(alert)}")
    return "\n".join(lines), alert_list_keyboard(alerts)


async def _edit_wizard_message(message: Message, state: FSMContext, text: str, reply_markup: object | None = None) -> None:
    data = await state.get_data()
    chat_id = data.get("wizard_chat_id")
    message_id = data.get("wizard_message_id")
    if chat_id is None or message_id is None:
        sent = await message.answer(text, reply_markup=reply_markup)
        await state.update_data(wizard_chat_id=sent.chat.id, wizard_message_id=sent.message_id)
        return

    await message.bot.edit_message_text(text=text, chat_id=chat_id, message_id=message_id, reply_markup=reply_markup)
