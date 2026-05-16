from __future__ import annotations

import logging
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
from app.bot.keyboards import (
    alert_list_keyboard,
    alert_type_keyboard,
    asset_candidates_keyboard,
    asset_type_keyboard,
    back_to_menu_keyboard,
    start_menu_keyboard,
    threshold_keyboard,
)
from app.bot.messages import (
    asset_type_prompt,
    examples_message,
    no_matches_message,
    provider_failed_message,
    query_prompt,
    start_message,
    threshold_prompt,
)
from app.bot.states import AlertWizard
from app.db import repositories as repo
from app.db.enums import AlertDirection, AlertType, AssetType
from app.providers.registry import provider_registry

router = Router(name="alerts")
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "menu:newalert")
async def new_alert_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await _ensure_callback_access(callback, session):
        return
    await state.set_state(AlertWizard.waiting_asset_type)
    if isinstance(callback.message, Message):
        await state.update_data(wizard_chat_id=callback.message.chat.id, wizard_message_id=callback.message.message_id)
        await callback.message.edit_text(
            asset_type_prompt(),
            reply_markup=asset_type_keyboard(),
            parse_mode="HTML",
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
        await _show_examples_then_menu(callback.message, edit_previous=True)
    await callback.answer()


@router.message(Command("examples"))
async def examples_command(message: Message, session: AsyncSession) -> None:
    if not await ensure_access(message, session):
        return
    await _show_examples_then_menu(message, edit_previous=False)


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
    await _send_start_message(message)


@router.message(Command("newalert"))
async def new_alert(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await ensure_access(message, session):
        return
    await state.set_state(AlertWizard.waiting_asset_type)
    prompt = await message.answer(
        asset_type_prompt(),
        reply_markup=asset_type_keyboard(),
        parse_mode="HTML",
    )
    await state.update_data(wizard_chat_id=prompt.chat.id, wizard_message_id=prompt.message_id)


@router.callback_query(AlertWizard.waiting_asset_type, F.data.startswith("asset_type:"))
async def wizard_asset_type(callback: CallbackQuery, state: FSMContext) -> None:
    asset_type = (callback.data or "").split(":", 1)[1]
    nft = asset_type == "nft"
    await state.update_data(asset_nft=nft)
    await state.set_state(AlertWizard.waiting_query)
    if isinstance(callback.message, Message):
        await state.update_data(wizard_chat_id=callback.message.chat.id, wizard_message_id=callback.message.message_id)
        await callback.message.edit_text(
            query_prompt(nft=nft),
            reply_markup=back_to_menu_keyboard(),
            parse_mode="HTML",
        )
    await callback.answer()


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
    except Exception:
        logger.exception("Asset provider search failed; query=%s nft=%s shortcut=true", parsed.query, nft)
        await message.answer(provider_failed_message(nft=nft))
        return
    if not candidates:
        await message.answer(no_matches_message(nft=nft))
        return
    if len(candidates) > 1:
        await state.update_data(parsed=parsed_to_dict(parsed), candidates=[candidate.__dict__ for candidate in candidates])
        await state.set_state(AlertWizard.waiting_asset)
        await message.answer("Select the asset to watch:", reply_markup=asset_candidates_keyboard(candidates))
        return

    await create_alert_from_candidate(message, session, parsed, candidates[0])


@router.message(AlertWizard.waiting_query)
async def wizard_query(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await ensure_access(message, session):
        return
    data = await state.get_data()
    query = (message.text or "").strip()
    nft = bool(data.get("asset_nft"))
    if "floor" in query.lower():
        nft = True
        query = query.replace("floor", "").strip()
    try:
        candidates = await provider_registry.search_assets(query, nft=nft)
    except Exception:
        logger.exception("Asset provider search failed; query=%s nft=%s shortcut=false", query, nft)
        await _send_wizard_message(message, state, provider_failed_message(nft=nft), reply_markup=back_to_menu_keyboard())
        return
    if not candidates:
        await _send_wizard_message(message, state, no_matches_message(nft=nft), reply_markup=back_to_menu_keyboard())
        return
    await state.update_data(candidates=[candidate.__dict__ for candidate in candidates])
    await state.set_state(AlertWizard.waiting_asset)
    await _send_wizard_message(message, state, "Select the asset to watch:", reply_markup=asset_candidates_keyboard(candidates))


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
            await callback.message.edit_text("Choose when this alert should trigger:", reply_markup=alert_type_keyboard())
    await callback.answer()


@router.callback_query(F.data == "wizard:cancel")
async def wizard_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            start_message(callback.from_user.first_name, callback.from_user.username)
            if callback.from_user
            else start_message(None, None),
            reply_markup=start_menu_keyboard(),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
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
        data = await state.get_data()
        candidate = candidate_from_dict(data["selected_candidate"])
        await callback.message.edit_text(
            threshold_prompt(asset_label=_candidate_display(candidate), alert_type=value),
            reply_markup=threshold_keyboard(value),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(AlertWizard.waiting_threshold, F.data == "threshold:default_percent")
async def wizard_default_threshold(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    candidate = candidate_from_dict(data["selected_candidate"])
    parsed = _parsed_threshold("percent", Decimal("10"))
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
    await callback.answer()


@router.message(AlertWizard.waiting_threshold)
async def wizard_threshold(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    try:
        threshold = Decimal((message.text or "").strip().removesuffix("%"))
    except Exception:
        await message.answer("Send a valid positive number.", reply_markup=back_to_menu_keyboard())
        return
    if threshold <= 0:
        await message.answer("Send a valid positive number.", reply_markup=back_to_menu_keyboard())
        return

    parsed = _parsed_threshold(data["alert_type"], threshold)
    candidate = candidate_from_dict(data["selected_candidate"])
    await create_alert_from_candidate(
        message,
        session,
        parsed,
        candidate,
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


async def _send_wizard_message(message: Message, state: FSMContext, text: str, reply_markup: object | None = None) -> None:
    sent = await message.answer(text, reply_markup=reply_markup, parse_mode="HTML", disable_web_page_preview=True)
    await state.update_data(wizard_chat_id=sent.chat.id, wizard_message_id=sent.message_id)


async def _send_start_message(message: Message) -> None:
    if message.from_user is None:
        return
    await message.answer(
        start_message(message.from_user.first_name, message.from_user.username),
        reply_markup=start_menu_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


async def _show_examples_then_menu(message: Message, *, edit_previous: bool) -> None:
    if edit_previous:
        try:
            await message.edit_text(
                examples_message(),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception:
            await message.answer(
                examples_message(),
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
    else:
        try:
            await message.delete()
        except Exception:
            pass
        await message.answer(
            examples_message(),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

    if message.from_user is None:
        return
    await message.answer(
        start_message(message.from_user.first_name, message.from_user.username),
        reply_markup=start_menu_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


def _parsed_threshold(alert_type: str, threshold: Decimal) -> ParsedAlertCommand:
    return ParsedAlertCommand(
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


def _candidate_display(candidate) -> str:
    parts = [candidate.name or candidate.symbol]
    if candidate.chain:
        parts.append(candidate.chain)
    if price := candidate.metadata.get("price_usd"):
        parts.append(f"${price}")
    return " - ".join(parts)
