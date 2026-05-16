from __future__ import annotations

from dataclasses import dataclass

from aiogram.types import BotCommand


@dataclass(frozen=True)
class CommandSpec:
    command: str
    description: str
    admin_only: bool = False


BOT_COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec("start", "Open main menu"),
    CommandSpec("help", "Show available commands"),
    CommandSpec("newalert", "Create an alert step by step"),
    CommandSpec("alert", "Create alert from text, e.g. BTC 10%"),
    CommandSpec("examples", "Show alert examples"),
    CommandSpec("alerts", "Show active alerts"),
    CommandSpec("deletealert", "Delete alert by id"),
    CommandSpec("cancel", "Cancel current action"),
    CommandSpec("stats", "Show bot stats", admin_only=True),
    CommandSpec("users", "List users", admin_only=True),
    CommandSpec("whitelist", "Allow user by Telegram id", admin_only=True),
    CommandSpec("suspend", "Suspend user by Telegram id", admin_only=True),
    CommandSpec("promote", "Promote user to admin", admin_only=True),
)


def bot_commands(*, include_admin: bool = False) -> list[BotCommand]:
    return [
        BotCommand(command=command.command, description=command.description)
        for command in BOT_COMMANDS
        if include_admin or not command.admin_only
    ]
