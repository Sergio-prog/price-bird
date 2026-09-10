from types import SimpleNamespace

from app.bot.keyboards import (
    alert_list_keyboard,
    asset_candidates_keyboard,
    asset_type_keyboard,
    back_to_menu_keyboard,
    start_menu_keyboard,
    threshold_keyboard,
)
from app.db.enums import AssetType
from app.providers.base import AssetCandidate


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


def test_alert_list_keyboard_uses_delete_callbacks() -> None:
    keyboard = alert_list_keyboard([SimpleNamespace(id=123), SimpleNamespace(id=456)])

    assert keyboard.inline_keyboard[0][1].text == "Delete #123"
    assert keyboard.inline_keyboard[0][1].callback_data == "alert_delete:123"
    assert keyboard.inline_keyboard[1][1].text == "Delete #456"
    assert keyboard.inline_keyboard[1][1].callback_data == "alert_delete:456"
    assert keyboard.inline_keyboard[2][0].callback_data == "wizard:cancel"


def test_back_to_menu_keyboard_uses_cancel_callback() -> None:
    keyboard = back_to_menu_keyboard()

    assert keyboard.inline_keyboard[0][0].text == "↩ Back to menu"
    assert keyboard.inline_keyboard[0][0].callback_data == "wizard:cancel"


def test_threshold_keyboard_has_default_percent_and_back() -> None:
    keyboard = threshold_keyboard("percent")

    assert keyboard.inline_keyboard[0][0].text == "Default (10.00%)"
    assert keyboard.inline_keyboard[0][0].callback_data == "threshold:default_percent"
    assert keyboard.inline_keyboard[1][0].callback_data == "wizard:cancel"


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
