from __future__ import annotations

from decimal import Decimal
from html import escape

from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.formatting import format_decimal, format_percent, format_threshold
from app.alerts.parser import ParsedAlertCommand
from app.alerts.service import alert_currency, asset_kind_label, create_alert_from_command
from app.bot.keyboards import alert_created_keyboard
from app.db import repositories as repo
from app.db.enums import AlertDirection, AlertType, AssetType
from app.i18n import t
from app.providers.base import AssetCandidate


async def create_alert_from_candidate(
    message: Message,
    session: AsyncSession,
    parsed: ParsedAlertCommand,
    candidate: AssetCandidate,
    *,
    edit_message: bool = False,
    edit_chat_id: int | None = None,
    edit_message_id: int | None = None,
    telegram_id: int | None = None,
    repeat: bool | None = None,
) -> None:
    if telegram_id is None and message.from_user is None:
        return

    resolved_telegram_id = telegram_id if telegram_id is not None else message.from_user.id
    user = await repo.get_user_by_telegram_id(session, resolved_telegram_id)
    if not repo.has_bot_access(user):
        await _send_result(
            message,
            t("access-pending"),
            edit_message=edit_message,
            edit_chat_id=edit_chat_id,
            edit_message_id=edit_message_id,
        )
        return

    asset = await repo.upsert_asset_from_candidate(session, candidate)
    try:
        alert = await create_alert_from_command(session, user_id=user.id, parsed=parsed, selected_asset=asset, repeat=repeat)
    except Exception as exc:
        await session.rollback()
        await _send_result(
            message,
            t("alert-create-failed", reason=str(exc)),
            edit_message=edit_message,
            edit_chat_id=edit_chat_id,
            edit_message_id=edit_message_id,
        )
        return

    await session.commit()
    await _send_result(
        message,
        t(
            "alert-created",
            symbol=escape(asset.symbol),
            condition=_format_condition(parsed, alert_currency(alert)),
            baseline=f"${format_decimal(alert.baseline_price)}",
            market=asset_kind_label(asset),
            mode=t("mode-repeat" if alert.repeat else "mode-one-time"),
        ),
        reply_markup=alert_created_keyboard(alert.id),
        parse_mode="HTML",
        edit_message=edit_message,
        edit_chat_id=edit_chat_id,
        edit_message_id=edit_message_id,
    )


async def ensure_access(message: Message, session: AsyncSession) -> bool:
    if message.from_user is None:
        return False

    user = await repo.get_user_by_telegram_id(session, message.from_user.id)
    if not repo.has_bot_access(user):
        await message.answer(t("access-denied-whitelist"))
        return False
    return True


async def ensure_admin(message: Message, session: AsyncSession) -> bool:
    if message.from_user is None:
        return False

    user = await repo.get_user_by_telegram_id(session, message.from_user.id)
    if not repo.is_admin(user):
        await message.answer(t("admin-required"))
        return False
    return True


def command_int_arg(message: Message) -> int | None:
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
        volume_usd=data.get("volume_usd") or 0.0,
    )


async def _send_result(
    message: Message,
    text: str,
    *,
    reply_markup=None,
    parse_mode: str | None = None,
    edit_message: bool,
    edit_chat_id: int | None,
    edit_message_id: int | None,
) -> None:
    if edit_chat_id is not None and edit_message_id is not None:
        await message.bot.edit_message_text(
            text=text,
            chat_id=edit_chat_id,
            message_id=edit_message_id,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
        return
    if edit_message:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        return
    await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)


def _format_condition(parsed: ParsedAlertCommand, currency: str) -> str:
    if parsed.alert_type == AlertType.PERCENT_CHANGE:
        return t("condition-percent", threshold=format_percent(parsed.threshold_value))
    key = {
        AlertType.PRICE_ABOVE: "condition-price-above",
        AlertType.PRICE_BELOW: "condition-price-below",
        AlertType.MCAP_ABOVE: "condition-mcap-above",
        AlertType.MCAP_BELOW: "condition-mcap-below",
    }.get(parsed.alert_type)
    if key is None:
        return t("condition-default")
    return t(key, threshold=format_threshold(parsed.alert_type.value, parsed.threshold_value, currency))
