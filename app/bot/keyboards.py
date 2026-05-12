from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.providers.base import AssetCandidate


def asset_candidates_keyboard(candidates: list[AssetCandidate]) -> InlineKeyboardMarkup:
    rows = []
    for index, candidate in enumerate(candidates[:10]):
        chain = f" / {candidate.chain}" if candidate.chain else ""
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{candidate.symbol}{chain} ({candidate.provider})",
                    callback_data=f"asset:{index}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def alert_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="+/- percent", callback_data="alert_type:percent")],
            [InlineKeyboardButton(text="Above price", callback_data="alert_type:above")],
            [InlineKeyboardButton(text="Below price", callback_data="alert_type:below")],
        ]
    )
