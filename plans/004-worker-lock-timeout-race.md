# Plan 004: Fix worker refresh lock timeout race

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 860c330..HEAD -- app/worker.py app/core/config.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `860c330`, 2026-07-01

## Why this matters

The refresh worker uses a Redis lock to prevent concurrent processing of the
same asset. The lock timeout is set to `settings.price_refresh_interval_seconds`
(default 45s). If a provider call takes longer than this (e.g., Reservoir API
is slow and retries 3 times with backoff), the lock expires before the refresh
completes. The scheduler (running in the same process) enqueues the asset again
at the next interval, and a second refresh can acquire the lock — two
concurrent refreshes for the same asset, producing duplicate snapshots and
double notifications. The fix: set the lock timeout to a value independent of
the scheduling interval, large enough to cover worst-case provider latency.

## Current state

`app/worker.py:49-95` — `process_refreshes` loop:

```python
async def process_refreshes() -> None:
    client = get_redis()
    ...
    while True:
        asset_id = await dequeue_asset_refresh(client)
        if asset_id is None:
            await asyncio.sleep(1)
            continue
        lock = client.lock(f"lock:asset_refresh:{asset_id}", timeout=settings.price_refresh_interval_seconds)
        if not await lock.acquire(blocking=False):
            ...
            continue
        try:
            async with SessionLocal() as session:
                ...  # fetch asset, refresh_and_evaluate_asset, commit
        finally:
            await lock.release()
```

Line 58 is the problem: `timeout=settings.price_refresh_interval_seconds`.

`app/core/config.py:26`:
```python
price_refresh_interval_seconds: int = Field(default=45, alias="PRICE_REFRESH_INTERVAL_SECONDS")
```

`app/core/config.py:27-28`:
```python
provider_timeout_seconds: int = Field(default=10, alias="PROVIDER_TIMEOUT_SECONDS")
provider_max_attempts: int = Field(default=3, alias="PROVIDER_MAX_ATTEMPTS")
```

Worst-case provider latency: `provider_timeout_seconds` (10s) ×
`provider_max_attempts` (3) = 30s for one provider. With NFT provider
fallback (OpenSea fails → Reservoir tries), double that: ~60s. This exceeds
the 45s lock timeout.

`app/worker.py:27-46` — the scheduler runs in the same `asyncio.gather` as
`process_refreshes`. It enqueues every `price_refresh_interval_seconds` (45s),
so a lock that expires at 45s will be re-acquired by a fresh dequeue at ~45s.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Install | `uv sync --extra dev` | exit 0 |
| Lint | `uv run ruff check app/` | exit 0, no output |
| Tests | `uv run pytest tests/ -q` | exit 0, all pass |

## Scope

**In scope** (files to modify):
- `app/core/config.py` — add `worker_lock_timeout_seconds` setting
- `app/worker.py` — use the new setting for the lock timeout
- `docker-compose.yml` — add the new env var (optional, with sensible default)
- `.env.example` — add the new env var

**Out of scope** (do NOT touch):
- `app/utils/redis.py` — the `get_redis` helper is fine.
- `app/utils/queues.py` — queue operations are fine.
- The scheduler logic in `worker.py:27-46`.
- Any other files.

## Git workflow

- Branch: `advisor/004-lock-timeout`
- Commits: conventional, e.g. `fix: use dedicated lock timeout in worker, not refresh interval`
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Add `worker_lock_timeout_seconds` to Settings

In `app/core/config.py`, add a new field after the existing provider settings
(line 28 area):

```python
worker_lock_timeout_seconds: int = Field(default=120, alias="WORKER_LOCK_TIMEOUT_SECONDS")
```

Rationale for default 120s: covers worst case of 2 NFT providers × 3 attempts
× 10s timeout = 60s, with 2x safety margin. Operators can tune it.

**Verify**:

```bash
uv run python -c "from app.core.config import settings; print(settings.worker_lock_timeout_seconds)"
```

Expected: `120`.

### Step 2: Use the new setting in the worker

In `app/worker.py`, line 58, change:

```python
lock = client.lock(f"lock:asset_refresh:{asset_id}", timeout=settings.price_refresh_interval_seconds)
```

to:

```python
lock = client.lock(f"lock:asset_refresh:{asset_id}", timeout=settings.worker_lock_timeout_seconds)
```

**Verify**:

```bash
grep "lock:asset_refresh" app/worker.py
```

Expected: shows one line with `settings.worker_lock_timeout_seconds`.

### Step 3: Add the env var to .env.example and docker-compose.yml

In `.env.example`, after the `NOTIFICATION_MAX_ATTEMPTS` line, add:

```
WORKER_LOCK_TIMEOUT_SECONDS=120
```

In `docker-compose.yml`, in the `x-app-environment` anchor (after
`NOTIFICATION_MAX_ATTEMPTS`), add:

```yaml
WORKER_LOCK_TIMEOUT_SECONDS: ${WORKER_LOCK_TIMEOUT_SECONDS:-120}
```

**Verify**:

```bash
grep WORKER_LOCK_TIMEOUT_SECONDS .env.example docker-compose.yml
```

Expected: one match in each file.

### Step 4: Run full verification

```bash
uv run ruff check app/
```

Expected: exit 0.

```bash
uv run pytest tests/ -q
```

Expected: exit 0, all tests pass.

## Test plan

No new tests needed. The lock timeout is a Redis-level concern not unit-testable
without a real Redis instance. The existing tests don't cover the worker loop.
Manual integration test (optional): set `WORKER_LOCK_TIMEOUT_SECONDS=5` and
verify a lock auto-expires after 5 seconds using `redis-cli TTL`.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `app/core/config.py` has `worker_lock_timeout_seconds` with default 120.
- [ ] `app/worker.py:58` references `settings.worker_lock_timeout_seconds`.
- [ ] `app/worker.py` nowhere references `settings.price_refresh_interval_seconds`
  in a lock context (grep confirms only the new setting is used).
- [ ] `.env.example` and `docker-compose.yml` have the new env var.
- [ ] `uv run ruff check app/` exits 0.
- [ ] `uv run pytest tests/ -q` exits 0.
- [ ] No files outside the in-scope list are modified (`git status`).
- [ ] `plans/README.md` status row updated.

## STOP conditions

Stop and report if:

- The lock acquisition line in `worker.py` doesn't match the pattern shown
  (the codebase drifted).
- `uv run pytest tests/ -q` fails.
- `settings.worker_lock_timeout_seconds` doesn't resolve after the config
  change — check for typos in the field name or alias.

## Maintenance notes

- The lock timeout is intentionally decoupled from the refresh interval.
  Changing `PRICE_REFRESH_INTERVAL_SECONDS` no longer risks lock expiry.
- If providers are added that are slower than the current worst case, bump
  `WORKER_LOCK_TIMEOUT_SECONDS` in production config.
- The lock key format (`lock:asset_refresh:{asset_id}`) is unchanged, so
  existing Redis locks are compatible.
