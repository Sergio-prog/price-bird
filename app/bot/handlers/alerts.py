from __future__ import annotations

import logging
from decimal import Decimal

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.parser import PERCENT_DIRECTIONS, ParsedAlertCommand, parse_alert_command, threshold_alert_type
from app.alerts.service import COOLDOWN_PRESETS, DEFAULT_COOLDOWN_SECONDS
from app.bot.handlers.helpers import (
    candidate_from_dict,
    candidate_heading,
    command_int_arg,
    create_alert_from_candidate,
    ensure_access,
    parsed_from_dict,
    parsed_to_dict,
    supports_market_cap,
)
from app.bot.keyboards import (
    alert_list_keyboard,
    alert_type_keyboard,
    asset_candidates_keyboard,
    asset_sources_keyboard,
    asset_type_keyboard,
    back_to_menu_keyboard,
    candidate_venues,
    start_menu_keyboard,
    threshold_keyboard,
    wizard_back_keyboard,
)
from app.bot.messages import (
    alert_type_prompt,
    alerts_list_message,
    asset_type_prompt,
    examples_message,
    no_alerts_message,
    no_matches_message,
    provider_failed_message,
    provider_misconfigured_message,
    query_prompt,
    start_message,
    threshold_prompt,
)
from app.bot.states import AlertWizard
from app.db import repositories as repo
from app.db.enums import AlertDirection, AlertType, AssetType
from app.i18n import LocalizedError, t
from app.providers.base import ProviderConfigurationError
from app.providers.registry import provider_registry
from app.utils.amounts import parse_amount, parse_percent, resolve_currency, split_market_cap_suffix
from app.utils.currency import native_symbol_or_none

router = Router(name="alerts")
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "menu:newalert")
async def new_alert_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await _ensure_callback_access(callback, session):
        return
    await state.clear()
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
    await _render_alerts_page(callback, session, page=1)


