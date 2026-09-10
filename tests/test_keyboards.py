from decimal import Decimal
from types import SimpleNamespace

from app.bot.keyboards import (
    alert_button_label,
    alert_list_keyboard,
    asset_candidates_keyboard,
    asset_type_keyboard,
    back_to_menu_keyboard,
    start_menu_keyboard,
    threshold_keyboard,
    wizard_back_keyboard,
)
from app.db.enums import AssetType
from app.providers.base import AssetCandidate


def _alert(alert_id: int, **overrides):
    values = {
        "id": alert_id,
        "type": "percent_change",
        "threshold_value": Decimal("10"),
        "direction": "both",
        "status": "active",
        "asset": SimpleNamespace(symbol="MEME"),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_start_menu_keyboard_exposes_main_actions() -> None:
    keyboard = start_menu_keyboard()

    assert keyboard.inline_keyboard[0][0].text == "🔔 New alert"
    assert keyboard.inline_keyboard[0][0].callback_data == "menu:newalert"
    assert keyboard.inline_keyboard[1][0].text == "📌 Active alerts"
    assert keyboard.inline_keyboard[1][0].callback_data == "menu:alerts"


def test_asset_type_keyboard_separates_tokens_and_nfts() -> None:
    keyboard = asset_type_keyboard()

    assert keyboard.inline_keyboard[0][0].text == "🪙 Coins / CEX"
    assert keyboard.inline_keyboard[0][0].callback_data == "asset_type:token"
    assert keyboard.inline_keyboard[1][0].text == "🖼 NFT floor"
    assert keyboard.inline_keyboard[1][0].callback_data == "asset_type:nft"


def test_alert_list_keyboard_shows_one_button_per_alert() -> None:
    keyboard = alert_list_keyboard([_alert(123), _alert(456, type="price_above", threshold_value=Decimal("100000"))])

    assert keyboard.inline_keyboard[0][0].text == "1. MEME 10.00% ↑↓"
    assert keyboard.inline_keyboard[0][0].callback_data == "alert_config:view:123"
    assert keyboard.inline_keyboard[1][0].text == "2. MEME > $100000"
    assert keyboard.inline_keyboard[1][0].callback_data == "alert_config:view:456"
    assert keyboard.inline_keyboard[2][0].text == "↩️ Back to menu"
    assert keyboard.inline_keyboard[2][0].callback_data == "wizard:cancel"


def test_alert_list_keyboard_paginates() -> None:
    alerts = [_alert(index) for index in range(1, 12)]

    first = alert_list_keyboard(alerts, page=1, page_size=5)
    second = alert_list_keyboard(alerts, page=2, page_size=5)
    last = alert_list_keyboard(alerts, page=99, page_size=5)

    assert [row[0].text for row in first.inline_keyboard[:5]] == [f"{n}. MEME 10.00% ↑↓" for n in range(1, 6)]
    assert [button.text for button in first.inline_keyboard[5]] == ["◀️", "1/3", "▶️"]
    assert first.inline_keyboard[5][0].callback_data == "alerts:noop"
    assert first.inline_keyboard[5][2].callback_data == "alerts:page:2"
    assert second.inline_keyboard[0][0].text == "6. MEME 10.00% ↑↓"
    assert second.inline_keyboard[5][0].callback_data == "alerts:page:1"
    assert last.inline_keyboard[0][0].text == "11. MEME 10.00% ↑↓"
    assert last.inline_keyboard[1][1].text == "3/3"
    assert last.inline_keyboard[1][2].callback_data == "alerts:noop"


def test_alert_button_label_formats_each_alert_type() -> None:
    assert alert_button_label(_alert(1, direction="up"), 1) == "1. MEME 10.00% ↑"
    assert alert_button_label(_alert(1, type="price_below", threshold_value=Decimal("0.5")), 2) == "2. MEME < $0.5"
    assert alert_button_label(_alert(1, type="mcap_above", threshold_value=Decimal("1500000")), 3) == "3. MEME MC > $1.5M"
    assert alert_button_label(_alert(1, type="mcap_below", threshold_value=Decimal("2000000000")), 4) == "4. MEME MC < $2B"
    assert alert_button_label(_alert(1, status="paused"), 5) == "5. MEME 10.00% ↑↓ ⏸"


def test_back_keyboards_use_expected_callbacks() -> None:
    menu = back_to_menu_keyboard()
    back = wizard_back_keyboard()

    assert menu.inline_keyboard[0][0].text == "↩️ Back to menu"
    assert menu.inline_keyboard[0][0].callback_data == "wizard:cancel"
    assert [button.callback_data for button in back.inline_keyboard[0]] == ["wizard:back", "wizard:cancel"]


def test_threshold_keyboard_has_default_percent_and_back() -> None:
    keyboard = threshold_keyboard("percent")

    assert keyboard.inline_keyboard[0][0].text == "Default (10.00%)"
    assert keyboard.inline_keyboard[0][0].callback_data == "threshold:default_percent"
    assert keyboard.inline_keyboard[1][0].callback_data == "wizard:back"


def test_threshold_keyboard_offers_one_time_toggle_for_market_cap() -> None:
    enabled = threshold_keyboard("mcap_above", one_time=True)
    disabled = threshold_keyboard("mcap_below", one_time=False)

    assert enabled.inline_keyboard[0][0].text == "One time: ✅"
    assert enabled.inline_keyboard[0][0].callback_data == "threshold:toggle_once"
    assert disabled.inline_keyboard[0][0].text == "One time: ❌"
    assert threshold_keyboard("above").inline_keyboard[0][0].callback_data == "wizard:back"


def test_asset_candidates_keyboard_includes_pair_and_price() -> None:
    keyboard = asset_candidates_keyboard(
        [
            AssetCandidate(
                type=AssetType.TOKEN,
                provider="dexscreener",
                provider_asset_id="solana:abc",
                symbol="BONK",
                chain="solana",
                metadata={"pair": "BONK/SOL", "price_usd": "0.00001823"},
            )
        ]
    )

    button = keyboard.inline_keyboard[0][0]
    assert button.text == "BONK / solana / BONK/SOL / $0.00001823 / dexscreener"
    assert button.callback_data == "asset:0"
    assert keyboard.inline_keyboard[1][0].callback_data == "wizard:back"


def test_threshold_keyboard_offers_currency_toggle_only_with_native_symbol() -> None:
    with_native = threshold_keyboard("above", currency="ETH", native_symbol="ETH")
    without_native = threshold_keyboard("above")

    assert with_native.inline_keyboard[0][0].text == "Currency: ETH"
    assert with_native.inline_keyboard[0][0].callback_data == "threshold:toggle_currency"
    assert without_native.inline_keyboard[0][0].callback_data == "wizard:back"
    assert threshold_keyboard("percent", native_symbol="ETH").inline_keyboard[1][0].callback_data == "wizard:back"


def test_alert_button_label_shows_native_currency() -> None:
    alert = _alert(1, type="price_below", threshold_value=Decimal("0.8"), threshold_currency="ETH")
    assert alert_button_label(alert, 1) == "1. MEME < 0.8 ETH"
    alert = _alert(1, type="mcap_above", threshold_value=Decimal("1500"), threshold_currency="SOL")
    assert alert_button_label(alert, 2) == "2. MEME MC > 1.5K SOL"
