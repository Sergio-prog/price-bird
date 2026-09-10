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

## Docker Compose deploy

1. Copy `.env.example` to `.env` and fill production values.
2. Use strong `POSTGRES_PASSWORD`, `BOT_TOKEN`, and provider API keys.
3. Start the stack:

```bash
docker compose up -d --build
```

Compose builds one app image and runs three app services:

- `migrate` runs `alembic upgrade head` once before the app starts.
- `bot` runs the Telegram bot.
- `worker` refreshes prices and sends notifications.

Set `DATABASE_URL` and `REDIS_URL` in `.env` to your production Postgres and Redis endpoints.
The Compose file includes optional Postgres and Redis services under the `infra` profile, but app services do not depend on them.
The webhook port binds to `127.0.0.1` by default; put a reverse proxy in front of the bot for webhook mode.

To run bundled infra on the same server:

```bash
docker compose --profile infra up -d --build
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

## Connected apps and notification settings

Price Bird is the only place to create and manage alerts. `/settings` controls where notifications go. Enable Price Bird, Trenchbook, custom webhooks, or several destinations. Disabling a destination cancels its pending deliveries; a request already in flight can still finish. Alert evaluation continues. `/alerts` lets you pause individual alerts, edit their threshold/note, change percentage direction, choose once or repeating crossings, set cooldown, or expire an alert in seven days.

Repeated alerts rearm after the condition becomes false. They do not repeatedly notify while a price stays beyond its threshold. Price and percentage baselines use real quotes. Market-cap alerts use actual market cap, never FDV. Missing prices or metrics do not trigger or rearm an alert.

To connect Trenchbook, configure:

- `TRENCHBOOK_WEBHOOK_URL=https://your-trenchbook-host/integrations/pricebird/webhook`
- `TRENCHBOOK_WEBHOOK_SECRET`, a random secret of at least 32 characters, shared with Trenchbook's `PRICEBIRD_WEBHOOK_SECRET`.
- In Trenchbook, `PRICEBIRD_BOT_USERNAME` points to this bot. Use the same Telegram user account in both bots and start Trenchbook first. Its allowlist still applies.

Then choose Connect Trenchbook in Settings and send a test. The test is explicitly labelled and contains no invented market data. Trenchbook notifications go to the linked user's private Telegram chat.

For custom apps, set `WEBHOOK_SIGNING_KEY` to a random secret of at least 32 characters. Keep it stable and backed up. Price Bird derives each connection's signing secret from this key and its unique id/version, so no raw per-connection secrets are stored in the database. Add a name and public HTTPS URL in Settings, configure the receiver with the displayed secret, then enable the connection. Rotation pauses delivery and cancels old pending requests until the receiver is updated.

Webhooks use HTTPS on port 443. Private/reserved addresses, embedded credentials and redirects are blocked. URLs cannot be edited in place; disconnect and create a new connection instead, so old private events cannot be silently rerouted.

## Webhook contract

Price Bird sends JSON with `schema_version: 1`, `type`, a stable `event_id`, `connection_id`, `occurred_at` and `recipient_telegram_id`. An `alert.triggered` event also includes `alert_id`, `note`, asset identity, rule/threshold/baseline, the measured observation/source and trigger direction/change. Decimal values are strings. `connection.test` has only the envelope. Provider raw responses, wallet balances and trade history are not sent.

Verify these headers before parsing the JSON:

- `X-PriceBird-Timestamp` is Unix seconds for this attempt. Reject attempts more than five minutes from your clock.
- `X-PriceBird-Delivery-Id` stays the same on retries.
- `X-PriceBird-Event-Id` must match the body.
- `X-PriceBird-Signature` is `v1=` followed by the hex HMAC-SHA256 of `timestamp + "." + delivery_id + "." + raw_body`, using the connection secret. Compare in constant time.

Store the event id uniquely before returning 2xx. Delivery is at least once; receivers must deduplicate. Trenchbook does this using a durable inbox and sends without an AI call. Test vectors live in `tests/test_delivery.py` and Trenchbook's `agent/lib/pricebird/receiver.test.ts`.

Each destination has its own Postgres delivery record, lease and retry state. Worker restarts do not lose events. Timeouts, 408/429 and 5xx retry with backoff, up to 12 attempts within 24 hours. Other failures become terminal. Settings shows the latest delivery and permits retry of a recent failed webhook. Telegram failures remain in the `deliveries` table for operator inspection. Redis still schedules price refreshes; it no longer carries notification delivery.

## Upgrading

Run `uv run alembic upgrade head` before starting the updated bot and worker. Stop old workers first so only the new delivery path runs. The migration widens price precision and preserves existing alerts. Existing percentage alerts become repeating crossings with a 15-minute cooldown, so a sustained move no longer sends every refresh. Untouched legacy queued events move to the new delivery queue; previously attempted legacy sends are retained as failed for review rather than automatically replayed. A crash after a successful Telegram send but before recording it can still result in a duplicate.

Trenchbook's old limit records are preserved but no longer evaluate after its cutover. Recreate desired alerts in Price Bird before deploying Trenchbook's change. Position-relative targets, rolling-window moves, trailing rules and automatic migration of wallet-based alerts are not included in this release.
