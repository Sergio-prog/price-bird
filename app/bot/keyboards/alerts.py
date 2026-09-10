from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.db.models import Alert
from app.providers.base import AssetCandidate


def start_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔔 New alert", callback_data="menu:newalert")],
            [InlineKeyboardButton(text="📌 Active alerts", callback_data="menu:alerts")],
            [InlineKeyboardButton(text="📚 Examples", callback_data="menu:examples")],
            [InlineKeyboardButton(text="Settings / connected apps", callback_data="settings:open")],
        ]
    )


def asset_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🪙 Coins / CEX", callback_data="asset_type:token")],
            [InlineKeyboardButton(text="🖼 NFT floor", callback_data="asset_type:nft")],
            [InlineKeyboardButton(text="↩ Back to menu", callback_data="wizard:cancel")],
        ]
    )


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="↩ Back to menu", callback_data="wizard:cancel")],
        ]
    )


def asset_candidates_keyboard(candidates: list[AssetCandidate]) -> InlineKeyboardMarkup:
    rows = []
    for index, candidate in enumerate(candidates[:10]):
        rows.append(
            [
                InlineKeyboardButton(
                    text=_asset_candidate_label(candidate),
                    callback_data=f"asset:{index}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="↩ Back to menu", callback_data="wizard:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def alert_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📈 Move % up/down", callback_data="alert_type:percent")],
            [InlineKeyboardButton(text="🚀 Breaks above", callback_data="alert_type:above")],
            [InlineKeyboardButton(text="🩸 Drops below", callback_data="alert_type:below")],
            [InlineKeyboardButton(text="Market cap above", callback_data="alert_type:mcap_above")],
            [InlineKeyboardButton(text="Market cap below", callback_data="alert_type:mcap_below")],
            [InlineKeyboardButton(text="↩ Back to menu", callback_data="wizard:cancel")],
        ]
    )


def threshold_keyboard(alert_type: str) -> InlineKeyboardMarkup:
    rows = []
    if alert_type == "percent":
        rows.append([InlineKeyboardButton(text="Default (10.00%)", callback_data="threshold:default_percent")])
    rows.append([InlineKeyboardButton(text="↩ Back to menu", callback_data="wizard:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def alert_created_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add another", callback_data="menu:newalert")],
            [InlineKeyboardButton(text="📌 Active alerts", callback_data="menu:alerts")],
            [InlineKeyboardButton(text="🏠 Menu", callback_data="wizard:cancel")],
        ]
    )


def alert_list_keyboard(alerts: list[Alert]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text=f"Settings #{alert.id}", callback_data=f"alert_config:view:{alert.id}"),
            InlineKeyboardButton(text=f"Delete #{alert.id}", callback_data=f"alert_delete:{alert.id}"),
        ]
        for alert in alerts
    ]
    rows.append([InlineKeyboardButton(text="↩ Back to menu", callback_data="wizard:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _asset_candidate_label(candidate: AssetCandidate) -> str:
    parts = [candidate.symbol]
    if candidate.chain:
        parts.append(candidate.chain)
    if pair := candidate.metadata.get("pair"):
        parts.append(str(pair))
    if price := candidate.metadata.get("price_usd"):
        parts.append(f"${price}")
    parts.append(candidate.provider)
    return _truncate_button_text(" / ".join(parts))


def _truncate_button_text(text: str, limit: int = 64) -> str:
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."
