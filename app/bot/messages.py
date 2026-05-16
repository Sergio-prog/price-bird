from __future__ import annotations

from html import escape

from app.bot.commands import CommandSpec

CHANNEL_URL = "https://t.me/there_is_no_meme"


def start_message(first_name: str | None, username: str | None) -> str:
    name = username or first_name or "there"
    return "\n".join(
        [
            f"👋 <b>{escape(name)}</b>, welcome to <b>Price Alerts</b>.",
            "",
            "Catch token moves, CEX pairs, and NFT floor changes before the market gets noisy.",
            "",
            "🔎 <b>Watch</b> coins by ticker or contract, then choose percent or price triggers.",
            "🖼 <b>Follow</b> NFT collections by floor price without token spam.",
            "📌 <b>Review</b> active alerts and remove stale ones from the menu.",
            "",
            f'📣 <a href="{CHANNEL_URL}">Channel</a>',
        ]
    )


def help_message(commands: tuple[CommandSpec, ...]) -> str:
    lines = [
        "<b>Available commands</b>",
        "",
    ]
    for command in commands:
        if command.admin_only:
            continue
        lines.append(f"/{command.command} - {escape(command.description)}")
    return "\n".join(lines)


def examples_message() -> str:
    return "\n".join(
        [
            "<b>Examples</b>",
            "",
            "<b>Fast command</b>",
            "<code>/alert BTC 10%</code>",
            "<code>/alert ETH &gt; 4000</code>",
            "<code>/alert SOL &lt; 120</code>",
            "<code>/alert PEPE 15%</code>",
            "<code>/alert BTC/USDT &lt; 90000</code>",
            "",
            "<b>NFT floors</b>",
            "<code>/alert milady floor 10%</code>",
            "<code>/alert pudgy penguins floor 15%</code>",
            "<code>/alert boredapeyachtclub floor &lt; 8</code>",
            "",
            "<b>Step by step</b>",
            "Use <code>/newalert</code> when search returns many matches or you want buttons.",
        ]
    )


def asset_type_prompt() -> str:
    return "What market are we watching?"


def query_prompt(*, nft: bool) -> str:
    if nft:
        return "🖼 Send the NFT collection name. Example: <code>milady</code>"
    return "🔎 Send a ticker, contract, or CEX pair. Example: <code>BONK</code> or <code>BTC</code>"


def provider_failed_message(*, nft: bool) -> str:
    if nft:
        return "Failed to search NFT collections. Provider is unavailable or not configured yet. Try again later."
    return "Failed to search assets. Provider is unavailable right now. Try again later."


def no_matches_message(*, nft: bool) -> str:
    if nft:
        return "No NFT collections found. Try the collection slug or a shorter name."
    return "No assets found. Try a ticker, contract address, or a shorter name."


def threshold_prompt(*, asset_label: str, alert_type: str) -> str:
    if alert_type == "percent":
        return "\n".join(
            [
                f"<b>{escape(asset_label)}</b>",
                "",
                "Enter % price change to receive notifications:",
            ]
        )
    if alert_type == "above":
        return "\n".join(
            [
                f"<b>{escape(asset_label)}</b>",
                "",
                "Enter USD price that should trigger when market moves above it:",
            ]
        )
    return "\n".join(
        [
            f"<b>{escape(asset_label)}</b>",
            "",
            "Enter USD price that should trigger when market drops below it:",
        ]
    )
