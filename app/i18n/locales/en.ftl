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
command-broadcast = Send a message to users

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
    <b>📚 Examples</b>

    <b>⚡ Fast command</b>
    <code>/alert BTC 10%</code> - moves up or down
    <code>/alert SOL +5%</code> - pumps only
    <code>/alert PEPE -15%</code> - dumps only
    <code>/alert ETH &gt; 4000</code>
    <code>/alert BTC/USDT &lt; 90000</code>
    <code>/alert BONK &lt; 0.0₄5</code>
    <code>/alert PEPE &gt; 5b mc</code> - market cap

    <b>🖼 NFT floors</b>
    <code>/alert milady floor 10%</code>
    <code>/alert pudgy penguins floor 15%</code>
    <code>/alert boredapeyachtclub floor &lt; 8</code>

    <b>🧭 Step by step</b>
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
button-edit-alert = ✏️ Edit alert
button-alert-settings = ⚙️ Alert settings

## Alert wizard

asset-type-prompt = What market are we watching?
asset-type-token = 🪙 Coins / CEX
asset-type-nft = 🖼 NFT floor
query-prompt-token = 🔎 Send a ticker, a token or pool address, or a CEX pair. Example: <code>BONK</code> or <code>BTC</code>
query-prompt-nft = 🖼 Send the NFT collection name or contract address. Example: <code>milady</code>
provider-failed-token = Failed to search assets. Provider is unavailable right now. Try again later.
provider-failed-nft = Failed to search NFT collections. Provider is unavailable right now. Try again later.
provider-misconfigured-token = Asset search is unavailable: provider is not configured. Ask an admin to check the bot settings.
provider-misconfigured-nft = NFT search is unavailable: the OpenSea API key is missing or expired. Ask an admin to renew it.
no-matches-token = No assets found. Try a ticker, a token or pool address, or a shorter name.
no-matches-nft = No NFT collections found. Try the collection slug, contract address, or a shorter name.
candidates-prompt = Select the asset to watch. Most traded first.
sources-prompt = Show results from:
source-all = All
button-source-filter = 🔀 Source: { $source }
alert-type-prompt =
    { $asset }

    Choose when this alert should trigger:
alert-type-percent = 📈 Move % up/down
alert-type-above = 🚀 Breaks above
alert-type-below = 🩸 Drops below
threshold-percent =
    { $asset }

    📈 Send the % move that should trigger the alert, e.g. <code>10</code>.
    <code>+5%</code> watches pumps only, <code>-5%</code> dumps only.
threshold-above =
    { $asset }

    🚀 Send the { $currency } price that should trigger when the market breaks above it:
    { $hint }
threshold-below =
    { $asset }

    🩸 Send the { $currency } price that should trigger when the market drops below it:
    { $hint }
threshold-mcap-above =
    { $asset }

    🚀 Send the market cap in { $currency } that should trigger when it breaks above it. FDV is not used.
    { $hint }
threshold-mcap-below =
    { $asset }

    🩸 Send the market cap in { $currency } that should trigger when it drops below it. FDV is not used.
    { $hint }
threshold-unit-hint = 💡 Shortcuts: 100k, 23m, 1b, 1e-6, 0.0₄5. Add a unit to override the currency, e.g. <code>$0.023</code>.
threshold-unit-hint-native = 💡 Shortcuts: 100k, 23m, 1b, 1e-6, 0.0₄5. Add a unit to override the currency, e.g. <code>$0.023</code> or <code>1.2 { $symbol }</code>.
threshold-mcap-hint = 📊 Add <code>mc</code> for market cap, e.g. <code>17m mc</code>.
button-default-percent = Default (10%)
button-metric-price = 💲 Price
button-metric-mcap = 📊 Market cap
button-currency = Currency: { $currency }
button-one-time = One time: { $state }
usd-only = This asset is priced in USD only.

## Alert creation

