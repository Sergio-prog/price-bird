from __future__ import annotations

from math import ceil

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.alerts.formatting import format_direction_arrows, format_percent, format_threshold, venue_label
from app.db.enums import AlertStatus, AlertType, AssetType
from app.db.models import Alert
from app.i18n import t
from app.providers.base import AssetCandidate
from app.utils.durations import format_duration

ALERTS_PAGE_SIZE = 8
CANDIDATES_LIMIT = 6
FILTERED_CANDIDATES_LIMIT = 8
SOURCES_PER_ROW = 2
PERCENT_DIRECTIONS = ("both", "up", "down")
METRICS = ("price", "mcap")


def start_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("menu-new-alert"), callback_data="menu:newalert", style="success")],
            [InlineKeyboardButton(text=t("menu-active-alerts"), callback_data="menu:alerts")],
            [InlineKeyboardButton(text=t("menu-examples"), callback_data="menu:examples")],
            [InlineKeyboardButton(text=t("menu-settings"), callback_data="settings:open")],
        ]
    )


def asset_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("asset-type-token"), callback_data="asset_type:token")],
            [InlineKeyboardButton(text=t("asset-type-nft"), callback_data="asset_type:nft")],
            _menu_button_row(),
        ]
    )


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[_menu_button_row()])


def wizard_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[_wizard_nav_row()])


def asset_candidates_keyboard(
    candidates: list[AssetCandidate], *, venue: str | None = None, back_to_menu: bool = False
) -> InlineKeyboardMarkup:
    shown = [(index, candidate) for index, candidate in enumerate(candidates) if venue in {None, candidate.venue}]
    shown = shown[: FILTERED_CANDIDATES_LIMIT if venue else CANDIDATES_LIMIT]
    ambiguous = _ambiguous_labels([candidate for _, candidate in shown])
    rows = [
        [
            InlineKeyboardButton(
                text=_asset_candidate_label(candidate, with_address=_label_key(candidate) in ambiguous),
                callback_data=f"asset:{index}",
            )
        ]
        for index, candidate in shown
    ]
    if len(candidate_venues(candidates)) > 1:
        source = venue_label(venue) if venue else t("source-all")
        rows.append([InlineKeyboardButton(text=t("button-source-filter", source=source), callback_data="asset_source:menu")])
    rows.append(_menu_button_row() if back_to_menu else _wizard_nav_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def asset_sources_keyboard(candidates: list[AssetCandidate], *, venue: str | None = None) -> InlineKeyboardMarkup:
    venues = candidate_venues(candidates)
    buttons = [_source_button(t("source-all"), len(candidates), selected=venue is None, callback_data="asset_source:all")]
    for index, name in enumerate(venues):
        count = sum(1 for candidate in candidates if candidate.venue == name)
        buttons.append(_source_button(venue_label(name), count, selected=venue == name, callback_data=f"asset_source:{index}"))
    rows = [buttons[start : start + SOURCES_PER_ROW] for start in range(0, len(buttons), SOURCES_PER_ROW)]
    rows.append([InlineKeyboardButton(text=t("button-back"), callback_data="asset_source:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def candidate_venues(candidates: list[AssetCandidate]) -> list[str]:
    return list(dict.fromkeys(candidate.venue for candidate in candidates))


def alert_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("alert-type-percent"), callback_data="alert_type:percent")],
            [InlineKeyboardButton(text=t("alert-type-above"), callback_data="alert_type:above")],
            [InlineKeyboardButton(text=t("alert-type-below"), callback_data="alert_type:below")],
            _wizard_nav_row(),
        ]
    )


