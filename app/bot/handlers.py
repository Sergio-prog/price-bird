from __future__ import annotations

from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.alerts.parser import ParsedAlertCommand, parse_alert_command
from app.alerts.service import asset_kind_label, create_alert_from_command
from app.bot.keyboards import alert_type_keyboard, asset_candidates_keyboard
from app.bot.states import AlertWizard
from app.db import repositories as repo
from app.db.enums import AccessStatus, AlertDirection, AlertType, AssetType, UserRole
from app.db.session import SessionLocal
from app.providers.base import AssetCandidate
from app.providers.registry import provider_registry

router = Router()


@router.message(CommandStart())
async def start(message: Message) -> None:
    tg_user = message.from_user
    if tg_user is None:
        return
    async with SessionLocal() as session:
        user = await repo.upsert_telegram_user(
            session,
            telegram_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
            language_code=tg_user.language_code,
        )
        await session.commit()

    if repo.has_bot_access(user):
        await message.answer("Access active. Use /alert BTC 10% or /newalert.")
    else:
        await message.answer("Access pending. Ask an admin to whitelist your Telegram ID.")


@router.message(Command("newalert"))
async def new_alert(message: Message, state: FSMContext) -> None:
    if not await _ensure_access(message):
        return
    await state.set_state(AlertWizard.waiting_query)
    await message.answer("Send token ticker/name/contract or NFT collection name.")


@router.message(Command("alert"))
async def alert_shortcut(message: Message, state: FSMContext) -> None:
    if not await _ensure_access(message):
        return
    try:
        parsed = parse_alert_command(message.text or "")
    except ValueError as exc:
        await message.answer(str(exc))
        return

    nft = parsed.asset_type_hint == AssetType.NFT_COLLECTION
    candidates = await provider_registry.search_assets(parsed.query, nft=nft)
    if not candidates:
        await message.answer("No matching asset found.")
        return
    if len(candidates) > 1:
        await state.update_data(parsed=parsed_to_dict(parsed), candidates=[candidate.__dict__ for candidate in candidates])
        await state.set_state(AlertWizard.waiting_asset)
        await message.answer("Select asset:", reply_markup=asset_candidates_keyboard(candidates))
        return

    await _create_alert_from_candidate(message, parsed, candidates[0])


@router.message(AlertWizard.waiting_query)
async def wizard_query(message: Message, state: FSMContext) -> None:
    if not await _ensure_access(message):
        return
    query = (message.text or "").strip()
    nft = "floor" in query.lower()
    query = query.replace("floor", "").strip()
    candidates = await provider_registry.search_assets(query, nft=nft)
    if not candidates:
        await message.answer("No matching asset found.")
        return
    await state.update_data(candidates=[candidate.__dict__ for candidate in candidates])
    await state.set_state(AlertWizard.waiting_asset)
    await message.answer("Select asset:", reply_markup=asset_candidates_keyboard(candidates))


@router.callback_query(AlertWizard.waiting_asset, F.data.startswith("asset:"))
async def wizard_asset(callback: CallbackQuery, state: FSMContext) -> None:
    index = int((callback.data or "").split(":", 1)[1])
    data = await state.get_data()
    raw_candidates = data["candidates"]
    candidate = candidate_from_dict(raw_candidates[index])
    await state.update_data(selected_candidate=candidate.__dict__)

    if data.get("parsed"):
        parsed = parsed_from_dict(data["parsed"])
        await _create_alert_from_candidate(callback.message, parsed, candidate)
        await state.clear()
    else:
        await state.set_state(AlertWizard.waiting_type)
        await callback.message.answer("Choose alert type:", reply_markup=alert_type_keyboard())
    await callback.answer()


@router.callback_query(AlertWizard.waiting_type, F.data.startswith("alert_type:"))
async def wizard_type(callback: CallbackQuery, state: FSMContext) -> None:
    value = (callback.data or "").split(":", 1)[1]
    await state.update_data(alert_type=value)
    await state.set_state(AlertWizard.waiting_threshold)
    if value == "percent":
        await callback.message.answer("Send percent threshold, for example: 10")
    else:
        await callback.message.answer("Send exact USD price.")
    await callback.answer()


@router.message(AlertWizard.waiting_threshold)
async def wizard_threshold(message: Message, state: FSMContext) -> None:
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
    await _create_alert_from_candidate(message, parsed, candidate)
    await state.clear()


@router.message(Command("whitelist"))
async def whitelist(message: Message) -> None:
    if not await _ensure_admin(message):
        return
    telegram_id = _command_int_arg(message)
    if telegram_id is None:
        await message.answer("Usage: /whitelist 123456789")
        return
    async with SessionLocal() as session:
        await repo.set_user_access(session, telegram_id=telegram_id, access_status=AccessStatus.ACTIVE)
        await session.commit()
    await message.answer(f"Whitelisted {telegram_id}.")


