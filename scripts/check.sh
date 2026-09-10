#!/usr/bin/env sh
set -eu
uv run --no-sync ruff check app tests alembic
uv run --no-sync ruff format --check app tests alembic
uv run --no-sync pytest
