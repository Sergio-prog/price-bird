from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)


class RateLimited(RuntimeError):
    def __init__(self, provider: str, seconds: float) -> None:
        super().__init__(f"{provider} is rate limited; retry in {seconds:.0f}s")
        self.provider = provider
        self.seconds = seconds


class ProviderThrottle:
    def __init__(
        self,
        name: str,
        *,
        rate_per_minute: float,
        burst: int | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.name = name
        self.rate = rate_per_minute / 60
        self.capacity = burst if burst is not None else max(1, int(rate_per_minute / 5))
        self.tokens = float(self.capacity)
        self._clock = clock
        self.updated_at = clock()
        self.paused_until = self.updated_at

    async def acquire(self, cost: float = 1) -> None:
        delay = self.reserve(cost)
        while delay > 0:
            await asyncio.sleep(delay)
            delay = self.remaining_pause()

    def reserve(self, cost: float = 1) -> float:
        now = self._clock()
        self.tokens = min(float(self.capacity), self.tokens + (now - self.updated_at) * self.rate)
        self.updated_at = now
        self.tokens -= cost
        wait = 0.0 if self.tokens >= 0 else -self.tokens / self.rate
        return max(wait, self.paused_until - now)

    def pause(self, seconds: float) -> None:
        until = self._clock() + seconds
        if until <= self.paused_until:
            return
        self.paused_until = until
        logger.warning("Provider paused after rate limit; provider=%s seconds=%.0f", self.name, seconds)

    def remaining_pause(self) -> float:
        return max(0.0, self.paused_until - self._clock())

    @property
    def paused(self) -> bool:
        return self.remaining_pause() > 0
