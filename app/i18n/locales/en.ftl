## Commands and profile

command-start = Open main menu
command-help = Show available commands
command-newalert = Create an alert step by step
command-alert = Create alert from text, e.g. BTC 10%
command-examples = Show alert examples
command-alerts = Manage alerts
command-settings = Manage notification delivery
command-language = Change language
command-deletealert = Delete alert by id
command-cancel = Cancel current action
command-stats = Show bot stats
command-users = List users
command-whitelist = Allow user by Telegram id
command-suspend = Suspend user by Telegram id
command-promote = Promote user to admin

profile-description =
    Price Bird watches token prices, CEX pairs, market caps, and NFT floor prices, then sends a Telegram alert when your rule triggers.

    Create percentage, above, or below alerts. Set one-time or repeating notifications, cooldowns, expiry dates, and notes. Data comes from live market providers. Missing data never becomes a made-up price.

    Use /newalert to build one step by step or /alert BTC 10% for a quick alert.
profile-short-description = Live token, CEX, market-cap, and NFT floor alerts. Set a rule and Price Bird watches it.

## Start, help and examples

start-name-fallback = there
start =
    👋 <b>{ $name }</b>, welcome to <b>Price Bird</b>.

    Set alerts for tokens, CEX pairs, market caps, and NFT floors. Price Bird checks live market data and messages you when your rule triggers.

    Choose an option below, or send <code>/alert BTC 10%</code> to start.

    📣 <a href="{ $channel_url }">Channel</a>
help-title = <b>Available commands</b>
examples =
    <b>Examples</b>

    <b>Fast command</b>
    <code>/alert BTC 10%</code>
    <code>/alert ETH &gt; 4000</code>
    <code>/alert SOL &lt; 120</code>
    <code>/alert PEPE 15%</code>
    <code>/alert BTC/USDT &lt; 90000</code>

    <b>NFT floors</b>
    <code>/alert milady floor 10%</code>
    <code>/alert pudgy penguins floor 15%</code>
    <code>/alert boredapeyachtclub floor &lt; 8</code>

    <b>Step by step</b>
    Use <code>/newalert</code> when search returns many matches or you want buttons.

## Access

access-denied = Access denied.
access-denied-whitelist = Access denied. Ask an admin to whitelist your Telegram ID.
access-pending = Access pending.
access-pending-whitelist = Access pending. Ask an admin to whitelist your Telegram ID.
admin-required = Admin access required.
private-chat-required = Open Price Bird in a private chat.

## Main menu and navigation

menu-new-alert = 🔔 New alert
menu-active-alerts = 📌 Active alerts
menu-examples = 📚 Examples
menu-settings = ⚙️ Settings
button-back = ↩️ Back
button-back-to-menu = ↩️ Back to menu
button-menu = 🏠 Menu
button-add-another = ➕ Add another

## Alert wizard

asset-type-prompt = What market are we watching?
asset-type-token = 🪙 Coins / CEX
asset-type-nft = 🖼 NFT floor
query-prompt-token = 🔎 Send a ticker, contract, or CEX pair. Example: <code>BONK</code> or <code>BTC</code>
query-prompt-nft = 🖼 Send the NFT collection name. Example: <code>milady</code>
provider-failed-token = Failed to search assets. Provider is unavailable right now. Try again later.
provider-failed-nft = Failed to search NFT collections. Provider is unavailable right now. Try again later.
provider-misconfigured-token = Asset search is unavailable: provider is not configured. Ask an admin to check the bot settings.
provider-misconfigured-nft = NFT search is unavailable: the OpenSea API key is missing or expired. Ask an admin to renew it.
no-matches-token = No assets found. Try a ticker, contract address, or a shorter name.
no-matches-nft = No NFT collections found. Try the collection slug or a shorter name.
candidates-prompt = Select the asset to watch:
alert-type-prompt = Choose when this alert should trigger:
alert-type-percent = 📈 Move % up/down
alert-type-above = 🚀 Breaks above
alert-type-below = 🩸 Drops below
alert-type-mcap-above = Market cap above
alert-type-mcap-below = Market cap below
threshold-percent =
    <b>{ $asset }</b>

    Enter % price change to receive notifications:
threshold-above =
    <b>{ $asset }</b>

    Enter { $currency } price that should trigger when market moves above it:
    { $hint }
threshold-below =
    <b>{ $asset }</b>

    Enter { $currency } price that should trigger when market drops below it:
    { $hint }
threshold-mcap =
    <b>{ $asset }</b>

    Enter actual market cap in { $currency }. FDV is not used.
    One time: the alert is removed after it fires once. Otherwise it rearms and repeats.
    { $hint }
threshold-unit-hint = Shortcuts: 100k, 23m, 1b. Add a unit to override the currency, e.g. <code>$0.023</code>.
threshold-unit-hint-native = Shortcuts: 100k, 23m, 1b. Add a unit to override the currency, e.g. <code>$0.023</code> or <code>1.2 { $symbol }</code>.
button-default-percent = Default (10%)
button-currency = Currency: { $currency }
button-one-time = One time: { $state }
usd-only = This asset is priced in USD only.

