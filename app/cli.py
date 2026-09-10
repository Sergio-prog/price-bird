from __future__ import annotations

import asyncio

import typer
from aiogram import Bot

from app.bot.commands import bot_commands
from app.core.config import settings
from app.db import repositories as repo
from app.db.enums import AccessStatus, UserRole
from app.db.session import SessionLocal
from app.integrations.catalog import TRENCHBOOK_BASE_URL, configure_trenchbook
from app.integrations.secrets import generate_encryption_key

app = typer.Typer(help="Price alert bot admin CLI.")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@app.command()
def sync_commands(include_admin: bool = typer.Option(False, help="Include admin-only bot commands.")) -> None:
    async def run() -> None:
        if not settings.bot_token:
            raise typer.BadParameter("BOT_TOKEN is required")

        bot = Bot(settings.bot_token)
        try:
            commands = bot_commands(include_admin=include_admin)
            await bot.set_my_commands(commands)
        finally:
            await bot.session.close()

        typer.echo(f"Synced {len(commands)} bot commands.")

    asyncio.run(run())


@app.command()
def create_admin(
    telegram_id: int = typer.Option(..., help="Telegram numeric user ID."),
    username: str | None = typer.Option(None, help="Optional Telegram username."),
) -> None:
    async def run() -> None:
        async with SessionLocal() as session:
            user = await repo.ensure_admin(session, telegram_id=telegram_id, username=username)
            await session.commit()
        typer.echo(f"Admin active: {user.telegram_id}")

    asyncio.run(run())


@app.command()
def whitelist(
    telegram_id: int = typer.Option(..., help="Telegram numeric user ID."),
    admin: bool = typer.Option(False, help="Grant admin role too."),
) -> None:
    async def run() -> None:
        async with SessionLocal() as session:
            user = await repo.set_user_access(
                session,
                telegram_id=telegram_id,
                access_status=AccessStatus.ACTIVE,
                role=UserRole.ADMIN if admin else None,
            )
            await session.commit()
        typer.echo(f"User active: {user.telegram_id}")

    asyncio.run(run())


@app.command()
def suspend(telegram_id: int = typer.Option(..., help="Telegram numeric user ID.")) -> None:
    async def run() -> None:
        async with SessionLocal() as session:
            user = await repo.set_user_access(
                session,
                telegram_id=telegram_id,
                access_status=AccessStatus.SUSPENDED,
            )
            await session.commit()
        typer.echo(f"User suspended: {user.telegram_id}")

    asyncio.run(run())


@app.command()
def generate_integration_key() -> None:
    """Generate the master key used to encrypt integration secrets."""
    typer.echo(f"INTEGRATION_SECRETS_KEY={generate_encryption_key()}")


@app.command()
def configure_trenchbook_integration(
    base_url: str = typer.Option(TRENCHBOOK_BASE_URL, help="Public Trenchbook base URL."),
    rotate_secret: bool = typer.Option(False, help="Replace the receiver secret and pause existing connections."),
) -> None:
    """Create or update the built-in Trenchbook integration."""

    async def run() -> None:
        try:
            async with SessionLocal() as session, session.begin():
                definition, secret = await configure_trenchbook(
                    session,
                    base_url=base_url,
                    rotate_secret=rotate_secret,
                )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc

        typer.echo(f"Configured {definition.name} at {definition.base_url}{definition.webhook_path}.")
        if secret:
            typer.echo("Copy this value to Trenchbook. It will not be shown again:")
            typer.echo(f"PRICEBIRD_WEBHOOK_SECRET={secret}")
        else:
            typer.echo("The existing signing secret was preserved. Use --rotate-secret to replace it.")

    asyncio.run(run())


if __name__ == "__main__":
    app(prog_name="uv run app/cli.py")
