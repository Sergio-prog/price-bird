from __future__ import annotations

from aiogram import Router

from app.bot.handlers import admin, alert_settings, alerts, common, settings


def setup_handlers() -> Router:
    router = Router(name="root")
    router.include_router(common.router)
    router.include_router(settings.router)
    router.include_router(alert_settings.router)
    router.include_router(alerts.router)
    router.include_router(admin.router)
    return router


__all__ = ["setup_handlers"]
