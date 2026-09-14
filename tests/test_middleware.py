from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.bot.middlewares import DbSessionMiddleware, LocaleMiddleware
from app.bot.middlewares import locale as locale_middleware
from app.i18n import current_locale


class FakeSessionPool:
    def __init__(self) -> None:
        self.session = object()
        self.entered = False
        self.exited = False

    def __call__(self):
        return self

    async def __aenter__(self):
        self.entered = True
        return self.session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.exited = True


async def test_db_session_middleware_injects_session() -> None:
    session_pool = FakeSessionPool()
    middleware = DbSessionMiddleware(session_pool)
    seen = {}

    async def handler(event, data):
        seen["session"] = data["session"]
        return "ok"

    result = await middleware(handler, object(), {})

    assert result == "ok"
    assert seen["session"] is session_pool.session
    assert session_pool.entered is True
    assert session_pool.exited is True


async def test_locale_middleware_prefers_saved_language(monkeypatch) -> None:
    monkeypatch.setattr(locale_middleware, "get_user_language", AsyncMock(return_value="uk"))
    seen = {}

    async def handler(event, data):
        seen["locale"] = current_locale()

    telegram_user = SimpleNamespace(id=1, language_code="ru")
    await LocaleMiddleware()(handler, object(), {"session": object(), "event_from_user": telegram_user})

    assert seen["locale"] == "uk"
    assert current_locale() == "en"
