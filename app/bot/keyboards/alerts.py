from __future__ import annotations

from math import ceil

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.alerts.formatting import format_direction_arrows, format_percent, format_threshold
from app.db.enums import AlertStatus, AlertType
from app.db.models import Alert
from app.providers.base import AssetCandidate

ALERTS_PAGE_SIZE = 8


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
            _menu_button_row(),
        ]
    )


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[_menu_button_row()])


def wizard_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[_wizard_nav_row()])


def asset_candidates_keyboard(candidates: list[AssetCandidate], *, back_to_menu: bool = False) -> InlineKeyboardMarkup:
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
    rows.append(_menu_button_row() if back_to_menu else _wizard_nav_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def alert_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📈 Move % up/down", callback_data="alert_type:percent")],
            [InlineKeyboardButton(text="🚀 Breaks above", callback_data="alert_type:above")],
            [InlineKeyboardButton(text="🩸 Drops below", callback_data="alert_type:below")],
            [InlineKeyboardButton(text="Market cap above", callback_data="alert_type:mcap_above")],
            [InlineKeyboardButton(text="Market cap below", callback_data="alert_type:mcap_below")],
            _wizard_nav_row(),
        ]
    )


def threshold_keyboard(
    alert_type: str, *, one_time: bool = True, currency: str = "USD", native_symbol: str | None = None
) -> InlineKeyboardMarkup:
    rows = []
    if alert_type == "percent":
        rows.append([InlineKeyboardButton(text="Default (10.00%)", callback_data="threshold:default_percent")])
    if alert_type.startswith("mcap_"):
        rows.append([InlineKeyboardButton(text=one_time_label(one_time), callback_data="threshold:toggle_once")])
    if alert_type != "percent" and native_symbol:
        rows.append([InlineKeyboardButton(text=f"Currency: {currency}", callback_data="threshold:toggle_currency")])
    rows.append(_wizard_nav_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def alert_created_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Add another", callback_data="menu:newalert")],
            [InlineKeyboardButton(text="📌 Active alerts", callback_data="menu:alerts")],
            [InlineKeyboardButton(text="🏠 Menu", callback_data="wizard:cancel")],
        ]
    )


def alert_list_keyboard(alerts: list[Alert], *, page: int = 1, page_size: int = ALERTS_PAGE_SIZE) -> InlineKeyboardMarkup:
    total_pages = max(ceil(len(alerts) / page_size), 1)
    page = min(max(page, 1), total_pages)
    offset = (page - 1) * page_size
    rows = [
        [
            InlineKeyboardButton(
                text=alert_button_label(alert, offset + index + 1), callback_data=f"alert_config:view:{alert.id}"
            )
        ]
        for index, alert in enumerate(alerts[offset : offset + page_size])
    ]
    if total_pages > 1:
        rows.append(
            [
                InlineKeyboardButton(text="◀️", callback_data=f"alerts:page:{page - 1}" if page > 1 else "alerts:noop"),
                InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="alerts:noop"),
                InlineKeyboardButton(
                    text="▶️", callback_data=f"alerts:page:{page + 1}" if page < total_pages else "alerts:noop"
                ),
            ]
        )
    rows.append(_menu_button_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def alert_button_label(alert: Alert, index: int) -> str:
    symbol = alert.asset.symbol if alert.asset else "asset"
    currency = getattr(alert, "threshold_currency", None) or "USD"
    exact = format_threshold(alert.type, alert.threshold_value, currency)
    compact = format_threshold(alert.type, alert.threshold_value, currency, compact=True)
    if alert.type == AlertType.PERCENT_CHANGE.value:
        condition = f"{format_percent(alert.threshold_value)} {format_direction_arrows(alert.direction)}"
    elif alert.type == AlertType.PRICE_ABOVE.value:
        condition = f"> {exact}"
    elif alert.type == AlertType.PRICE_BELOW.value:
        condition = f"< {exact}"
    elif alert.type == AlertType.MCAP_ABOVE.value:
        condition = f"MC > {compact}"
    elif alert.type == AlertType.MCAP_BELOW.value:
        condition = f"MC < {compact}"
    else:
        condition = f"±{exact}"
    label = f"{index}. {symbol} {condition}"
    if alert.status == AlertStatus.PAUSED.value:
        label += " ⏸"
    return _truncate_button_text(label)


def one_time_label(one_time: bool) -> str:
    return f"One time: {'✅' if one_time else '❌'}"


def _menu_button_row() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text="↩️ Back to menu", callback_data="wizard:cancel")]


def _wizard_nav_row() -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton(text="↩️ Back", callback_data="wizard:back"),
        InlineKeyboardButton(text="🏠 Menu", callback_data="wizard:cancel"),
    ]


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
