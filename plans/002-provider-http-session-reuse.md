# Plan 002: Reuse HTTP sessions across provider API calls

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 860c330..HEAD -- app/providers/dexscreener.py app/providers/opensea.py app/providers/reservoir.py app/providers/base.py app/utils/http.py`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: perf
- **Planned at**: commit `860c330`, 2026-07-01

## Why this matters

Every provider API call creates a fresh `aiohttp.ClientSession`, tears it down,
and repeats. This means a TCP+TLS handshake per call — multiplied by every
price refresh cycle and every user search. Under any real load (dozens of
watched assets, multiple users), this wastes latency and CPU. A single
session per provider, created once and reused, pools connections and reuses
warm TLS sessions. The fix is a one-line change per call site.

## Current state

Three providers make HTTP calls. Each creates a new `ClientSession` inside the
method body, used for exactly one request:

`app/providers/dexscreener.py:21-22` (search):
```python
async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=settings.provider_timeout_seconds)) as session:
    async with session.get(f"{self.base_url}/search", params={"q": query}) as response:
```

`app/providers/dexscreener.py:58-59` (get_price):
```python
async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=settings.provider_timeout_seconds)) as session:
    async with session.get(f"{self.base_url}/tokens/{address}") as response:
```

`app/providers/reservoir.py:75` (inside `_get_json`):
```python
async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
    for attempt in range(settings.provider_max_attempts):
```

`app/providers/opensea.py:35-43` (inside `_get_json`, similar pattern to Reservoir).

The OpenSea provider also imports `ccxt` lazily inside `_get_eth_usd`
(`opensea.py:103-114`) and creates/destroys an exchange per call. That pattern
is out of scope for this plan (it's a ccxt concern, not aiohttp).

The `PriceProvider` protocol is defined in `app/providers/base.py:33-40`. It
has no lifecycle methods — providers are instantiated once at module load
(`registry.py:14`) and live for the process lifetime. This means a session can
safely be created in `__init__` and reused.

Repo conventions:
- Providers are plain classes (not dataclasses), instantiated in
  `ProviderRegistry.__init__` or `_build_nft_providers`.
- Configuration comes from `app.core.config.settings`.
- Error handling: raise on failure, let callers catch. DexScreener has no
  retry; Reservoir and OpenSea have retry loops in `_get_json`.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Install | `uv sync --extra dev` | exit 0 |
| Lint | `uv run ruff check app/` | exit 0, no output |
| Tests | `uv run pytest tests/ -q` | exit 0, all pass |

## Scope

**In scope** (files to modify):
- `app/providers/dexscreener.py` — add session to `__init__`, use it in `search_assets` and `get_price`
- `app/providers/opensea.py` — add session to `__init__`, use it in `_get_json`
- `app/providers/reservoir.py` — add session to `__init__`, use it in `_get_json`

**Out of scope** (do NOT touch):
- `app/providers/cex.py` — uses ccxt, not aiohttp.
- `app/providers/base.py` — the `PriceProvider` protocol stays unchanged.
- `app/providers/registry.py` — no changes needed; provider instantiation
  already happens once.
- Retry logic changes (DexScreener has no retry — that's plan 003).
- Any test files.

## Git workflow

- Branch: `advisor/002-session-reuse`
- Commits: conventional, e.g. `perf: reuse aiohttp session in providers`
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Add session to DexScreenerProvider

In `app/providers/dexscreener.py`, modify the class:

1. Add `__init__` that creates a `ClientSession` stored as `self._session`.
   Use a class-level timeout. Keep the existing `name` and `base_url` class
   attributes.

2. In `search_assets`, replace the `async with aiohttp.ClientSession(...)`
   context manager with a direct `self._session.get(...)` call. Remove the
   `async with` wrapping the session.

3. In `get_price`, same replacement.

After the change, `DexScreenerProvider` should look approximately like:

```python
class DexScreenerProvider:
    name = "dexscreener"
    base_url = "https://api.dexscreener.com/latest/dex"

    def __init__(self) -> None:
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=settings.provider_timeout_seconds)
        )

    async def search_assets(self, query: str, *, nft: bool = False) -> list[AssetCandidate]:
        if nft:
            return []
        async with self._session.get(f"{self.base_url}/search", params={"q": query}) as response:
            response.raise_for_status()
            payload = await response.json()
        # ... rest unchanged

    async def get_price(self, asset: Asset) -> PriceQuote:
        chain, address = asset.provider_asset_id.split(":", 1)
        async with self._session.get(f"{self.base_url}/tokens/{address}") as response:
            response.raise_for_status()
            payload = await response.json()
        # ... rest unchanged
