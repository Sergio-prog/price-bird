from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import aiohttp

from app.core.config import settings
from app.utils.ratelimit import ProviderThrottle, RateLimited

logger = logging.getLogger(__name__)

MAX_INLINE_PAUSE_SECONDS = 10


def backoff_seconds(attempt: int) -> float:
    return 0.5 * (2**attempt)


def retry_after_seconds(response: aiohttp.ClientResponse, attempt: int) -> float:
    retry_after = response.headers.get("retry-after")
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            pass
    reset_at = response.headers.get("x-ratelimit-reset")
    if reset_at:
        try:
            return max(0.0, float(reset_at) - time.time())
        except ValueError:
            pass
    return backoff_seconds(attempt)


class HttpClient:
    def __init__(self, *, throttle: ProviderThrottle, headers: dict[str, str] | None = None) -> None:
        self.throttle = throttle
        self.headers = headers or {}
        self._session: aiohttp.ClientSession | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def session(self) -> aiohttp.ClientSession:
        loop = asyncio.get_running_loop()
        if self._session is None or self._session.closed or self._loop is not loop:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=settings.provider_timeout_seconds),
                headers=self.headers,
            )
            self._loop = loop
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None
        self._loop = None

    async def get_json(self, url: str, *, params: dict[str, str] | None = None, missing_ok: bool = False) -> Any:
        last_error: Exception | None = None
        for attempt in range(settings.provider_max_attempts):
            await self.throttle.acquire()
            try:
                async with self.session().get(url, params=params) as response:
                    if response.status == 429:
                        delay = retry_after_seconds(response, attempt)
                        self.throttle.pause(delay)
                        if delay > MAX_INLINE_PAUSE_SECONDS:
                            raise RateLimited(self.throttle.name, delay)
                        continue
                    if 500 <= response.status < 600:
                        last_error = aiohttp.ClientResponseError(
                            response.request_info,
                            response.history,
                            status=response.status,
                            message=response.reason or "",
                        )
                        await asyncio.sleep(backoff_seconds(attempt))
                        continue
                    if missing_ok and response.status in {400, 404}:
                        return None
                    response.raise_for_status()
                    return await response.json()
            except aiohttp.ClientResponseError:
                raise
            except (aiohttp.ClientError, TimeoutError) as exc:
                last_error = exc
                if attempt + 1 >= settings.provider_max_attempts:
                    break
                await asyncio.sleep(backoff_seconds(attempt))

        if last_error is not None:
            raise last_error
        raise RuntimeError(f"{self.throttle.name} request failed after {settings.provider_max_attempts} attempts")
