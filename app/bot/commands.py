from __future__ import annotations

from dataclasses import dataclass

from aiogram.types import BotCommand

from app.i18n import t, translate


@dataclass(frozen=True)
class CommandSpec:
    command: str
    admin_only: bool = False


BOT_COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec("start"),
    CommandSpec("help"),
    CommandSpec("newalert"),
    CommandSpec("alert"),
    CommandSpec("examples"),
    CommandSpec("alerts"),
    CommandSpec("settings"),
    CommandSpec("language"),
    CommandSpec("deletealert"),
    CommandSpec("cancel"),
    CommandSpec("stats", admin_only=True),
    CommandSpec("users", admin_only=True),
    CommandSpec("whitelist", admin_only=True),
    CommandSpec("suspend", admin_only=True),
    CommandSpec("promote", admin_only=True),
)


def command_description(command: CommandSpec, locale: str | None = None) -> str:
    key = f"command-{command.command}"
    return t(key) if locale is None else translate(locale, key)


def bot_commands(*, include_admin: bool = False, locale: str | None = None) -> list[BotCommand]:
    return [
        BotCommand(command=command.command, description=command_description(command, locale))
        for command in BOT_COMMANDS
        if include_admin or not command.admin_only
    ]
