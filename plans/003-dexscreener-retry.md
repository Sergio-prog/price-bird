# Plan 003: Add retry with backoff to DexScreener provider

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 860c330..HEAD -- app/providers/dexscreener.py app/utils/http.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: plan 002 (session reuse) — this plan assumes `self._session`
  exists. If 002 hasn't landed, apply the retry using a local session.
- **Category**: bug
- **Planned at**: commit `860c330`, 2026-07-01

## Why this matters

DexScreener is the primary token price provider. Unlike Reservoir and OpenSea
(both have retry+backoff in `_get_json`), DexScreener has zero retry logic. A
single transient network error or 429 rate-limit response causes the entire
price refresh to fail for that asset. For a user watching 20 tokens, every
refresh cycle becomes a dice roll. Adding the same retry pattern the other
providers already use eliminates this fragility.

## Current state

`app/providers/dexscreener.py:18-66` — the `DexScreenerProvider` class has
`search_assets` and `get_price`. Neither method retries on failure. Each does
a single `response.raise_for_status()` and propagates any exception.

`app/utils/http.py:1-16` — the `sleep_before_retry` helper, already used by
Reservoir and OpenSea providers. It reads `Retry-After` headers for 429
responses and falls back to exponential backoff (`0.5 * 2^attempt`).

`app/core/config.py:27-28` — `provider_timeout_seconds` (default 10) and
`provider_max_attempts` (default 3) are already configured and used by
Reservoir/OpenSea. DexScreener only uses the timeout, not max attempts.

The Reservoir retry pattern (`reservoir.py:67-92`) is the exemplar to follow:
- Loop `range(settings.provider_max_attempts)`.
- On 429 or 5xx: call `sleep_before_retry`, then `continue`.
- On `ClientError`/`TimeoutError`: sleep with exponential backoff if retries
  remain, else break and re-raise.
- After loop: re-raise the last error or a generic RuntimeError.

Repo conventions:
- Retry helpers live in `app/utils/http.py`.
- Providers are plain classes in `app/providers/`.
- Configuration comes from `app.core.config.settings` (global singleton).

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Install | `uv sync --extra dev` | exit 0 |
| Lint | `uv run ruff check app/` | exit 0, no output |
| Tests | `uv run pytest tests/ -q` | exit 0, all pass |

## Scope

**In scope** (files to modify):
- `app/providers/dexscreener.py` — add retry to `search_assets` and `get_price`

**Out of scope** (do NOT touch):
- `app/utils/http.py` — `sleep_before_retry` is correct as-is.
- `app/providers/reservoir.py`, `app/providers/opensea.py` — their retry
  patterns are fine.
- `app/core/config.py` — settings are correct.
- Any other provider.

## Git workflow

- Branch: `advisor/003-dexscreener-retry`
- Commits: conventional, e.g. `fix: add retry with backoff to DexScreener provider`
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Add retry to `search_assets`

Refactor `search_assets` to wrap the HTTP call in a retry loop matching the
Reservoir pattern. The method currently does:

```python
async def search_assets(self, query: str, *, nft: bool = False) -> list[AssetCandidate]:
    if nft:
        return []
    async with self._session.get(f"{self.base_url}/search", params={"q": query}) as response:
        response.raise_for_status()
        payload = await response.json()
    # ... candidate building from payload
```

After the change — add the retry loop around the HTTP call, keep the candidate
building after:

