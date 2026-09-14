from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from aiogram import Bot
from aiogram.types import FSInputFile, InputProfilePhotoStatic

from app.bot.commands import bot_commands
from app.bot.profile import BOT_NAME, bot_description, bot_short_description
from app.core.config import settings
from app.db import repositories as repo
from app.db.enums import AccessStatus, AlertLimitKind, UserRole
from app.db.session import SessionLocal
from app.i18n import DEFAULT_LOCALE, SUPPORTED_LOCALES
from app.integrations.catalog import TRENCHBOOK_BASE_URL, configure_trenchbook
from app.integrations.secrets import generate_encryption_key

app = typer.Typer(help="Price alert bot admin CLI.")
DEFAULT_PROFILE_PHOTO = Path(__file__).resolve().parents[1] / "assets/brand/price-bird-logo.jpg"


def _language_code(locale: str) -> str | None:
    return None if locale == DEFAULT_LOCALE else locale


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
            for locale in SUPPORTED_LOCALES:
                commands = bot_commands(include_admin=include_admin, locale=locale)
                await bot.set_my_commands(commands, language_code=_language_code(locale))
        finally:
            await bot.session.close()

        typer.echo(f"Synced {len(commands)} bot commands for {', '.join(SUPPORTED_LOCALES)}.")

    asyncio.run(run())


@app.command()
def sync_profile(
    profile_photo: Annotated[
        Path,
        typer.Option(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Static JPG profile photo to upload.",
        ),
    ] = DEFAULT_PROFILE_PHOTO,
) -> None:
    """Publish the production name, copy, and profile photo to Telegram."""

    async def run() -> None:
        if not settings.bot_token:
            raise typer.BadParameter("BOT_TOKEN is required")

        bot = Bot(settings.bot_token)
        try:
            await bot.set_my_name(BOT_NAME)
            for locale in SUPPORTED_LOCALES:
                language_code = _language_code(locale)
                await bot.set_my_description(bot_description(locale), language_code=language_code)
                await bot.set_my_short_description(bot_short_description(locale), language_code=language_code)
            await bot.set_my_profile_photo(
                InputProfilePhotoStatic(photo=FSInputFile(profile_photo)),
            )
        finally:
            await bot.session.close()

        typer.echo("Synced the Price Bird name, description, bio, and profile photo.")

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
def set_alert_limit(
    kind: Annotated[AlertLimitKind, typer.Option(help="Alert kind the limits apply to.")],
    max_watched_assets: Annotated[int | None, typer.Option(min=0, help="Distinct assets polled for this kind.")] = None,
    max_active_alerts: Annotated[int | None, typer.Option(min=0, help="Active and paused alerts across all users.")] = None,
    default_user_max_alerts: Annotated[int | None, typer.Option(min=0, help="Per-user limit without an override.")] = None,
) -> None:
    """Update the global limits for token or NFT alerts."""

    async def run() -> None:
        async with SessionLocal() as session, session.begin():
            limit = await repo.update_alert_limit(
                session,
                kind,
                max_watched_assets=max_watched_assets,
                max_active_alerts=max_active_alerts,
                default_user_max_alerts=default_user_max_alerts,
            )
            typer.echo(
                f"{kind.value}: max_watched_assets={limit.max_watched_assets} "
                f"max_active_alerts={limit.max_active_alerts} default_user_max_alerts={limit.default_user_max_alerts}"
            )

    asyncio.run(run())


@app.command()
def set_user_alert_limit(
    telegram_id: Annotated[int, typer.Option(help="Telegram numeric user ID.")],
    kind: Annotated[AlertLimitKind, typer.Option(help="Alert kind the limit applies to.")],
    max_alerts: Annotated[int | None, typer.Option(min=0, help="Omit to restore the global default.")] = None,
) -> None:
    """Override or reset one user's alert limit."""

    async def run() -> None:
        async with SessionLocal() as session, session.begin():
            user = await repo.get_user_by_telegram_id(session, telegram_id)
            if user is None:
                raise typer.BadParameter(f"User {telegram_id} not found")
            await repo.set_user_alert_limit(session, user_id=user.id, kind=kind, max_alerts=max_alerts)
        limit = "global default" if max_alerts is None else str(max_alerts)
        typer.echo(f"User {telegram_id} {kind.value} alert limit: {limit}")

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