## Alert creation

alert-create-failed = Could not create alert: { $reason }
alert-created =
    ✅ <b>{ $symbol }</b> is now on your watchlist.

    Trigger: { $condition }
    Baseline: { $baseline }
    Market: { $market }
    Mode: { $mode }
mode-repeat = repeat
mode-one-time = one time
condition-percent = Moves { $threshold } up or down
condition-price-above = Price goes above { $threshold }
condition-price-below = Price goes below { $threshold }
condition-mcap-above = Market cap goes above { $threshold }
condition-mcap-below = Market cap goes below { $threshold }
condition-default = Price alert

## Alert limits

limit-user-token =
    { $limit ->
        [one] You can have up to { $limit } token alert. Delete an alert to add a new one.
       *[other] You can have up to { $limit } token alerts. Delete an alert to add a new one.
    }
limit-user-nft =
    { $limit ->
        [one] You can have up to { $limit } NFT alert. Delete an alert to add a new one.
       *[other] You can have up to { $limit } NFT alerts. Delete an alert to add a new one.
    }
limit-global-alerts-token = Price Bird has reached its token alert capacity. Try again later.
limit-global-alerts-nft = Price Bird has reached its NFT alert capacity. Try again later.
limit-global-assets-token = Price Bird is watching the maximum number of tokens. Add an alert for a token that is already watched, or try again later.
limit-global-assets-nft = Price Bird is watching the maximum number of NFT collections. Add an alert for a collection that is already watched, or try again later.

## Alert list

no-alerts = No alerts here. Use <code>/alert BTC 10%</code> or create it in menu.
alerts-list =
    📌 <b>Active alerts</b> ({ $total })
    Tap an alert to edit it.
delete-alert-usage = Usage: /deletealert 123
active-alert-not-found = Active alert not found.
alert-deleted = Deleted alert #{ $id }.
nothing-to-cancel = Nothing to cancel.
asset-fallback = asset
market-cap-short = MC

## Alert descriptions

describe-percent = { $symbol } moves { $threshold } up or down
describe-price-above = { $symbol } above { $threshold }
describe-price-below = { $symbol } below { $threshold }
describe-mcap-above = { $symbol } market cap above { $threshold }
describe-mcap-below = { $symbol } market cap below { $threshold }
describe-absolute = { $symbol } absolute change { $threshold }
market-token = token
market-cex = CEX
market-nft = NFT floor
direction-up = Up
direction-down = Down
direction-both = Up or down

## Alert settings

invalid-alert = Invalid alert.
alert-not-found = Alert not found.
alert-not-editable = Alert no longer editable.
alert-deleted-toast = Deleted
clear-expiry-before-resume = Clear the expiry before resuming.
field-market = Market: { $value }
field-status = Status: { $value }
field-mode = Mode: { $value }
field-threshold = Threshold: { $value }
field-baseline = Baseline: { $value }
field-cooldown = Cooldown: { $value }
field-direction = Direction: { $value }
field-expires = Expires: { $value }
field-note = Note: { $value }
status-active = ▶️ active
status-paused = ⏸ paused
note-none = none
mode-one-time-removed = one time, removed after it fires
mode-repeat-rebase = repeats, baseline moves to each trigger price
mode-repeat-reset = repeats after the condition resets
button-pause = ⏸ Pause
button-resume = ▶️ Resume
button-cooldown = ⏱ Cooldown: { $value }
button-direction = Direction: { $value }
button-threshold = ✏️ Threshold
button-note = 📝 Note
button-expires = ⏳ Expires: { $value }
button-delete = 🗑 Delete
button-confirm-delete = ✅ Yes, delete
button-back-to-alerts = ↩️ Back to alerts
confirm-delete = 🗑 Delete <b>{ $description }</b>?
expiry-never = never
expiry-expired = expired
expiry-in = in { $duration }
expiry-at = { $date } (in { $duration })
prompt-note = Send a note, up to 300 characters. Send - to clear it.
prompt-cooldown = Send a cooldown like 15m, 2h or 1d. Current: { $current }
prompt-expiry = Send an expiry like 24h, 2d, 3mo or 1y. Send - to never expire. Current: { $current }
prompt-threshold-percent = Send a new threshold in %. Current: { $current }
prompt-threshold-price = Send a new price in { $units }. Current: { $current }
prompt-threshold-mcap = Send a new market cap in { $units }. Current: { $current }
units-usd = USD (e.g. $0.023, 23m)
units-native = USD or { $symbol } (e.g. $0.023, 23m, 1.2 { $symbol })

## Input errors