```python
async def search_assets(self, query: str, *, nft: bool = False) -> list[AssetCandidate]:
    if nft:
        return []
    url = f"{self.base_url}/search"
    params = {"q": query}
    last_error: Exception | None = None
    for attempt in range(settings.provider_max_attempts):
        try:
            async with self._session.get(url, params=params) as response:
                if response.status == 429 or 500 <= response.status < 600:
                    await sleep_before_retry(response, attempt)
                    continue
                response.raise_for_status()
                payload = await response.json()
                break
        except (aiohttp.ClientError, TimeoutError) as exc:
            last_error = exc
            if attempt + 1 >= settings.provider_max_attempts:
                if last_error is not None:
                    raise last_error
                raise RuntimeError(f"DexScreener request failed after {settings.provider_max_attempts} attempts")
            await asyncio.sleep(0.5 * (2 ** attempt))
    else:
        if last_error is not None:
            raise last_error
        raise RuntimeError(f"DexScreener request failed after {settings.provider_max_attempts} attempts")
    # ... existing candidate building code (lines 26-54 unchanged)
```

Note: the `for...else` pattern requires the `break` on success inside the
try block. If the loop exhausts without breaking, the `else` runs and raises.

You'll need to add imports at the top of the file:
- `import asyncio`
- `from app.utils.http import sleep_before_retry`

Existing imports `aiohttp` and `from app.core.config import settings` are
already present.

**Verify**:

```bash
uv run ruff check app/providers/dexscreener.py
```

Expected: exit 0, no output. If ruff reports unused imports, double-check
that `asyncio` and `sleep_before_retry` are actually used.

### Step 2: Add retry to `get_price`

Apply the identical retry pattern to `get_price`. The method currently does:

```python
async def get_price(self, asset: Asset) -> PriceQuote:
    chain, address = asset.provider_asset_id.split(":", 1)
    async with self._session.get(f"{self.base_url}/tokens/{address}") as response:
        response.raise_for_status()
        payload = await response.json()
    # ... pair selection and PriceQuote construction
```

Wrap the HTTP call in the same retry loop structure as step 1. The URL is
`f"{self.base_url}/tokens/{address}"` with no query params.

After the retry loop succeeds, the existing pair-selection logic (`dexscreener.py:62-66`
in the original — finding the best pair by liquidity) stays unchanged.

**Verify**:

```bash
uv run ruff check app/providers/dexscreener.py
```

Expected: exit 0.

### Step 3: Run full verification

```bash
uv run ruff check app/
```

Expected: exit 0.

```bash
uv run pytest tests/ -q
```

Expected: exit 0. No existing tests exercise DexScreener HTTP calls directly,
so this change has no test impact.

## Test plan

No new tests required. The existing test suite doesn't exercise provider HTTP
calls — they're all mocked. If provider integration tests are added later, they
should verify that a transient 503 on attempt 1 succeeds on attempt 2.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `uv run ruff check app/providers/dexscreener.py` exits 0.
- [ ] `uv run ruff check app/` exits 0.
- [ ] `uv run pytest tests/ -q` exits 0.
- [ ] Both `search_assets` and `get_price` in dexscreener.py contain a retry
  loop iterating `range(settings.provider_max_attempts)`.
- [ ] Both methods call `sleep_before_retry` on 429/5xx responses.
- [ ] Both methods use exponential backoff on `ClientError`/`TimeoutError`.
- [ ] No files outside the in-scope list are modified (`git status`).
- [ ] `plans/README.md` status row updated.

## STOP conditions

Stop and report if:

- `app/providers/dexscreener.py` doesn't have `self._session` (plan 002 not
  applied). Fall back: use a local `aiohttp.ClientSession(...)` as context
  manager inside the retry loop instead.
- The `search_assets` or `get_price` method signatures have changed since this
  plan was written.
- `uv run pytest tests/ -q` fails — investigate and fix before proceeding.
- The `sleep_before_retry` import fails because `app/utils/http.py` was
  removed or renamed.

## Maintenance notes

- The retry pattern is now duplicated across three providers (DexScreener,
  Reservoir, OpenSea). A follow-up refactor could extract a shared
  `_retry_get_json(session, url, params, headers)` in `app/utils/http.py`.
  That's intentionally deferred — this plan fixes the bug, not the duplication.
- If `settings.provider_max_attempts` is increased, all three providers
  automatically respect it since they all read the same setting.