alert-create-failed = Could not create alert: { $reason }
alert-created =
    ✅ <b>{ $symbol }</b> is now on your watchlist.

    🎯 Trigger: { $condition }
    📍 Baseline: { $baseline }
    🏦 Market: { $market }
    🔁 Mode: { $mode }
mode-repeat = repeat
mode-one-time = one time
condition-percent-both = Moves { $threshold } up or down
condition-percent-up = Moves { $threshold } up
condition-percent-down = Moves { $threshold } down
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

describe-percent-both = { $symbol } moves { $threshold } up or down
describe-percent-up = { $symbol } moves { $threshold } up
describe-percent-down = { $symbol } moves { $threshold } down
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
field-market = 🏦 Market: { $value }
field-source = 🛰 Source: { $value }
field-status = Status: { $value }
field-mode = 🔁 Mode: { $value }
field-threshold = 🎯 Threshold: { $value }
field-baseline = 📍 Baseline: { $value }
field-cooldown = ⏱ Cooldown: { $value }
field-direction = ↕️ Direction: { $value }
field-expires = ⏳ Expires: { $value }
field-note = 📝 Note: { $value }
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
prompt-cooldown = Send a cooldown like 10s, 1m, 15m or 2h. Current: { $current }
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
error-amount-format = Send a number like 0.023, 100k, 23m, 1b, 1e-6 or 0.0₄5, optionally with a unit: $0.023, 1.2 ETH.
error-amount-not-positive = Value must be a positive number.
error-percent-format = Send a percent like 10, 2.5%, +5% or -5%.
error-currency-usd = This asset is priced in USD, not { $unit }.
error-currency-native = This asset is priced in USD or { $symbol }, not { $unit }.
error-duration-format = Use a number with a unit: 15m, 24h, 2d, 5w, 3mo, 1y (also 15 min, 5 years).
error-duration-not-positive = Duration must be positive.
error-duration-too-short = Use at least { $min }.
error-duration-too-long = Use at most { $max }.
error-note-length = Use 1 to 300 characters, or - to clear the note.
error-alert-usage = Usage: /alert BTC 10%, /alert SOL +5% or /alert ETH > 70000
error-alert-missing-parts = Missing asset query or alert condition.
error-alert-condition = Condition must be a percent like 10%, +5% or -5%, or a threshold like > 70000, < 0.8 ETH or > 17m mc.
error-no-price = No valid price available.
error-mcap-unavailable = Actual market cap is unavailable for this asset.
error-url-https = Use an HTTPS URL on port 443.
error-url-invalid = Use an HTTPS URL on port 443, without credentials or fragments.
error-url-public = Webhook addresses must be public.

## Settings

settings-private-only = Open a private chat with Price Bird to manage settings.
settings-text =
    ⚙️ <b>Settings</b>

    🔔 Notifications: <b>{ $bird }</b>
    🌍 Timezone: <b>{ $timezone }</b>
    🌙 Quiet hours: <b>{ $quiet }</b>
    🔗 Coin links: { $links }
    🌐 Language: <b>{ $language }</b>

    <i>Alerts keep evaluating while notifications are off. Pause single alerts in /alerts.</i>
settings-destinations-hint = 📡 <i>Choose where alerts go: Price Bird, connected apps, or both. Turning a destination off cancels its pending deliveries.</i>
settings-trenchbook-hint = <a href="{ $url }">Trenchbook</a> uses your same Telegram account; start its bot first.
settings-bird = 🔔 Notifications: { $state }
settings-timezone = 🌍 { $timezone }
settings-quiet-hours = 🌙 Quiet hours: { $value }
settings-coin-links = 🔗 Coin links: { $value }
settings-language = 🌐 { $language }
settings-connection = 🔌 { $name }: { $state }
settings-connect = ➕ Connect { $name }
settings-add-webhook = 🪝 Add custom webhook
state-on = on
state-off = off
language-prompt = 🌐 Choose your language:
quiet-hours-text =
    🌙 <b>Quiet hours:</b> { $value }
    Price Bird alerts still arrive, but without sound.
