from __future__ import annotations

import asyncio

import typer

from app.db import repositories as repo
from app.db.enums import AccessStatus, UserRole
from app.db.session import SessionLocal

app = typer.Typer(help="Price alert bot admin CLI.")


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
