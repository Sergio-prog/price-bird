from __future__ import annotations

from aiogram import Router

from app.bot.handlers import admin, alerts, common


def setup_handlers() -> Router:
    router = Router(name="root")
    router.include_router(common.router)
    router.include_router(alerts.router)
    router.include_router(admin.router)
    return router


__all__ = ["setup_handlers"]
