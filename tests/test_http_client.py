import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from app.utils.http import HttpClient
from app.utils.ratelimit import ProviderThrottle, RateLimited


async def _serve(statuses: list[int], headers: dict[str, str] | None = None) -> TestServer:
    calls: list[int] = []

    async def handler(request: web.Request) -> web.Response:
        status = statuses[min(len(calls), len(statuses) - 1)]
        calls.append(status)
        if status == 200:
            return web.json_response({"ok": len(calls)})
        return web.Response(status=status, headers=headers or {})

    app = web.Application()
    app.router.add_get("/resource", handler)
    server = TestServer(app)
    await server.start_server()
    server.calls = calls
    return server


@pytest.mark.asyncio
async def test_short_retry_after_pauses_then_retries() -> None:
    server = await _serve([429, 200], headers={"Retry-After": "0"})
    client = HttpClient(throttle=ProviderThrottle("test", rate_per_minute=6000))
    try:
        payload = await client.get_json(str(server.make_url("/resource")))
    finally:
        await client.close()
        await server.close()

    assert payload == {"ok": 2}
    assert server.calls == [429, 200]


@pytest.mark.asyncio
async def test_long_retry_after_raises_and_pauses_provider() -> None:
    server = await _serve([429], headers={"Retry-After": "120"})
    throttle = ProviderThrottle("test", rate_per_minute=6000)
    client = HttpClient(throttle=throttle)
    try:
        with pytest.raises(RateLimited):
            await client.get_json(str(server.make_url("/resource")))
    finally:
        await client.close()
        await server.close()

    assert throttle.remaining_pause() > 100
    assert server.calls == [429]


@pytest.mark.asyncio
async def test_client_errors_are_not_retried() -> None:
    server = await _serve([404])
    client = HttpClient(throttle=ProviderThrottle("test", rate_per_minute=6000))
    try:
        assert await client.get_json(str(server.make_url("/resource")), missing_ok=True) is None
        with pytest.raises(Exception, match="404"):
            await client.get_json(str(server.make_url("/resource")))
    finally:
        await client.close()
        await server.close()

    assert server.calls == [404, 404]