def threshold_keyboard(
    alert_type: str,
    *,
    one_time: bool = True,
    currency: str = "USD",
    native_symbol: str | None = None,
    metric: str = "price",
    supports_market_cap: bool = False,
    direction: str = "both",
    cooldown_seconds: int | None = None,
) -> InlineKeyboardMarkup:
    rows = []
    if alert_type == "percent":
        rows.append(
            [InlineKeyboardButton(text=t("button-default-percent"), callback_data="threshold:default_percent", style="success")]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text=_selected(format_direction_arrows(option), option == direction),
                    callback_data=f"threshold:direction:{option}",
                )
                for option in PERCENT_DIRECTIONS
            ]
        )
    elif supports_market_cap:
        rows.append(
            [
                InlineKeyboardButton(
                    text=_selected(t(f"button-metric-{option}"), option == metric), callback_data=f"threshold:metric:{option}"
                )
                for option in METRICS
            ]
        )
    options_row = [InlineKeyboardButton(text=one_time_label(one_time), callback_data="threshold:toggle_once")]
    if cooldown_seconds is not None:
        options_row.append(
            InlineKeyboardButton(
                text=t("button-cooldown", value=format_duration(cooldown_seconds)), callback_data="threshold:cooldown"
            )
        )
    rows.append(options_row)
    if alert_type != "percent" and native_symbol:
        rows.append(
            [InlineKeyboardButton(text=t("button-currency", currency=currency), callback_data="threshold:toggle_currency")]
        )
    rows.append(_wizard_nav_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def alert_created_keyboard(alert_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("button-edit-alert"), callback_data=f"alert_config:view:{alert_id}", style="primary")],
            [InlineKeyboardButton(text=t("button-add-another"), callback_data="menu:newalert", style="success")],
            [InlineKeyboardButton(text=t("menu-active-alerts"), callback_data="menu:alerts")],
            [InlineKeyboardButton(text=t("button-menu"), callback_data="wizard:cancel")],
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
    symbol = alert.asset.symbol if alert.asset else t("asset-fallback")
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
        condition = f"{t('market-cap-short')} > {compact}"
    elif alert.type == AlertType.MCAP_BELOW.value:
        condition = f"{t('market-cap-short')} < {compact}"
    else:
        condition = f"±{exact}"
    label = f"{index}. {symbol} {condition}"
    if alert.status == AlertStatus.PAUSED.value:
        label += " ⏸"
    return _truncate_button_text(label)


def one_time_label(one_time: bool) -> str:
    return t("button-one-time", state="✅" if one_time else "❌")


def notification_keyboard(alert_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("button-alert-settings"), callback_data=f"alert_config:open:{alert_id}", style="primary"
                )
            ]
        ]
    )


def _selected(label: str, selected: bool) -> str:
    return f"✅ {label}" if selected else label


def _menu_button_row() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text=t("button-back-to-menu"), callback_data="wizard:cancel")]


def _wizard_nav_row() -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton(text=t("button-back"), callback_data="wizard:back"),
        InlineKeyboardButton(text=t("button-menu"), callback_data="wizard:cancel"),
    ]


def _source_button(label: str, count: int, *, selected: bool, callback_data: str) -> InlineKeyboardButton:
    text = f"{'✅ ' if selected else ''}{label} ({count})"
    return InlineKeyboardButton(text=_truncate_button_text(text), callback_data=callback_data)


def _asset_candidate_label(candidate: AssetCandidate, *, with_address: bool = False) -> str:
    parts = [_label_key(candidate)[0], venue_label(candidate.venue)]
    if price := candidate.metadata.get("price_usd"):
        parts.append(f"${price}")
    if with_address and candidate.contract_address:
        parts.append(_short_address(candidate.contract_address))
    return _truncate_button_text(" · ".join(parts))


def _label_key(candidate: AssetCandidate) -> tuple[str, str]:
    title = candidate.name if candidate.type == AssetType.NFT_COLLECTION and candidate.name else candidate.symbol
    return title, candidate.venue


def _ambiguous_labels(candidates: list[AssetCandidate]) -> set[tuple[str, str]]:
    keys = [_label_key(candidate) for candidate in candidates]
    return {key for key in keys if keys.count(key) > 1}


def _short_address(address: str) -> str:
    return address if len(address) <= 10 else f"{address[:4]}…{address[-4:]}"


def _truncate_button_text(text: str, limit: int = 64) -> str:
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."