quiet-from = from { $time }
quiet-to = to { $time }
quiet-turn-off = 🔔 Turn off
quiet-turn-on = 🌙 Turn on 22:00-07:00
timezone-text =
    🌍 <b>Timezone:</b> { $timezone }
    Quiet hours use this local time. Fixed UTC offsets don't follow daylight saving time.
coin-links-text =
    🔗 <b>Coin links:</b> { $links }
    Pick the links shown under each alert. If none of them support an asset, its source link is shown instead.
coin-links-none = hidden
button-coin-links-none = 🚫 Hide all links
invalid-timezone-setting = Invalid timezone setting.
invalid-quiet-hours-setting = Invalid quiet-hours setting.
invalid-coin-link = Invalid coin link.
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
connection-host = 🌐 Host: { $host }
host-unavailable = unavailable
connection-notifications = 🔔 Notifications: { $state }
connection-last-delivery = 📬 Last delivery: { $status }
button-enable = ▶️ Enable
button-disable = ⏸ Disable
button-send-test = 🧪 Send test
button-retry-failure = 🔁 Retry last failure
button-rotate-secret = 🔑 Rotate signing secret
button-disconnect = 🔌 Disconnect

## Notifications

notification-test = Price Bird connection test. No alert was triggered.
notification-rule = 🎯 <b>Rule:</b> { $rule }
notification-price = 💵 <b>Price:</b> { $price }
notification-floor = 🖼 <b>Floor price:</b> { $native } { $symbol } ({ $usd })
notification-market-cap = 📊 <b>Market cap:</b> { $value }
notification-dex = 🏦 <b>DEX:</b> { $dex }
notification-note = 📝 <b>Note:</b> { $note }
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

## Broadcast

broadcast-audience-prompt = 📣 <b>New broadcast</b>

    Who should receive it?
button-broadcast-all = 👥 All users ({ $count })
button-broadcast-specific = 🎯 Specific users
button-broadcast-cancel = ✖️ Cancel
broadcast-recipients-prompt = Send Telegram IDs or @usernames separated by spaces, commas or new lines.
broadcast-recipients-found = 👥 Recipients found: { $count }
broadcast-recipients-missing = ⚠️ Not found: { $refs }
broadcast-recipients-none = None of these users have started the bot. Send other IDs or usernames.
broadcast-content-prompt = Send the post: text, photo, video, GIF or file. Formatting and custom emoji are kept.
broadcast-confirm =
    📣 <b>Post preview is above</b>

    👥 Recipients: <b>{ $count }</b> ({ $audience })
    🔘 Buttons: { $buttons }
broadcast-audience-all = all users
broadcast-audience-specific = selected users
broadcast-buttons-none = none
button-broadcast-add = ➕ Add button
button-broadcast-remove = ↩️ Remove last button
button-broadcast-send = ✅ Send to { $count }
broadcast-button-text-prompt = Send the button text, up to { $max } characters.
broadcast-button-action-prompt =
    Send a link for <b>{ $text }</b> (https://…, t.me/… or tg://…)
    or callback data up to { $max } bytes.
broadcast-started = 📤 Sending to { $count } users…
broadcast-finished = 📣 Broadcast finished: delivered { $sent } of { $total }, failed { $failed }.
broadcast-cancelled = Broadcast cancelled.
broadcast-expired = This broadcast is no longer active.
broadcast-no-recipients = No users to send to.
error-broadcast-button-text = Button text must be 1–{ $max } characters.
error-broadcast-button-url = Send a valid https://, t.me/ or tg:// link.
error-broadcast-button-data = Callback data must be 1–{ $max } bytes.
error-broadcast-recipient = Not a Telegram ID or @username: { $value }
error-broadcast-recipients-empty = Send at least one Telegram ID or @username.
