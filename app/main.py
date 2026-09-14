from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from app.bot.handlers import setup_handlers
from app.bot.middlewares import DbSessionMiddleware, LocaleMiddleware
from app.core.config import settings
from app.db.session import SessionLocal
from app.providers.registry import provider_registry

logger = logging.getLogger(__name__)


def build_dispatcher() -> Dispatcher:
    storage = RedisStorage.from_url(settings.redis_url)
    dispatcher = Dispatcher(storage=storage)
    dispatcher.update.middleware(DbSessionMiddleware(SessionLocal))
    dispatcher.update.middleware(LocaleMiddleware())
    dispatcher.include_router(setup_handlers())

    return dispatcher


async def run_polling() -> None:
    logger.info("Starting bot in polling mode")
    bot = Bot(settings.bot_token)
    dispatcher = build_dispatcher()
    await bot.delete_webhook(drop_pending_updates=True)
    await dispatcher.start_polling(bot)


async def run_webhook() -> None:
    logger.info("Starting bot in webhook mode")
    bot = Bot(settings.bot_token)
    dispatcher = build_dispatcher()
    webhook_url = f"{settings.webhook_base_url.rstrip('/')}{settings.webhook_path}"
    await bot.set_webhook(webhook_url, secret_token=settings.webhook_secret)

    app = web.Application()
    SimpleRequestHandler(dispatcher=dispatcher, bot=bot, secret_token=settings.webhook_secret).register(
        app,
        path=settings.webhook_path,
    )
    setup_application(app, dispatcher, bot=bot)
    app.add_routes([web.get("/", lambda x: web.Response(text="Hello, world"))])

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, settings.web_server_host, settings.web_server_port)
    await site.start()
    logger.info(
        "Webhook server started; host=%s port=%s path=%s",
        settings.web_server_host,
        settings.web_server_port,
        settings.webhook_path,
    )
    await asyncio.Event().wait()


async def async_main() -> None:
    logging.basicConfig(level=logging.INFO)
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is required")
    try:
        if settings.bot_mode == "webhook":
            await run_webhook()
        else:
            await run_polling()
    finally:
        await provider_registry.close()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
