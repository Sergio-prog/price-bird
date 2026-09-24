# Price Bird

Async Telegram bot for token, CEX pair, market-cap, and NFT floor alerts.

The production assets are in `assets/brand`. The release checklist is in [`docs/production-release.md`](docs/production-release.md).

Production: [price-alerts-tg.serhiifotex.dev](https://price-alerts-tg.serhiifotex.dev). The built-in Trenchbook integration targets [trenches.serhiifotex.dev](https://trenches.serhiifotex.dev).

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

Alerts are grouped by watched asset. Every `PRICE_REFRESH_INTERVAL_SECONDS` the worker loads the active assets,
groups them by provider and fetches prices in batches: one Binance ticker call covers 20 pairs and one DexScreener
call covers 30 tokens. NFT floors refresh every `NFT_REFRESH_INTERVAL_SECONDS` instead. Each provider runs behind
a client-side token bucket and pauses itself on 429/418 responses, so a rate limit delays that provider's alerts
instead of banning the server IP. Budgets and the published limits are in
[`docs/provider-rate-limits.md`](docs/provider-rate-limits.md). All active alerts for the asset are evaluated against
each quote; a price snapshot is stored only when an alert triggers, and notifications are queued.

Search queries Hyperliquid (spot and perps), Binance and DexScreener in parallel, ranks exact ticker matches by 24h volume and
collapses DEX pools into one entry per token, which tracks the token's deepest pool. Pasting a pool address tracks
that pool instead. A single match is selected without showing the list. Pasting an NFT contract address resolves it to its OpenSea collection.

NFT collection floors are provider-backed. OpenSea is the default (`NFT_PROVIDERS=opensea`);
add `reservoir` only if you have a working Reservoir API.
OpenSea collection search needs a valid `OPENSEA_API_KEY`; keys expire, and an expired key makes
NFT search fall back to exact collection slugs only (for example `milady`, `pudgypenguins`).
Floor price polling works without a key.

## Bot commands

- `/alert BTC 10%` - create a quick alert.
- `/newalert` - create an alert with inline keyboards.
- `/alerts` - list active alerts with delete buttons.
- `/deletealert 123` - delete an active alert by ID.
- `/cancel` - cancel the current alert wizard.
- `/language` - switch between English, Ukrainian and Russian.

## Languages

The bot speaks English, Ukrainian and Russian. It uses the language picked in `/language` or Settings, then the Telegram client language, then English. Strings live in `app/i18n/locales/*.ftl` ([Fluent](https://projectfluent.org/)). Every locale must define the same messages with the same variables; `tests/test_i18n.py` enforces it. After changing command descriptions or profile copy, run `uv run price-alert-cli sync-commands` and `uv run price-alert-cli sync-profile` to publish every language.

## Alert limits

Limits live in Postgres and apply per alert kind: `token` covers DEX tokens and CEX pairs, `nft` covers NFT collections. Active and paused alerts count toward them.

`alert_limits` has one row per kind. The migration seeds these values from provider rate limits at the old 45-second refresh interval; batching keeps them within budget at the 10-second default:

| Column | token | nft | Meaning |
|---|---|---|---|
| `max_watched_assets` | 200 | 5 | Distinct assets polled per refresh. Binance allows about 200 single-symbol tickers and DexScreener about 225 tokens per tick; the free OpenSea key covers about 7 collections. |
| `max_active_alerts` | 5000 | 500 | Alerts across all users. |
| `default_user_max_alerts` | 20 | 5 | Per-user limit when the user has no override. |

A new alert on an asset that is already watched adds no provider requests, so it skips the watched-asset check. `user_alert_limits` stores per-user overrides:

```bash
uv run price-alert-cli set-alert-limit --kind nft --max-watched-assets 20
uv run price-alert-cli set-user-alert-limit --telegram-id 123456789 --kind token --max-alerts 50
uv run price-alert-cli set-user-alert-limit --telegram-id 123456789 --kind token
```

The last command removes the override and restores the default.

## Connected apps and notification settings

Price Bird is the only place to create and manage alerts. `/settings` controls Telegram delivery, a per-user fixed UTC offset, local quiet hours, and the preferred coin link for every active user. Quiet hours default to off and deliver alerts without sound rather than delaying them. Coin links can use TradingView, DexScreener, GMGN, Fomo Trade, or CoinMarketCap. The provider source link remains in the alert when it differs from the preferred link.

Built-in integrations and custom webhooks are admin-only by default. Set `PUBLIC_INTEGRATIONS_ENABLED=true` or `PUBLIC_CUSTOM_WEBHOOKS_ENABLED=true` only when those features are ready for every active user. The delivery worker checks the same policy before every send, so hidden or old connections cannot bypass it. Disabling a destination cancels its pending deliveries; a request already in flight can still finish. Alert evaluation continues. `/alerts` lets you pause individual alerts, edit their threshold/note, change percentage direction, choose once or repeating crossings, set cooldown, or expire an alert in seven days.

Registration remains allowlist-only while `PUBLIC_ACCESS_ENABLED=false`. Set it to `true` for public launch. New users and previously pending users become active when they send `/start`; suspended users remain blocked.

Price and market-cap thresholds accept `100k`, `23m`, `1b`, `1t` shortcuts, scientific notation (`1e-6`), DexScreener-style zero counts (`0.0₄5` or `0.0{4}5` = `0.00005`) and an optional unit (`$0.023`, `1.2 ETH`).
Breakout alerts watch price by default; add `mc` (`> 17m mc`) or pick Market cap in the wizard to watch market cap instead.
Percent alerts accept `+5%` for pumps only and `-5%` for dumps only. New alerts use a 1-minute cooldown; the wizard cycles 1m, 5m, 15m and 1h.

Messages show chain and DEX logos as Telegram custom emoji from the BasedBot logo packs. Telegram renders them only when the bot owner has Telegram Premium; otherwise the plain emoji fallback is shown. Set `CUSTOM_EMOJI_ENABLED=false` to always send the plain emoji.
Assets quoted in a native currency (NFT floors, DEX pairs against ETH/SOL/BNB) can use that currency instead of USD;
NFT floor thresholds default to the native currency, everything else defaults to USD.

Repeating percentage and absolute-change alerts move their baseline to the trigger price, so the next notification needs another full move from there. Repeating price and market-cap alerts rearm after the condition becomes false and do not notify again while the price stays beyond the threshold. Price and percentage baselines use real quotes. Market-cap alerts use actual market cap, never FDV. Missing prices or metrics do not trigger or rearm an alert.

Built-in integration definitions live in Postgres. Each definition owns its display name, base URL, webhook path, enabled state and encrypted receiver secret. The application environment contains only `INTEGRATION_SECRETS_KEY`, the master encryption key. Keep that key stable and backed up; losing it makes existing integration secrets unreadable.

After migrating, create the Trenchbook definition and its signing secret:

```bash
# Run once locally and save the result as INTEGRATION_SECRETS_KEY in Price Bird's environment.
uv run price-alert-cli generate-integration-key

# After restarting with that key, create the database definition.
uv run price-alert-cli configure-trenchbook-integration
```

The second command prints `PRICEBIRD_WEBHOOK_SECRET` only when it creates or rotates the secret. Copy that value into Trenchbook, set `PRICEBIRD_BOT_USERNAME` there, then choose Connect Trenchbook in Price Bird Settings and send a test. Use the same Telegram account in both bots and start Trenchbook first. Its allowlist still applies. The production receiver is `https://trenches.serhiifotex.dev/integrations/pricebird/webhook`; pass `--base-url` when installing a different Trenchbook deployment.

To rotate the built-in secret, run `uv run price-alert-cli configure-trenchbook-integration --rotate-secret`. Rotation disables existing Trenchbook connections until the receiver has the new value and the user enables the connection again.

For custom apps, add a name and public HTTPS URL in Settings. Price Bird creates a unique random signing secret, encrypts it in Postgres and shows the plaintext once. Configure the receiver with that value, then enable the connection. Rotating a custom secret also pauses delivery and cancels pending requests until the receiver is updated.

The built-in Trenchbook secret is shared because it authenticates one operator-controlled Trenchbook deployment. If Price Bird later supports third-party Trenchbook installations, credentials should move to a separate installation record so every deployment gets its own endpoint and secret.

Webhooks use HTTPS on port 443. Private/reserved addresses, embedded credentials and redirects are blocked. URLs cannot be edited in place; disconnect and create a new connection instead, so old private events cannot be silently rerouted.

## Webhook contract

Price Bird sends JSON with `schema_version: 1`, `type`, a stable `event_id`, `connection_id`, `occurred_at` and `recipient_telegram_id`. An `alert.triggered` event also includes `alert_id`, `note`, asset identity, rule/threshold/baseline, the measured observation/source and trigger direction/change. Decimal values are strings. `connection.test` has only the envelope. Provider raw responses, wallet balances and trade history are not sent.

Verify these headers before parsing the JSON:

- `X-PriceBird-Timestamp` is Unix seconds for this attempt. Reject attempts more than five minutes from your clock.
- `X-PriceBird-Delivery-Id` stays the same on retries.
- `X-PriceBird-Event-Id` must match the body.
- `X-PriceBird-Signature` is `v1=` followed by the hex HMAC-SHA256 of `timestamp + "." + delivery_id + "." + raw_body`, using the connection secret. Compare in constant time.

Store the event id uniquely before returning 2xx. Delivery is at least once; receivers must deduplicate. Trenchbook does this using a durable inbox and sends without an AI call. Test vectors live in `tests/test_delivery.py` and Trenchbook's `agent/lib/pricebird/receiver.test.ts`.

Each destination has its own Postgres delivery record, lease and retry state. Worker restarts do not lose events. Timeouts, 408/429 and 5xx retry with backoff, up to 12 attempts within 24 hours. Other failures become terminal. Settings shows the latest delivery and permits retry of a recent failed webhook. Telegram failures remain in the `deliveries` table for operator inspection. Redis holds the per-provider refresh locks and NFT refresh timers; it no longer carries notification delivery.

## Upgrading

Run `uv run alembic upgrade head` before starting the updated bot and worker. Stop old workers first so only the new delivery path runs. The migration widens price precision and preserves existing alerts. Existing percentage alerts become repeating crossings with a 15-minute cooldown, so a sustained move no longer sends every refresh. Untouched legacy queued events move to the new delivery queue; previously attempted legacy sends are retained as failed for review rather than automatically replayed. Existing connected apps are disabled because their environment-derived secrets cannot be migrated; run the Trenchbook configuration command or reconnect custom webhooks. A crash after a successful Telegram send but before recording it can still result in a duplicate.

Trenchbook's old limit records are preserved but no longer evaluate after its cutover. Recreate desired alerts in Price Bird before deploying Trenchbook's change. Position-relative targets, rolling-window moves, trailing rules and automatic migration of wallet-based alerts are not included in this release.

## CI checks

Run `uv sync --locked --extra dev`, then `sh scripts/check.sh` for Ruff lint, formatting and pytest. GitHub Actions runs these checks on pull requests and pushes to `main`, along with conventional branch/PR/commit names and Alembic migration/model checks against a fresh PostgreSQL 16 database. PR checks include title edits and support stacked branches.

## Continuous deployment

After both CI jobs pass on a push to `main`, the `Publish to VPS` job connects over SSH and runs `deploy/update.sh`. The script fast-forwards the VPS checkout, builds the application images, applies migrations, restarts the bot and worker, and checks that both containers stay running.

Configure these repository secrets:

- `DEPLOY_HOST`: VPS hostname or IP address.
- `DEPLOY_USER`: SSH user that owns the checkout and can run Docker Compose.
- `DEPLOY_SSH_KEY`: private SSH key authorized for that user.
- `DEPLOY_PORT`: optional SSH port, defaults to `22`.
- `DEPLOY_PATH`: optional checkout path, defaults to `/opt/price-bird`.

The VPS checkout must have its production `.env`, an `origin` remote pointing to this repository, and Docker with the Compose plugin. The deployment job skips with a notice until the three required connection secrets exist. Production environment protection rules can require approval before the job starts.
