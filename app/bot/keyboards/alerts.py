from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.db.models import Alert
from app.providers.base import AssetCandidate


def start_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="New alert", callback_data="menu:newalert")],
            [InlineKeyboardButton(text="My alerts", callback_data="menu:alerts")],
            [InlineKeyboardButton(text="Examples", callback_data="menu:examples")],
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
    rows.append([InlineKeyboardButton(text="Cancel", callback_data="wizard:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def alert_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="+/- percent", callback_data="alert_type:percent")],
            [InlineKeyboardButton(text="Above price", callback_data="alert_type:above")],
            [InlineKeyboardButton(text="Below price", callback_data="alert_type:below")],
            [InlineKeyboardButton(text="Cancel", callback_data="wizard:cancel")],
        ]
    )


def alert_list_keyboard(alerts: list[Alert]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Delete #{alert.id}", callback_data=f"alert_delete:{alert.id}")] for alert in alerts
        ]
    )


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