error-positive-number = Send a valid positive number.
error-threshold-format = Send a positive finite number with at most 36 decimal places.
error-threshold-range = Threshold must be positive, finite and fit within 36 decimal places.
error-amount-format = Send a number like 0.023, 100k, 23m, 1b, optionally with a unit: $0.023, 1.2 ETH.
error-amount-not-positive = Value must be a positive number.
error-invalid-number = Invalid number: { $value }
error-currency-usd = This asset is priced in USD, not { $unit }.
error-currency-native = This asset is priced in USD or { $symbol }, not { $unit }.
error-duration-format = Use a number with a unit: 15m, 24h, 2d, 5w, 3mo, 1y (also 15 min, 5 years).
error-duration-not-positive = Duration must be positive.
error-duration-too-short = Use at least 1 minute.
error-duration-too-long = Use at most { $max }.
error-note-length = Use 1 to 300 characters, or - to clear the note.
error-alert-usage = Usage: /alert BTC 10% or /alert ETH > 70000
error-alert-missing-parts = Missing asset query or alert condition.
error-alert-condition = Condition must be a percent like 10% or threshold like > 70000, > 100k or < 0.8 ETH.
error-no-price = No valid price available.
error-mcap-unavailable = Actual market cap is unavailable for this asset.
error-url-https = Use an HTTPS URL on port 443.
error-url-invalid = Use an HTTPS URL on port 443, without credentials or fragments.
error-url-public = Webhook addresses must be public.

## Settings

settings-private-only = Open a private chat with Price Bird to manage settings.
settings-text =
    Delivery settings

    Turn Price Bird notifications on or off. Turning them off cancels pending Telegram deliveries. Alerts keep evaluating. Pause individual alerts from /alerts.
settings-text-connections =
    Delivery settings

    Choose where all your alerts are sent. Turn on Price Bird, a connected app, or both. Turning off a destination cancels its pending deliveries. Alerts keep evaluating. Pause individual alerts from /alerts.
settings-trenchbook-hint = <a href="{ $url }">Trenchbook</a> uses your same Telegram account; start its bot first.
settings-bird = Price Bird notifications: { $state }
settings-language = 🌐 Language: { $language }
settings-connection = { $name }: { $state }
settings-connect = Connect { $name }
settings-add-webhook = Add custom webhook
state-on = on
state-off = off
language-prompt = Choose your language:
invalid-connection-action = Invalid connection action.
connection-not-found = Connection not found.
integration-not-found = Integration not found.
admin-only-destination = This destination is available to admins only.
admin-only-integrations = Integrations are available to admins only.
admin-only-custom-webhooks = Custom webhooks are available to admins only.
connections-limit = You can connect up to { $limit } apps.
custom-webhook-prompt =
    Send a name and HTTPS webhook URL, for example:
    My app https://example.com/webhook

    /cancel to stop.
custom-webhook-connected =
    Connected { $name }. Store this signing secret in your receiver:
    { $secret }

    Requests use HMAC-SHA256. Configure your receiver, then enable the connection in Settings.
webhook-name-too-long = Use a name with at most 80 characters.
webhook-name-and-url = Send a name followed by the HTTPS URL.
new-signing-secret =
    New signing secret. Update your receiver before enabling delivery:
    { $secret }
enable-connection-first = Enable this connection first.
delivery-already-pending = Delivery already pending.
connection-host = Host: { $host }
host-unavailable = unavailable
connection-notifications = Notifications: { $state }
connection-last-delivery = Last delivery: { $status }
button-enable = Enable
button-disable = Disable
button-send-test = Send test
button-retry-failure = Retry last failure
button-rotate-secret = Rotate signing secret
button-disconnect = Disconnect

## Notifications

notification-test = Price Bird connection test. No alert was triggered.
notification-rule = <b>Rule:</b> { $rule }
notification-price = <b>Price:</b> { $price }
notification-floor = <b>Floor price:</b> { $native } { $symbol } ({ $usd })
notification-market-cap = <b>Market cap:</b> { $value }
notification-source = <b>Source:</b> { $source }
notification-links = <b>Links:</b> { $links }
notification-note = <b>Note:</b> { $note }
rule-percent-both = { $threshold } move up or down
rule-percent-up = { $threshold } move up
rule-percent-down = { $threshold } move down
rule-price-above = Price above { $threshold }
rule-price-below = Price below { $threshold }
rule-mcap-above = Market cap above { $threshold }
rule-mcap-below = Market cap below { $threshold }
rule-absolute = Price change of { $threshold }

## Admin

admin-usage = Usage: /{ $command } 123456789
admin-whitelisted = Whitelisted { $telegram_id }.
admin-suspended = Suspended { $telegram_id }.
admin-promoted = Promoted { $telegram_id }.
admin-no-users = No users.
admin-stats =
    Users: { $users }
    Active alerts: { $active_alerts }
    Watched assets: { $watched_assets }
admin-debug-connect-trenchbook = Connect and enable Trenchbook first.
admin-debug-no-alert = No previous alert is available to replay.
admin-debug-queued = Queued alert #{ $alert_id } for Trenchbook.