@router.message(Command("suspend"))
async def suspend(message: Message) -> None:
    if not await _ensure_admin(message):
        return
    telegram_id = _command_int_arg(message)
    if telegram_id is None:
        await message.answer("Usage: /suspend 123456789")
        return
    async with SessionLocal() as session:
        await repo.set_user_access(session, telegram_id=telegram_id, access_status=AccessStatus.SUSPENDED)
        await session.commit()
    await message.answer(f"Suspended {telegram_id}.")


@router.message(Command("promote"))
async def promote(message: Message) -> None:
    if not await _ensure_admin(message):
        return
    telegram_id = _command_int_arg(message)
    if telegram_id is None:
        await message.answer("Usage: /promote 123456789")
        return
    async with SessionLocal() as session:
        await repo.set_user_access(
            session,
            telegram_id=telegram_id,
            access_status=AccessStatus.ACTIVE,
            role=UserRole.ADMIN,
        )
        await session.commit()
    await message.answer(f"Promoted {telegram_id}.")


@router.message(Command("users"))
async def users(message: Message) -> None:
    if not await _ensure_admin(message):
        return
    async with SessionLocal() as session:
        rows = await repo.list_users(session)
    text = "\n".join(f"{u.telegram_id} @{u.username or '-'} {u.role}/{u.access_status}" for u in rows)
    await message.answer(text or "No users.")


@router.message(Command("stats"))
async def stats(message: Message) -> None:
    if not await _ensure_admin(message):
        return
    async with SessionLocal() as session:
        data = await repo.get_stats(session)
    await message.answer(
        f"Users: {data['users']}\nActive alerts: {data['active_alerts']}\nWatched assets: {data['watched_assets']}"
    )


async def _create_alert_from_candidate(message: Message, parsed: ParsedAlertCommand, candidate: AssetCandidate) -> None:
    if message.from_user is None:
        return
    async with SessionLocal() as session:
        user = await repo.get_user_by_telegram_id(session, message.from_user.id)
        if not repo.has_bot_access(user):
            await message.answer("Access pending.")
            return
        asset = await repo.upsert_asset_from_candidate(session, candidate)
        try:
            alert = await create_alert_from_command(session, user_id=user.id, parsed=parsed, selected_asset=asset)
        except Exception as exc:
            await session.rollback()
            await message.answer(f"Could not create alert: {exc}")
            return
        await session.commit()
    await message.answer(
        f"Alert created: {asset.symbol} ({asset_kind_label(asset)}) at baseline ${alert.baseline_price.normalize()}."
    )


async def _ensure_access(message: Message) -> bool:
    if message.from_user is None:
        return False
    async with SessionLocal() as session:
        user = await repo.get_user_by_telegram_id(session, message.from_user.id)
    if not repo.has_bot_access(user):
        await message.answer("Access denied. Ask an admin to whitelist your Telegram ID.")
        return False
    return True


async def _ensure_admin(message: Message) -> bool:
    if message.from_user is None:
        return False
    async with SessionLocal() as session:
        user = await repo.get_user_by_telegram_id(session, message.from_user.id)
    if not repo.is_admin(user):
        await message.answer("Admin access required.")
        return False
    return True


def _command_int_arg(message: Message) -> int | None:
    parts = (message.text or "").split()
    if len(parts) != 2:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def parsed_to_dict(parsed: ParsedAlertCommand) -> dict:
    return {
        "query": parsed.query,
        "asset_type_hint": parsed.asset_type_hint.value if parsed.asset_type_hint else None,
        "alert_type": parsed.alert_type.value,
        "threshold_value": str(parsed.threshold_value),
        "direction": parsed.direction.value,
    }


def parsed_from_dict(data: dict) -> ParsedAlertCommand:
    return ParsedAlertCommand(
        query=data["query"],
        asset_type_hint=AssetType(data["asset_type_hint"]) if data.get("asset_type_hint") else None,
        alert_type=AlertType(data["alert_type"]),
        threshold_value=Decimal(data["threshold_value"]),
        direction=AlertDirection(data["direction"]),
    )


def candidate_from_dict(data: dict) -> AssetCandidate:
    return AssetCandidate(
        type=AssetType(data["type"]),
        provider=data["provider"],
        provider_asset_id=data["provider_asset_id"],
        symbol=data["symbol"],
        name=data.get("name"),
        chain=data.get("chain"),
        contract_address=data.get("contract_address"),
        metadata=data.get("metadata") or {},
        links=data.get("links") or {},
    )
