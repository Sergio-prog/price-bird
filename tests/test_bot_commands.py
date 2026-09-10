from app.bot.commands import BOT_COMMANDS, bot_commands


def test_bot_commands_are_valid_for_telegram_menu() -> None:
    names = [command.command for command in BOT_COMMANDS]

    assert len(names) == len(set(names))
    for command in BOT_COMMANDS:
        assert command.command == command.command.lower()
        assert command.command.replace("_", "").isalnum()
        assert 1 <= len(command.command) <= 32
        assert 1 <= len(command.description) <= 256


def test_bot_commands_exclude_admin_by_default() -> None:
    public_commands = bot_commands()
    all_commands = bot_commands(include_admin=True)

    assert len(public_commands) < len(all_commands)
    assert "whitelist" not in {command.command for command in public_commands}
    assert "whitelist" in {command.command for command in all_commands}
    assert "help" in {command.command for command in public_commands}
    assert "debugalert" not in {command.command for command in all_commands}
