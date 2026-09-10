from click.utils import strip_ansi
from typer.testing import CliRunner

from app.cli import app


def test_cli_without_args_lists_commands() -> None:
    result = CliRunner().invoke(app, [])

    assert result.exit_code == 0
    assert "Commands" in result.output
    assert "sync-commands" in result.output
    assert "create-admin" in result.output
    assert "configure-trenchbook-integration" in result.output
    assert "generate-integration-key" in result.output


def test_cli_bad_usage_shows_usage() -> None:
    result = CliRunner().invoke(app, ["create-admin"])
    output = strip_ansi(result.output)

    assert result.exit_code != 0
    assert "Usage:" in output
    assert "--telegram-id" in output
