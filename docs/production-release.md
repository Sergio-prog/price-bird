# Production release checklist

## Before launch

1. Create and back up strong values for `POSTGRES_PASSWORD`, `BOT_TOKEN`, `WEBHOOK_SECRET`, and `INTEGRATION_SECRETS_KEY`.
2. Run `uv sync --locked --extra dev` and `sh scripts/check.sh`.
3. Run `uv run alembic upgrade head` against the production database before starting the bot and worker.
4. Create the first admin with `uv run price-alert-cli create-admin --telegram-id <id>`.
5. Set `BOT_MODE=webhook`, use an HTTPS origin in `WEBHOOK_BASE_URL`, set a random `WEBHOOK_SECRET`, and keep the app port bound to `127.0.0.1` behind the reverse proxy. The app rejects an incomplete webhook configuration at startup.
6. Set `PUBLIC_ACCESS_ENABLED=true` only when registration should open. Suspended users stay suspended.
7. Keep `PUBLIC_INTEGRATIONS_ENABLED=false` and `PUBLIC_CUSTOM_WEBHOOKS_ENABLED=false`. Admins retain access to both.
8. Run `uv run price-alert-cli sync-commands` and `uv run price-alert-cli sync-profile`. The second command publishes the name, description, bio, and 512 x 512 profile photo.
9. In BotFather, upload `assets/brand/price-bird-description-banner.png` as the description picture. Telegram's Bot API does not expose this field.
10. Disable group joins in BotFather unless group support is intentionally added and tested.

## Private Trenchbook setup

Run `uv run price-alert-cli configure-trenchbook-integration` after migrations. Store the printed receiver secret in Trenchbook. Do not set `PUBLIC_INTEGRATIONS_ENABLED=true` while Trenchbook is private.

## Release checks

- Open the bot from a non-admin Telegram account. `/start`, alert creation, alert editing, and Price Bird delivery must work.
- Confirm that the non-admin Settings screen has no integration or custom webhook controls.
- Trigger one real alert and confirm its source link, price, and threshold are correct.
- Confirm that an admin can connect Trenchbook and send a test event.
- Restart the worker with a delivery pending and confirm it resumes from Postgres.
- Check reverse-proxy request limits and logs without recording bot tokens, signing secrets, or webhook payloads.

The description picture still requires an explicit BotFather upload. The CLI handles the other profile fields.
