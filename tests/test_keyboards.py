from types import SimpleNamespace

from app.bot.keyboards import alert_list_keyboard, asset_candidates_keyboard, start_menu_keyboard
from app.db.enums import AssetType
from app.providers.base import AssetCandidate


def test_start_menu_keyboard_exposes_main_actions() -> None:
    keyboard = start_menu_keyboard()

    assert keyboard.inline_keyboard[0][0].text == "New alert"
    assert keyboard.inline_keyboard[0][0].callback_data == "menu:newalert"
    assert keyboard.inline_keyboard[1][0].text == "My alerts"
    assert keyboard.inline_keyboard[1][0].callback_data == "menu:alerts"


def test_alert_list_keyboard_uses_delete_callbacks() -> None:
    keyboard = alert_list_keyboard([SimpleNamespace(id=123), SimpleNamespace(id=456)])

    assert keyboard.inline_keyboard[0][0].text == "Delete #123"
    assert keyboard.inline_keyboard[0][0].callback_data == "alert_delete:123"
    assert keyboard.inline_keyboard[1][0].text == "Delete #456"
    assert keyboard.inline_keyboard[1][0].callback_data == "alert_delete:456"


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
