from __future__ import annotations

from html import escape

from app.bot.commands import CommandSpec, command_description
from app.i18n import t

CHANNEL_URL = "https://t.me/there_is_no_meme"


def start_message(first_name: str | None, username: str | None) -> str:
    name = username or first_name or t("start-name-fallback")
    return t("start", name=escape(name), channel_url=CHANNEL_URL)


def help_message(commands: tuple[CommandSpec, ...]) -> str:
    lines = [t("help-title"), ""]
    for command in commands:
        if command.admin_only:
            continue
        lines.append(f"/{command.command} - {escape(command_description(command))}")
    return "\n".join(lines)


def examples_message() -> str:
    return t("examples")


def asset_type_prompt() -> str:
    return t("asset-type-prompt")


def query_prompt(*, nft: bool) -> str:
    return t("query-prompt-nft" if nft else "query-prompt-token")


def provider_failed_message(*, nft: bool) -> str:
    return t("provider-failed-nft" if nft else "provider-failed-token")


def provider_misconfigured_message(*, nft: bool) -> str:
    return t("provider-misconfigured-nft" if nft else "provider-misconfigured-token")


def no_alerts_message() -> str:
    return t("no-alerts")


def alerts_list_message(total: int) -> str:
    return t("alerts-list", total=str(total))


def no_matches_message(*, nft: bool) -> str:
    return t("no-matches-nft" if nft else "no-matches-token")


def threshold_prompt(*, asset_label: str, alert_type: str, currency: str = "USD", native_symbol: str | None = None) -> str:
    asset = escape(asset_label)
    if alert_type == "percent":
        return t("threshold-percent", asset=asset)
    if native_symbol:
        hint = t("threshold-unit-hint-native", symbol=escape(native_symbol))
    else:
        hint = t("threshold-unit-hint")
    key = {"above": "threshold-above", "below": "threshold-below"}.get(alert_type, "threshold-mcap")
    return t(key, asset=asset, currency=escape(currency), hint=hint)
