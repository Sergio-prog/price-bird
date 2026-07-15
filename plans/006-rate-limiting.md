# Plan 006: Add per-user rate limiting middleware

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 860c330..HEAD -- app/bot/middlewares/ app/core/config.py app/bot/handlers/__init__.py app/main.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none
- **Category**: security
- **Planned at**: commit `860c330`, 2026-07-01

## Why this matters

Every bot command that triggers a provider search (`/alert BTC 10%`,
`/newalert` wizard queries) makes outbound API calls. Without rate limiting, a
malicious or overeager user can spam commands and exhaust provider rate limits
(DexScreener allows 300 req/min without an API key), degrading service for
everyone. A simple per-user sliding-window rate limiter backed by Redis
prevents this. Redis is already available, already used for FSM storage and
queues — the infrastructure is in place.

## Current state

`app/main.py:19-25` — `build_dispatcher` sets up middleware:

```python
def build_dispatcher() -> Dispatcher:
    storage = RedisStorage.from_url(settings.redis_url)
    dispatcher = Dispatcher(storage=storage)
    dispatcher.update.middleware(DbSessionMiddleware(SessionLocal))
    dispatcher.include_router(setup_handlers())
    return dispatcher
```

Only one middleware exists: `DbSessionMiddleware` in
`app/bot/middlewares/db.py:10-23`. It injects a DB session into every update:

```python
class DbSessionMiddleware(BaseMiddleware):
    def __init__(self, session_pool):
        super().__init__()
        self.session_pool = session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self.session_pool() as session:
            data["session"] = session
            return await handler(event, data)
```

The `BaseMiddleware.__call__` pattern is the aiogram 3 standard. Middleware is
registered via `dispatcher.update.middleware(...)` (outer) or
`router.message.middleware(...)` (inner, per-router). For rate limiting we want
outer middleware — it runs before any handler.

`app/core/config.py` — no rate limit settings exist.

`app/utils/redis.py:8-9` — the Redis client factory:

```python
def get_redis() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)
```

Redis is used with `decode_responses=True` (strings, not bytes). Rate limit
keys will be strings.

Repo conventions:
- Middleware lives in `app/bot/middlewares/`.
- Each middleware is its own file with an `__init__.py` that re-exports nothing
  special (just empty). Check `app/bot/middlewares/__init__.py` — it's likely
  empty or minimal.
- aiogram middleware receives `event` (TelegramObject) and `data` (dict with
  injected dependencies). The `event` has `.from_user` for the Telegram user.
- Rate limits should skip admin users (they need to manage the bot).
- Use existing patterns: `settings` for config, `get_redis()` for Redis client.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Install | `uv sync --extra dev` | exit 0 |
| Lint | `uv run ruff check app/` | exit 0, no output |
| Tests | `uv run pytest tests/ -q` | exit 0, all pass |

## Scope

**In scope** (files to create/modify):
- `app/bot/middlewares/rate_limit.py` — create, contains `RateLimitMiddleware`
- `app/core/config.py` — add rate limit settings
- `app/main.py` — register the middleware in `build_dispatcher`
- `.env.example` — add new env vars (optional, with defaults)
- `docker-compose.yml` — add new env vars (optional, with defaults)

**Out of scope** (do NOT touch):
- `app/bot/handlers/` — no handler changes needed; middleware applies globally.
- `app/bot/middlewares/db.py` — unrelated.
- `app/utils/redis.py` — fine as-is.
- `app/db/repositories/users.py` — `is_admin` is used read-only.
- Any test files (middleware testing requires Redis mock; defer).

## Git workflow

- Branch: `advisor/006-rate-limiting`
- Commits: conventional, e.g. `feat: add per-user rate limiting middleware`
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Add rate limit settings to config

In `app/core/config.py`, after the notification settings (around line 29), add:

```python
rate_limit_max_requests: int = Field(default=30, alias="RATE_LIMIT_MAX_REQUESTS")
rate_limit_window_seconds: int = Field(default=60, alias="RATE_LIMIT_WINDOW_SECONDS")
```

Default: 30 requests per 60 seconds per user. This is conservative —
DexScreener allows 300/min without a key. Bump in production if needed.

**Verify**:

```bash
uv run python -c "from app.core.config import settings; print(settings.rate_limit_max_requests, settings.rate_limit_window_seconds)"
```

Expected: `30 60`.

### Step 2: Create RateLimitMiddleware

Create `app/bot/middlewares/rate_limit.py`. The middleware must:

1. Accept `redis_url` in `__init__` and create a Redis client lazily (or on
   init, matching the `get_redis()` pattern).
2. In `__call__`, extract the user ID from `event.from_user`. Skip if no user
   (e.g., channel posts) or if user is admin (import `is_admin` from
   `app.db.repositories.users` — but that requires a DB session, which is
   injected by `DbSessionMiddleware` AFTER this middleware runs).

   **Important ordering**: `RateLimitMiddleware` must be registered BEFORE
   `DbSessionMiddleware` in the dispatcher, so it can't use the DB session
   for admin checks. Use a simpler check: skip rate limiting for users
   listed in an admin ID set, or skip the admin check entirely in middleware
   and rely on the fact that admins have few commands to run. Alternative:
   check `event.from_user.id` against a configurable set of admin Telegram IDs.

   Simplest correct approach: skip admin check entirely in v1. Rate limiting
   applies to all users equally. Admins can whitelist themselves later via a
   config setting if needed. This keeps the middleware stateless (no DB dep).