@router.callback_query(F.data.startswith("alerts:page:"))
async def alerts_page(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _ensure_callback_access(callback, session):
        return
    raw_page = (callback.data or "").rsplit(":", 1)[1]
    await _render_alerts_page(callback, session, page=int(raw_page) if raw_page.isdigit() else 1)


@router.callback_query(F.data == "alerts:noop")
async def alerts_noop(callback: CallbackQuery) -> None:
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
    text, reply_markup = alerts_message(alerts)
    await message.answer(text, reply_markup=reply_markup, parse_mode="HTML")


@router.message(Command("deletealert"))
async def delete_alert(message: Message, session: AsyncSession) -> None:
    if not await ensure_access(message, session):
        return
    if message.from_user is None:
        return

    alert_id = command_int_arg(message)
    if alert_id is None:
        await message.answer(t("delete-alert-usage"))
        return

    deleted = await repo.delete_active_alert_for_user(session, telegram_id=message.from_user.id, alert_id=alert_id)
    await session.commit()
    if not deleted:
        await message.answer(t("active-alert-not-found"))
        return
    await message.answer(t("alert-deleted", id=str(alert_id)))


@router.message(Command("cancel"))
async def cancel_alert_wizard(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        await message.answer(t("nothing-to-cancel"))
        return
    await state.clear()
    await _send_start_message(message)


@router.message(Command("newalert"))
async def new_alert(message: Message, state: FSMContext, session: AsyncSession) -> None:
    if not await ensure_access(message, session):
        return
    await state.clear()
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
            reply_markup=wizard_back_keyboard(),
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
    except ProviderConfigurationError:
        logger.exception("Asset provider is misconfigured; query=%s nft=%s shortcut=true", parsed.query, nft)
        await message.answer(provider_misconfigured_message(nft=nft))
        return
    except Exception:
        logger.exception("Asset provider search failed; query=%s nft=%s shortcut=true", parsed.query, nft)
        await message.answer(provider_failed_message(nft=nft))
        return
    if not candidates:
        await message.answer(no_matches_message(nft=nft))
        return
    if len(candidates) > 1:
        await state.clear()
        await state.update_data(parsed=parsed_to_dict(parsed), candidates=[candidate.__dict__ for candidate in candidates])
        await state.set_state(AlertWizard.waiting_asset)
        await message.answer(t("candidates-prompt"), reply_markup=asset_candidates_keyboard(candidates, back_to_menu=True))
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
    except ProviderConfigurationError:
        logger.exception("Asset provider is misconfigured; query=%s nft=%s shortcut=false", query, nft)
        await _send_wizard_message(message, state, provider_misconfigured_message(nft=nft), reply_markup=wizard_back_keyboard())
        return
    except Exception:
        logger.exception("Asset provider search failed; query=%s nft=%s shortcut=false", query, nft)
        await _send_wizard_message(message, state, provider_failed_message(nft=nft), reply_markup=wizard_back_keyboard())
        return
    if not candidates:
        await _send_wizard_message(message, state, no_matches_message(nft=nft), reply_markup=wizard_back_keyboard())
        return
    await state.update_data(candidates=[candidate.__dict__ for candidate in candidates], asset_venue=None)
    if len(candidates) == 1:
        await state.update_data(selected_candidate=candidates[0].__dict__)
        await state.set_state(AlertWizard.waiting_type)
        await _send_wizard_message(
            message, state, alert_type_prompt(candidate_heading(candidates[0])), reply_markup=alert_type_keyboard()
        )
        return
    await state.set_state(AlertWizard.waiting_asset)
    await _send_wizard_message(message, state, t("candidates-prompt"), reply_markup=asset_candidates_keyboard(candidates))


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
            await _edit_message(
                callback.message,
                alert_type_prompt(candidate_heading(candidate)),
                reply_markup=alert_type_keyboard(),
                parse_mode="HTML",
            )
    await callback.answer()


@router.callback_query(AlertWizard.waiting_asset, F.data.startswith("asset_source:"))
async def wizard_asset_source(callback: CallbackQuery, state: FSMContext) -> None:
    action = (callback.data or "").split(":", 1)[1]
    data = await state.get_data()
    if action == "menu":
        candidates = [candidate_from_dict(raw) for raw in data.get("candidates", [])]
        text, reply_markup = t("sources-prompt"), asset_sources_keyboard(candidates, venue=data.get("asset_venue"))
    else:
        if action != "back":
            data["asset_venue"] = _venue_for_action(data, action)
            await state.update_data(asset_venue=data["asset_venue"])
        text, reply_markup = t("candidates-prompt"), _candidates_keyboard(data)
    if isinstance(callback.message, Message):
        await _edit_message(callback.message, text, reply_markup=reply_markup)
    await callback.answer()


@router.callback_query(F.data == "wizard:cancel")
async def wizard_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(callback.message, Message):
        await _edit_message(
            callback.message,
            start_message(callback.from_user.first_name, callback.from_user.username)
            if callback.from_user
            else start_message(None, None),
            reply_markup=start_menu_keyboard(),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(AlertWizard.waiting_query, F.data == "wizard:back")
async def wizard_back_to_asset_type(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AlertWizard.waiting_asset_type)
    if isinstance(callback.message, Message):
        await _edit_message(callback.message, asset_type_prompt(), reply_markup=asset_type_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(AlertWizard.waiting_asset, F.data == "wizard:back")
async def wizard_back_to_query(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("parsed"):
        await wizard_cancel(callback, state)
        return
    await state.set_state(AlertWizard.waiting_query)
    if isinstance(callback.message, Message):
        await state.update_data(wizard_chat_id=callback.message.chat.id, wizard_message_id=callback.message.message_id)
        await _edit_message(
            callback.message,
            query_prompt(nft=bool(data.get("asset_nft"))),
            reply_markup=wizard_back_keyboard(),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(AlertWizard.waiting_type, F.data == "wizard:back")
async def wizard_back_to_candidates(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    if len(data.get("candidates", [])) == 1:
        await wizard_back_to_query(callback, state)
        return
    await state.set_state(AlertWizard.waiting_asset)
    if isinstance(callback.message, Message):
        await _edit_message(callback.message, t("candidates-prompt"), reply_markup=_candidates_keyboard(data))
    await callback.answer()


@router.callback_query(AlertWizard.waiting_threshold, F.data == "wizard:back")
async def wizard_back_to_type(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AlertWizard.waiting_type)
    if isinstance(callback.message, Message):
        candidate = candidate_from_dict((await state.get_data())["selected_candidate"])
        await _edit_message(
            callback.message,
            alert_type_prompt(candidate_heading(candidate)),
            reply_markup=alert_type_keyboard(),
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(AlertWizard.waiting_type, F.data.startswith("alert_type:"))
async def wizard_type(callback: CallbackQuery, state: FSMContext) -> None:
    value = (callback.data or "").split(":", 1)[1]
    data = await state.get_data()
    candidate = candidate_from_dict(data["selected_candidate"])
    native_symbol = native_symbol_or_none(candidate.metadata.get("native_symbol"))
    currency = native_symbol if native_symbol and candidate.type == AssetType.NFT_COLLECTION else "USD"
    await state.update_data(
        alert_type=value,
        one_time=value != "percent",
        currency=currency,
        native_symbol=native_symbol,
        metric="price",
        supports_market_cap=supports_market_cap(candidate),
        direction=AlertDirection.BOTH.value,
        cooldown_seconds=DEFAULT_COOLDOWN_SECONDS,
    )
    await state.set_state(AlertWizard.waiting_threshold)
    if isinstance(callback.message, Message):
        await _render_threshold_step(callback.message, await state.get_data())
    await callback.answer()


@router.callback_query(AlertWizard.waiting_threshold, F.data == "threshold:toggle_once")
async def wizard_toggle_once(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.update_data(one_time=not data.get("one_time", True))
    if isinstance(callback.message, Message):
        await _edit_reply_markup(callback.message, _threshold_keyboard(await state.get_data()))
    await callback.answer()


@router.callback_query(AlertWizard.waiting_threshold, F.data.startswith("threshold:direction:"))
async def wizard_direction(callback: CallbackQuery, state: FSMContext) -> None:
    direction = (callback.data or "").rsplit(":", 1)[1]
    if direction in {item.value for item in AlertDirection}:
        await state.update_data(direction=direction)
    if isinstance(callback.message, Message):
        await _edit_reply_markup(callback.message, _threshold_keyboard(await state.get_data()))
    await callback.answer()


@router.callback_query(AlertWizard.waiting_threshold, F.data.startswith("threshold:metric:"))
async def wizard_metric(callback: CallbackQuery, state: FSMContext) -> None:
    metric = (callback.data or "").rsplit(":", 1)[1]
    if metric in {"price", "mcap"}:
        await state.update_data(metric=metric)
    if isinstance(callback.message, Message):
        await _render_threshold_step(callback.message, await state.get_data())
    await callback.answer()


@router.callback_query(AlertWizard.waiting_threshold, F.data == "threshold:cooldown")
async def wizard_cooldown(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    current = data.get("cooldown_seconds", DEFAULT_COOLDOWN_SECONDS)
    following = [preset for preset in COOLDOWN_PRESETS if preset > current]
    await state.update_data(cooldown_seconds=following[0] if following else COOLDOWN_PRESETS[0])
    if isinstance(callback.message, Message):
        await _edit_reply_markup(callback.message, _threshold_keyboard(await state.get_data()))
    await callback.answer()


@router.callback_query(AlertWizard.waiting_threshold, F.data == "threshold:toggle_currency")
async def wizard_toggle_currency(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    native_symbol = data.get("native_symbol")
    if not native_symbol:
        await callback.answer(t("usd-only"))
        return
    await state.update_data(currency=native_symbol if data.get("currency", "USD") == "USD" else "USD")
    if isinstance(callback.message, Message):
        await _render_threshold_step(callback.message, await state.get_data())
    await callback.answer()


@router.callback_query(AlertWizard.waiting_threshold, F.data == "threshold:default_percent")
async def wizard_default_threshold(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    candidate = candidate_from_dict(data["selected_candidate"])
    parsed = _parsed_threshold(data, Decimal("10"))
    if isinstance(callback.message, Message) and callback.from_user is not None:
        await create_alert_from_candidate(
            callback.message,
            session,
            parsed,
            candidate,
            edit_message=True,
            telegram_id=callback.from_user.id,
            repeat=not data.get("one_time", False),
            cooldown_seconds=data.get("cooldown_seconds"),
        )
    await state.clear()
    await callback.answer()


@router.message(AlertWizard.waiting_threshold)
async def wizard_threshold(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    text = (message.text or "").strip()
    try:
        if data["alert_type"] == "percent":
            threshold, sign = parse_percent(text)
            currency = "USD"
            if sign:
                data["direction"] = PERCENT_DIRECTIONS[sign].value
        else:
            amount, market_cap = split_market_cap_suffix(text)
            if market_cap:
                data["metric"] = "mcap"
            threshold, unit = parse_amount(amount)
            currency = resolve_currency(unit, default=data.get("currency", "USD"), native_symbol=data.get("native_symbol"))
        if not threshold.is_finite() or threshold <= 0 or threshold >= Decimal("1e42"):
            raise LocalizedError("error-positive-number")
    except LocalizedError as exc:
        await message.answer(str(exc), reply_markup=wizard_back_keyboard())
        return
    except Exception:
        await message.answer(t("error-positive-number"), reply_markup=wizard_back_keyboard())
        return

    parsed = _parsed_threshold(data, threshold, currency)
    candidate = candidate_from_dict(data["selected_candidate"])
    await create_alert_from_candidate(
        message,
        session,
        parsed,
        candidate,
        repeat=not data.get("one_time", data["alert_type"] != "percent"),
        cooldown_seconds=data.get("cooldown_seconds"),
    )
    await state.clear()


async def _render_threshold_step(message: Message, data: dict) -> None:
    candidate = candidate_from_dict(data["selected_candidate"])
    await _edit_message(
        message,
        threshold_prompt(
            asset=candidate_heading(candidate),
            alert_type=data["alert_type"],
            metric=data.get("metric", "price"),
            currency=data.get("currency", "USD"),
            native_symbol=data.get("native_symbol"),
            supports_market_cap=data.get("supports_market_cap", False),
        ),
        reply_markup=_threshold_keyboard(data),
        parse_mode="HTML",
    )


def _candidates_keyboard(data: dict) -> InlineKeyboardMarkup:
    return asset_candidates_keyboard(
        [candidate_from_dict(raw) for raw in data.get("candidates", [])],
        venue=data.get("asset_venue"),
        back_to_menu=bool(data.get("parsed")),
    )


def _venue_for_action(data: dict, action: str) -> str | None:
    venues = candidate_venues([candidate_from_dict(raw) for raw in data.get("candidates", [])])
    if action.isdigit() and int(action) < len(venues):
        return venues[int(action)]
    return None


def _threshold_keyboard(data: dict) -> InlineKeyboardMarkup:
    one_time = data.get("one_time", True)
    return threshold_keyboard(
        data["alert_type"],
        one_time=one_time,
        currency=data.get("currency", "USD"),
        native_symbol=data.get("native_symbol"),
        metric=data.get("metric", "price"),
        supports_market_cap=data.get("supports_market_cap", False),
        direction=data.get("direction", AlertDirection.BOTH.value),
        cooldown_seconds=None if one_time else data.get("cooldown_seconds", DEFAULT_COOLDOWN_SECONDS),
    )


def alerts_message(alerts: list, *, page: int = 1) -> tuple[str, InlineKeyboardMarkup]:
    if not alerts:
        return no_alerts_message(), back_to_menu_keyboard()
    return alerts_list_message(len(alerts)), alert_list_keyboard(alerts, page=page)


async def _render_alerts_page(callback: CallbackQuery, session: AsyncSession, *, page: int) -> None:
    if callback.from_user is None or not isinstance(callback.message, Message):
        await callback.answer()
        return
    alerts = list(await repo.active_alerts_for_user(session, callback.from_user.id))
    text, reply_markup = alerts_message(alerts, page=page)
    await _edit_message(callback.message, text, reply_markup=reply_markup, parse_mode="HTML")
    await callback.answer()


async def _edit_message(
    message: Message, text: str, *, reply_markup: InlineKeyboardMarkup | None = None, parse_mode: str | None = None
) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=True)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            raise


async def _edit_reply_markup(message: Message, reply_markup: InlineKeyboardMarkup) -> None:
    try:
        await message.edit_reply_markup(reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            raise


async def _ensure_callback_access(callback: CallbackQuery, session: AsyncSession) -> bool:
    if callback.from_user is None:
        await callback.answer()
        return False

    user = await repo.get_user_by_telegram_id(session, callback.from_user.id)
    if not repo.has_bot_access(user):
        await callback.answer(t("access-denied"), show_alert=True)
        return False
    return True


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


def _parsed_threshold(data: dict, threshold: Decimal, currency: str = "USD") -> ParsedAlertCommand:
    if data["alert_type"] == "percent":
        alert_type = AlertType.PERCENT_CHANGE
        direction = AlertDirection(data.get("direction", AlertDirection.BOTH.value))
    else:
        above = data["alert_type"] == "above"
        alert_type = threshold_alert_type(above=above, market_cap=data.get("metric") == "mcap")
        direction = AlertDirection.UP if above else AlertDirection.DOWN
    return ParsedAlertCommand(
        query="",
        asset_type_hint=None,
        threshold_currency=currency,
        alert_type=alert_type,
        threshold_value=threshold,
        direction=direction,
    )
