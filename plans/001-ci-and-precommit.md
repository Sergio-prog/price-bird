# Plan 001: Add CI pipeline and pre-commit hooks

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**: `git diff --stat 860c330..HEAD -- .github/ .pre-commit-config.yaml pyproject.toml`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none
- **Category**: dx
- **Planned at**: commit `860c330`, 2026-07-01

## Why this matters

The project has zero automated verification on push or PR. Ruff is configured
in `pyproject.toml` but never enforced. Tests exist but must be run manually.
A CI pipeline gives every change a baseline quality gate — lint passes, tests
pass — before merge. Pre-commit hooks catch formatting and lint issues before
they hit a PR. This plan unblocks all other plans by providing a verification
baseline.

## Current state

- `pyproject.toml:37-42`: Ruff configured with rules `E, F, I, UP, B`, line
  length 128, but no CI or pre-commit integration.
- `pyproject.toml:44-46`: pytest configured with `asyncio_mode = "auto"` and
  `testpaths = ["tests"]`.
- No `.github/` directory exists. No `.pre-commit-config.yaml` exists.
- `uv.lock` is committed (good — reproducible installs).
- Tests run with `uv run pytest tests/`.
- Lint runs with `uv run ruff check app/ tests/`.
- Repo uses conventional commits (seen in `git log`: `feat:`, `chore:`,
  `refactor:`). Branch naming: plain descriptive slugs, no prefix convention
  enforced.

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Install | `uv sync --extra dev` | exit 0 |
| Lint | `uv run ruff check app/ tests/` | exit 0, no output (clean) |
| Lint fix | `uv run ruff check --fix app/ tests/` | exit 0 |
| Format | `uv run ruff format --check app/ tests/` | exit 0, "1 file(s) already formatted" or similar |
| Tests | `uv run pytest tests/ -q` | exit 0, all pass |
| Pre-commit run | `uv run pre-commit run --all-files` | exit 0, all hooks pass |

## Scope

**In scope** (files to create/modify):
- `.github/workflows/ci.yml` — create
- `.pre-commit-config.yaml` — create

**Out of scope** (do NOT touch):
- `pyproject.toml` — Ruff and pytest config are correct, do not change them.
- Any source code under `app/` or `tests/`.
- `Dockerfile` or `docker-compose.yml`.
- CD/deployment pipeline — CI only.
- Test coverage reporting — not needed yet.

## Git workflow

- Branch: `advisor/001-ci-precommit`
- Commits: conventional commits, e.g. `ci: add GitHub Actions workflow` and
  `ci: add pre-commit hooks`.
- Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Add pre-commit configuration

Create `.pre-commit-config.yaml` at the repo root. Use the `ruff-pre-commit`
official hook. The hook should run `ruff check --fix` and `ruff format` on
Python files. No other hooks — keep it minimal.

The file:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

**Verify**: Install pre-commit in the dev environment: `uv run pre-commit` is
not yet available. Instead, check the file exists and is valid YAML:

```bash
uv run python -c "import yaml; yaml.safe_load(open('.pre-commit-config.yaml'))" 2>&1 || echo "yaml not available, manual review needed"
```

If `pyyaml` is not available, just confirm the file is syntactically clean by
eye — the CI step will catch any issues.

### Step 2: Add GitHub Actions CI workflow

Create `.github/workflows/ci.yml`. The workflow triggers on push to any branch
and on PRs to `main`. It must:

1. Check out the repo.
2. Install `uv` using the official `astral-sh/setup-uv` action (v5).
3. Set Python 3.13.
4. Install dependencies with `uv sync --extra dev`.
5. Run `uv run ruff check app/ tests/`.
6. Run `uv run ruff format --check app/ tests/`.
7. Run `uv run pytest tests/ -q`.

The workflow file:

```yaml
name: CI

on:
  push:
    branches: ["*"]
  pull_request:
    branches: [main]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    timeout-minutes: 10

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: price_alerts
          POSTGRES_USER: price_alerts
          POSTGRES_PASSWORD: price_alerts
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:8-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5
        with:
          python-version: "3.13"

      - name: Install dependencies
        run: uv sync --extra dev

      - name: Lint
        run: uv run ruff check app/ tests/

      - name: Format check
        run: uv run ruff format --check app/ tests/

      - name: Test
        run: uv run pytest tests/ -q
        env:
          DATABASE_URL: postgresql+asyncpg://price_alerts:price_alerts@localhost:5432/price_alerts
          REDIS_URL: redis://localhost:6379/0
```

**Verify**: The workflow file exists at `.github/workflows/ci.yml`. No local
command can fully validate GitHub Actions syntax, but check it's valid YAML:

```bash
uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" 2>&1 || echo "manual review needed"
```

Also confirm the file paths referenced in the workflow exist:

```bash
test -f pyproject.toml && echo "pyproject.toml exists"
test -f uv.lock && echo "uv.lock exists"
test -d tests && echo "tests/ exists"
test -d app && echo "app/ exists"
```

### Step 3: Run full local verification

Run the exact checks the CI pipeline will run:

```bash
uv run ruff check app/ tests/
```

Expected: exit 0, no output (already clean per audit).

```bash
uv run ruff format --check app/ tests/
```

Expected: exit 0.

```bash
uv run pytest tests/ -q
```

Expected: exit 0, all existing tests pass.

## Test plan

No new application tests needed — this plan adds infrastructure, not behavior.
The verification is that the CI pipeline runs green when pushed to GitHub.
Manual verification: push the branch, check the Actions tab.

## Done criteria

Machine-checkable. ALL must hold:

- [ ] `.pre-commit-config.yaml` exists and is valid YAML.
- [ ] `.github/workflows/ci.yml` exists and is valid YAML.
- [ ] `uv run ruff check app/ tests/` exits 0.
- [ ] `uv run ruff format --check app/ tests/` exits 0.
- [ ] `uv run pytest tests/ -q` exits 0 with all tests passing.
- [ ] No files outside the in-scope list are modified (`git status`).
- [ ] `plans/README.md` status row updated.

## STOP conditions

Stop and report back if:

- `uv run ruff check app/ tests/` reports lint errors — the codebase has
  drifted since the audit. Fix them with `uv run ruff check --fix app/ tests/`
  first, then proceed.
- `uv run pytest tests/ -q` fails — fix or report before proceeding.
- `uv sync --extra dev` fails — dependency resolution issue.
- Any step's verification command fails twice after a reasonable fix attempt.

## Maintenance notes

- When adding new Ruff rules to `pyproject.toml`, the CI and pre-commit config
  stay in sync automatically since they both invoke `ruff`.
- The CI uses service containers for Postgres and Redis. If tests grow to need
  actual DB access (migrations, integration tests), add an `alembic upgrade
  head` step before the test step.
- The `ruff-pre-commit` rev (`v0.11.0`) should be bumped periodically. Check
  https://github.com/astral-sh/ruff-pre-commit/releases for the latest.
