# Plan 005: Re-enqueue notifications on transient failure

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 860c330..HEAD -- app/worker.py app/notifications.py app/utils/queues.py`
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

The notification pipeline has a critical gap: when `send_alert_notification`
fails (e.g., Telegram API is temporarily down, user blocked the bot), the
event's `notification_attempts` counter is incremented and the status is set
to `FAILED` if max attempts reached — but the event is **never re-enqueued**
for a retry. It falls into a black hole. The worker's `process_notifications`
loop dequeues the event ID, tries once, and moves on regardless of outcome.
Users miss alerts whenever Telegram has a hiccup. The fix: re-enqueue the
event ID when the failure is transient (attempts < max), so the worker retries
on the next loop iteration.

## Current state

`app/worker.py:98-131` — `process_notifications` loop:

```python
async def process_notifications() -> None:
    client = get_redis()
    bot = Bot(settings.bot_token)
    ...
    while True:
        event_id = await dequeue_notification(client)
        if event_id is None:
            await asyncio.sleep(1)
            continue
        async with SessionLocal() as session:
            event = await session.scalar(
                select(AlertEvent)
                .where(AlertEvent.id == event_id)
                .options(...)
            )
            if event is None:
                ...
                continue
            try:
                await send_alert_notification(session, bot, event)
            except Exception:
                logger.exception("Failed to send notification for event %s", event_id)
            await session.commit()
```

The `except` block on line 124-125 logs and swallows the error. It does NOT
re-enqueue. The event stays in whatever state `send_alert_notification` left it
(QUEUED if attempts < max, FAILED if attempts == max), but nobody picks it up
again because it was already popped from the Redis queue.

`app/notifications.py:50-80` — `send_alert_notification`:

```python
async def send_alert_notification(session: AsyncSession, bot: Bot, event: AlertEvent) -> None:
    try:
        await bot.send_message(...)
    except Exception:
        attempts = event.notification_attempts + 1
        status = (
            NotificationStatus.FAILED.value
            if attempts >= settings.notification_max_attempts
            else NotificationStatus.QUEUED.value
        )
        await session.execute(
            update(AlertEvent)
            .where(AlertEvent.id == event.id)
            .values(notification_attempts=attempts, notification_status=status)
        )
        raise  # <-- re-raises, caught by process_notifications
    else:
        ...  # mark SENT
```

So when `send_alert_notification` raises, the event's status is already
updated to QUEUED (if retries remain) or FAILED (if exhausted). The caller
just needs to check and re-enqueue.

`app/utils/queues.py:22-30`:

```python
async def enqueue_notification(client: redis.Redis, event_id: int) -> None:
    await client.lpush(NOTIFICATION_QUEUE, json.dumps({"event_id": event_id}))
```

This is already available. The fix: call `enqueue_notification` from the
`except` block when the event still has retries left.

Repo conventions:
- `settings.notification_max_attempts` (default 5) controls the retry budget.
- `NotificationStatus` enum: QUEUED, SENT, FAILED.
- Worker uses `SessionLocal` for DB access, `get_redis()` for Redis.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Install | `uv sync --extra dev` | exit 0 |
| Lint | `uv run ruff check app/` | exit 0, no output |
| Tests | `uv run pytest tests/ -q` | exit 0, all pass |

## Scope

**In scope** (files to modify):
- `app/worker.py` — add re-enqueue logic in `process_notifications` except block

**Out of scope** (do NOT touch):
- `app/notifications.py` — `send_alert_notification` correctly updates status
  and re-raises. No changes needed.
- `app/utils/queues.py` — `enqueue_notification` is correct.
- `app/db/repositories/events.py` — no changes needed.
- Any other files.

## Git workflow

- Branch: `advisor/005-notification-reenqueue`
- Commits: conventional, e.g. `fix: re-enqueue notifications on transient failure`
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Re-enqueue on transient failure in process_notifications

In `app/worker.py`, modify the `except` block inside `process_notifications`
(lines 124-125). After catching the exception, check whether the event still
has retries left. If so, re-enqueue it.

The current block:

```python
try:
    await send_alert_notification(session, bot, event)
except Exception:
    logger.exception("Failed to send notification for event %s", event_id)
```

Replace with:

```python
try:
    await send_alert_notification(session, bot, event)
except Exception:
    logger.exception("Failed to send notification for event %s", event_id)
    if event.notification_attempts < settings.notification_max_attempts:
        await enqueue_notification(client, event_id)
        logger.info(
            "Re-queued notification; event_id=%s attempt=%s/%s",
            event_id,
            event.notification_attempts,
            settings.notification_max_attempts,
        )
```

The condition uses `<` (strict less-than) because `send_alert_notification`
already incremented `notification_attempts` before re-raising. If attempts
reached `notification_max_attempts`, the status is already FAILED and we
should NOT re-enqueue — the event is dead.

The `client` variable is already in scope from line 99.

**Verify**:

```bash
grep -A 5 "except Exception:" app/worker.py | head -20
```

Expected: shows the new `enqueue_notification` call inside the except block.

### Step 2: Run full verification

```bash
uv run ruff check app/worker.py
```

Expected: exit 0.

```bash
uv run ruff check app/
```

Expected: exit 0.

```bash
uv run pytest tests/ -q
```

Expected: exit 0, all tests pass. The worker loop is not unit-tested, so
this change has no test impact.

## Test plan

No new tests required — the worker loop has no existing unit tests and adding
them requires Redis mocking infrastructure beyond this plan's scope. The change
is straightforward enough to verify by code review.

Optional manual smoke test (not required for done criteria):
1. Set `NOTIFICATION_MAX_ATTEMPTS=3` and point `BOT_TOKEN` at an invalid token.
2. Trigger an alert — it will fail to send.
3. Check Redis: `LLEN queue:notifications` should show the event re-enqueued.
4. After 3 cycles, the event should be marked FAILED and not re-enqueued.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `app/worker.py` contains `enqueue_notification(client, event_id)` inside
  the `except Exception` block of `process_notifications`.
- [ ] The re-enqueue is guarded by `event.notification_attempts <
  settings.notification_max_attempts`.
- [ ] A log line at INFO level records the re-enqueue with attempt count.
- [ ] `uv run ruff check app/` exits 0.
- [ ] `uv run pytest tests/ -q` exits 0.
- [ ] No files outside the in-scope list are modified (`git status`).
- [ ] `plans/README.md` status row updated.

## STOP conditions

Stop and report if:

- The `process_notifications` function shape has changed significantly (e.g.,
  `client` is no longer in scope at the except block).
- `enqueue_notification` import is missing — add `from app.utils.queues import
  enqueue_notification` to the worker imports.
- `uv run pytest tests/ -q` fails.
- The `send_alert_notification` function behavior has changed — specifically,
  if it no longer increments `notification_attempts` before re-raising.

## Maintenance notes

- The re-enqueue is immediate (no delay). This is intentional — the worker
  loop already has a 1-second sleep when the queue is empty, providing natural
  backoff between retries if the queue is otherwise idle. Under load, the
  event just goes to the back of the line.
- If notification volume grows, consider adding a dedicated dead-letter queue
  or a retry queue with explicit delay (`enqueue_notification_delayed`). That's
  a future optimization, not needed now.
- The `notification_max_attempts` setting controls both the DB status update
  (in `send_alert_notification`) and the re-enqueue guard (in the worker).
  Keep them consistent — both read the same setting.
