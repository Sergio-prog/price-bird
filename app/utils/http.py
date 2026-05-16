from __future__ import annotations

import asyncio

import aiohttp


async def sleep_before_retry(response: aiohttp.ClientResponse, attempt: int) -> None:
    retry_after = response.headers.get("retry-after")
    if retry_after:
        try:
            await asyncio.sleep(min(float(retry_after), 5))
            return
        except ValueError:
            pass
    await asyncio.sleep(0.5 * (2**attempt))