3. Use a Redis sorted set for the sliding window:
   - Key: `ratelimit:{user_id}`
   - On each request: `ZREMRANGEBYSCORE` to remove entries older than
     `now - window_seconds`, then `ZCARD` to count remaining. If count >= max,
     return early without calling the handler (optionally answer with a
     "rate limited" message if the event is a message/callback).
   - If under limit: `ZADD` with current timestamp + a unique member (use
     `time.time() + random` or an incrementing counter), then call the handler.

4. After the handler, clean up: `EXPIRE` the key to `window_seconds * 2` to
   prevent key accumulation.

```python
from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject, CallbackQuery
from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        super().__init__()
        self._redis: Redis | None = None

    def _client(self) -> Redis:
        if self._redis is None:
            from app.utils.redis import get_redis
            self._redis = get_redis()
        return self._redis

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id = getattr(event, "from_user", None)
        if user_id is None:
            return await handler(event, data)

        uid = user_id.id
        client = self._client()
        key = f"ratelimit:{uid}"
        now = time.time()
        window_start = now - settings.rate_limit_window_seconds

        async with client.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            _, current = await pipe.execute()

        if current >= settings.rate_limit_max_requests:
            logger.warning("Rate limit hit; user_id=%s count=%s", uid, current)
            if isinstance(event, Message):
                await event.answer("Too many requests. Please wait a moment.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Slow down!", show_alert=True)
            return

        await client.zadd(key, {str(now): now})
        await client.expire(key, settings.rate_limit_window_seconds * 2, nx=True)

        return await handler(event, data)
```

**Verify**:

```bash
uv run ruff check app/bot/middlewares/rate_limit.py
```

Expected: exit 0.

### Step 3: Register the middleware in build_dispatcher

In `app/main.py`, import the new middleware and register it BEFORE
`DbSessionMiddleware` (so rate limiting doesn't consume DB sessions from
rate-limited users):

Add import at top (around line 12):

```python
from app.bot.middlewares.rate_limit import RateLimitMiddleware
```

In `build_dispatcher` (line 22), add before the DB middleware:

```python
dispatcher.update.middleware(RateLimitMiddleware())
```

The order should be:

```python
def build_dispatcher() -> Dispatcher:
    storage = RedisStorage.from_url(settings.redis_url)
    dispatcher = Dispatcher(storage=storage)
    dispatcher.update.middleware(RateLimitMiddleware())
    dispatcher.update.middleware(DbSessionMiddleware(SessionLocal))
    dispatcher.include_router(setup_handlers())
    return dispatcher
```

Outer middleware runs in registration order — `RateLimitMiddleware` first,
then `DbSessionMiddleware`. Rate-limited requests never reach the DB middleware.

**Verify**:

```bash
grep "RateLimitMiddleware" app/main.py
```

Expected: two matches — the import and the `.middleware(...)` registration.

### Step 4: Add optional env vars

In `.env.example`, after the notification settings:

```
RATE_LIMIT_MAX_REQUESTS=30
RATE_LIMIT_WINDOW_SECONDS=60
```

In `docker-compose.yml`, in `x-app-environment`:

```yaml
RATE_LIMIT_MAX_REQUESTS: ${RATE_LIMIT_MAX_REQUESTS:-30}
RATE_LIMIT_WINDOW_SECONDS: ${RATE_LIMIT_WINDOW_SECONDS:-60}
```

**Verify**:

```bash
grep RATE_LIMIT .env.example docker-compose.yml
```

Expected: two matches in each file.

### Step 5: Run full verification

```bash
uv run ruff check app/
```

Expected: exit 0.

```bash
uv run pytest tests/ -q
```

Expected: exit 0, all tests pass. The middleware is not exercised by existing
tests — they use in-memory FSM storage, not full dispatcher with middleware.

## Test plan

No new tests required for this plan. The middleware interacts with Redis, which
requires a running Redis instance for meaningful testing. The existing test
suite doesn't cover middleware at this level.

If middleware tests are added later:
- Test that requests under the limit pass through.
- Test that requests over the limit are blocked with a message.
- Test that the sliding window expires old entries.
- Model the test after `tests/test_middleware.py` (the existing middleware test
  file — read it for patterns).

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `app/bot/middlewares/rate_limit.py` exists with `RateLimitMiddleware`.
- [ ] `app/core/config.py` has `rate_limit_max_requests` and
  `rate_limit_window_seconds`.
- [ ] `app/main.py` registers `RateLimitMiddleware()` before
  `DbSessionMiddleware`.
- [ ] `.env.example` and `docker-compose.yml` have the new env vars.
- [ ] `uv run ruff check app/` exits 0.
- [ ] `uv run pytest tests/ -q` exits 0.
- [ ] No files outside the in-scope list are modified (`git status`).
- [ ] `plans/README.md` status row updated.

## STOP conditions

Stop and report if:

- The `build_dispatcher` function in `main.py` has changed significantly
  (different middleware registration pattern).
- `from app.utils.redis import get_redis` import fails — the module was
  renamed or moved.
- `uv run pytest tests/ -q` fails after the changes.
- Redis is not available locally for manual testing — that's fine, CI will
  catch any issues when plan 001 lands.

## Maintenance notes

- The sliding window uses sorted sets. Under heavy load with many unique
  users, Redis memory usage grows with the number of active rate limit keys.
  The `EXPIRE` call ensures keys are cleaned up after `2 * window_seconds`.
  Monitor `DBSIZE` and `MEMORY USAGE` if the user base grows to thousands.
- Admin users are NOT exempt in v1. Add an `admin_telegram_ids` config setting
  if this becomes needed — check it in `__call__` before the rate limit logic.
- The middleware creates a Redis client lazily. If Redis is unavailable at
  startup, the first user request will fail. Consider adding a health check or
  making the client creation eager in `__init__`.
