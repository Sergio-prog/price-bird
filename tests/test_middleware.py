from app.bot.middlewares import DbSessionMiddleware


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