```

Note: `aiohttp.ClientSession` does not need to be explicitly closed if the
process lifetime matches. For extra safety, add a `close` method, but it's
not required since providers live for the process duration.

**Verify**:

```bash
uv run ruff check app/providers/dexscreener.py
```

Expected: exit 0, no output.

### Step 2: Add session to ReservoirNftProvider and OpenSeaNftProvider

The pattern is slightly different because Reservoir and OpenSea already have
`__init__` methods.

In `app/providers/reservoir.py`:

1. Add `self._session` creation in `__init__`, after the existing `self.api_key`
   assignment. Use a timeout matching the existing pattern:
   `aiohttp.ClientTimeout(total=settings.provider_timeout_seconds)`.

2. In `_get_json`, remove the `async with aiohttp.ClientSession(...)` context
   manager. Use `self._session.get(...)` directly inside the retry loop. The
   headers are already set on the session? No — in the current code, headers
   vary per call. Keep the `headers` kwarg on each `self._session.get(...)`.

After: `_get_json` becomes:

```python
async def _get_json(self, path: str, *, params: dict[str, str]) -> dict[str, Any]:
    headers = {"accept": "application/json"}
    if self.api_key:
        headers["x-api-key"] = self.api_key

    timeout = aiohttp.ClientTimeout(total=settings.provider_timeout_seconds)
    url = f"{self.base_url}{path}"
    last_error: Exception | None = None
    for attempt in range(settings.provider_max_attempts):
        try:
            async with self._session.get(url, params=params, headers=headers, timeout=timeout) as response:
                if response.status == 429 or 500 <= response.status < 600:
                    await sleep_before_retry(response, attempt)
                    continue
                response.raise_for_status()
                return await response.json()
        except (aiohttp.ClientError, TimeoutError) as exc:
            last_error = exc
            if attempt + 1 >= settings.provider_max_attempts:
                break
            await asyncio.sleep(0.5 * (2 ** attempt))

    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Reservoir request failed after {settings.provider_max_attempts} attempts")
```

Note: `timeout` is passed per-request as a kwarg to `session.get()` since
aiohttp allows per-request timeout overrides. The session-level timeout set
in `__init__` is no longer needed — or keep it as the default and override
per-request.

Apply the identical pattern to `app/providers/opensea.py`'s `_get_json` method
(steps 79-101 in the current file). The OpenSea provider also uses headers with
`x-api-key`.

**Verify**:

```bash
uv run ruff check app/providers/reservoir.py app/providers/opensea.py
```

Expected: exit 0, no output.

### Step 3: Run full verification

```bash
uv run ruff check app/
```

Expected: exit 0.

```bash
uv run pytest tests/ -q
```

Expected: exit 0, all existing tests pass. (No provider tests exist that mock
the HTTP layer, so session reuse has no test impact.)

## Test plan

No new tests needed. The existing test suite doesn't exercise provider HTTP
calls — they're all mocked via monkeypatch or use SimpleNamespace stubs. If
provider integration tests are added later, they should verify that multiple
calls reuse the same session (check connection count or session identity).

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `uv run ruff check app/providers/dexscreener.py app/providers/opensea.py app/providers/reservoir.py` exits 0.
- [ ] `uv run ruff check app/` exits 0.
- [ ] `uv run pytest tests/ -q` exits 0.
- [ ] In all three provider files, `aiohttp.ClientSession(` appears exactly
  once — in `__init__`.
- [ ] No files outside the in-scope list are modified (`git status`).
- [ ] `plans/README.md` status row updated.

## STOP conditions

Stop and report if:

- A provider's `__init__` signature has changed since this plan was written
  (e.g., new parameters added). The session line should be added at the end of
  `__init__`.
- `uv run pytest tests/ -q` fails after the changes — tests may have been
  added that mock `aiohttp.ClientSession` construction. Adjust mocks to target
  `self._session.get` instead.
- The `_get_json` method shape in reservoir.py or opensea.py doesn't match
  the excerpts above — the codebase drifted.

## Maintenance notes

- If a provider ever needs custom headers per-session (not per-request), set
  them on `self._session` via `self._session.headers.update(...)` in
  `__init__`. Per-request headers are fine as kwargs.
- The session is never explicitly closed. For a long-running process this is
  acceptable — aiohttp sessions close on GC. If graceful shutdown is added
  later, call `await self._session.close()` in a `close()` method on each
  provider and iterate providers in the worker shutdown path.
- Plan 003 (DexScreener retry) builds on this change — it will wrap the
  `self._session.get()` call in a retry loop.
