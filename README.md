# Telegram Price Alerts

Async Telegram bot for token, NFT floor, and CEX price alerts.

## Local setup

1. Copy `.env.example` to your real env file and fill `BOT_TOKEN`.
2. Start services: `docker compose up -d postgres redis`.
3. Install dependencies: `uv sync --extra dev`.
4. Run migrations: `uv run alembic upgrade head`.
5. Create first admin:

```bash
uv run price-alert-cli create-admin --telegram-id 123456789 --username your_username
```

6. Run bot in polling mode:

```bash
uv run price-alert-bot
```

7. Run worker separately:

```bash
uv run price-alert-worker
```

## Core idea

Alerts are grouped by watched asset. The worker refreshes each active asset once per interval,
stores the snapshot, evaluates all active alerts for that asset, and queues Telegram notifications.

NFT collection floors are provider-backed. Use `NFT_PROVIDERS=opensea,reservoir` for fallback,
or set a single value like `NFT_PROVIDERS=opensea` if you want exactly one provider.

## Bot commands

- `/alert BTC 10%` - create a quick alert.
- `/newalert` - create an alert with inline keyboards.
- `/alerts` - list active alerts with delete buttons.
- `/deletealert 123` - delete an active alert by ID.
- `/cancel` - cancel the current alert wizard.
