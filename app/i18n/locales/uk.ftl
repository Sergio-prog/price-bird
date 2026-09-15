## Commands and profile

command-start = Відкрити головне меню
command-help = Показати доступні команди
command-newalert = Створити алерт покроково
command-alert = Створити алерт з тексту, напр. BTC 10%
command-examples = Показати приклади алертів
command-alerts = Керувати алертами
command-settings = Керувати доставкою сповіщень
command-language = Змінити мову
command-deletealert = Видалити алерт за id
command-cancel = Скасувати поточну дію
command-stats = Показати статистику бота
command-users = Список користувачів
command-whitelist = Дозволити користувача за Telegram id
command-suspend = Заблокувати користувача за Telegram id
command-promote = Призначити користувача адміном

profile-description =
    Price Bird стежить за цінами токенів, CEX-парами, капіталізацією та флорами NFT і надсилає сповіщення в Telegram, коли спрацьовує твоє правило.

    Створюй алерти на відсоток зміни, вище або нижче ціни. Обирай одноразові чи повторювані сповіщення, кулдауни, термін дії та нотатки. Дані беруться з live-провайдерів ринку. Якщо даних немає, ціна ніколи не вигадується.

    Використовуй /newalert, щоб створити алерт покроково, або /alert BTC 10% для швидкого алерту.
profile-short-description = Алерти на токени, CEX, капіталізацію та флори NFT у реальному часі. Задай правило — Price Bird відстежить.

## Start, help and examples

start-name-fallback = друже
start =
    👋 <b>{ $name }</b>, вітаю в <b>Price Bird</b>.

    Став алерти на токени, CEX-пари, капіталізацію та флори NFT. Price Bird перевіряє live-дані ринку і пише тобі, коли спрацьовує правило.

    Обери варіант нижче або надішли <code>/alert BTC 10%</code>, щоб почати.

    📣 <a href="{ $channel_url }">Канал</a>
help-title = <b>Доступні команди</b>
examples =
    <b>Приклади</b>

    <b>Швидка команда</b>
    <code>/alert BTC 10%</code>
    <code>/alert ETH &gt; 4000</code>
    <code>/alert SOL &lt; 120</code>
    <code>/alert PEPE 15%</code>
    <code>/alert BTC/USDT &lt; 90000</code>

    <b>Флори NFT</b>
    <code>/alert milady floor 10%</code>
    <code>/alert pudgy penguins floor 15%</code>
    <code>/alert boredapeyachtclub floor &lt; 8</code>

    <b>Покроково</b>
    Використовуй <code>/newalert</code>, якщо пошук знайшов забагато варіантів або хочеш кнопки.

## Access

access-denied = Доступ заборонено.
access-denied-whitelist = Доступ заборонено. Попроси адміна додати твій Telegram ID у вайтлист.
access-pending = Доступ очікує підтвердження.
access-pending-whitelist = Доступ очікує підтвердження. Попроси адміна додати твій Telegram ID у вайтлист.
admin-required = Потрібні права адміна.
private-chat-required = Відкрий Price Bird у приватному чаті.

## Main menu and navigation

menu-new-alert = 🔔 Новий алерт
menu-active-alerts = 📌 Активні алерти
menu-examples = 📚 Приклади
menu-settings = ⚙️ Налаштування
button-back = ↩️ Назад
button-back-to-menu = ↩️ До меню
button-menu = 🏠 Меню
button-add-another = ➕ Додати ще

## Alert wizard

asset-type-prompt = За яким ринком стежимо?
asset-type-token = 🪙 Монети / CEX
asset-type-nft = 🖼 Флор NFT
query-prompt-token = 🔎 Надішли тікер, контракт або CEX-пару. Наприклад: <code>BONK</code> або <code>BTC</code>
query-prompt-nft = 🖼 Надішли назву NFT-колекції. Наприклад: <code>milady</code>
provider-failed-token = Не вдалося знайти активи. Провайдер зараз недоступний. Спробуй пізніше.
provider-failed-nft = Не вдалося знайти NFT-колекції. Провайдер зараз недоступний. Спробуй пізніше.
provider-misconfigured-token = Пошук активів недоступний: провайдер не налаштований. Попроси адміна перевірити налаштування бота.
provider-misconfigured-nft = Пошук NFT недоступний: відсутній або прострочений ключ OpenSea API. Попроси адміна оновити його.
no-matches-token = Активів не знайдено. Спробуй тікер, адресу контракту або коротшу назву.
no-matches-nft = NFT-колекцій не знайдено. Спробуй slug колекції або коротшу назву.
candidates-prompt = Вибери актив для відстеження:
alert-type-prompt = Обери, коли має спрацювати алерт:
alert-type-percent = 📈 Зміна % вгору/вниз
alert-type-above = 🚀 Пробиває вище
alert-type-below = 🩸 Падає нижче
alert-type-mcap-above = Капіталізація вище
alert-type-mcap-below = Капіталізація нижче
threshold-percent =
    <b>{ $asset }</b>

    Введи % зміни ціни для сповіщень:
threshold-above =
    <b>{ $asset }</b>

    Введи ціну в { $currency }, при пробитті якої вгору спрацює алерт:
    { $hint }
threshold-below =
    <b>{ $asset }</b>

    Введи ціну в { $currency }, при падінні нижче якої спрацює алерт:
    { $hint }
threshold-mcap =
    <b>{ $asset }</b>

    Введи фактичну капіталізацію в { $currency }. FDV не використовується.
    Одноразовий: алерт видаляється після першого спрацювання. Інакше він перезаряджається і повторюється.
    { $hint }
threshold-unit-hint = Скорочення: 100k, 23m, 1b. Додай одиницю, щоб змінити валюту, напр. <code>$0.023</code>.
threshold-unit-hint-native = Скорочення: 100k, 23m, 1b. Додай одиницю, щоб змінити валюту, напр. <code>$0.023</code> або <code>1.2 { $symbol }</code>.
button-default-percent = За замовчуванням (10%)
button-currency = Валюта: { $currency }
button-one-time = Одноразовий: { $state }
usd-only = Цей актив оцінюється лише в USD.

## Alert creation

alert-create-failed = Не вдалося створити алерт: { $reason }
alert-created =
    ✅ <b>{ $symbol }</b> тепер у твоєму списку відстеження.

    Умова: { $condition }
    Базова ціна: { $baseline }
    Ринок: { $market }
    Режим: { $mode }
mode-repeat = повторюваний
mode-one-time = одноразовий
condition-percent = Зміна { $threshold } вгору чи вниз
condition-price-above = Ціна вище { $threshold }
condition-price-below = Ціна нижче { $threshold }
condition-mcap-above = Капіталізація вище { $threshold }
condition-mcap-below = Капіталізація нижче { $threshold }
condition-default = Ціновий алерт

## Alert limits

limit-user-token =
    { $limit ->
        [one] Максимум { $limit } алерт на токени. Видали алерт, щоб додати новий.
        [few] Максимум { $limit } алерти на токени. Видали алерт, щоб додати новий.
        [many] Максимум { $limit } алертів на токени. Видали алерт, щоб додати новий.
       *[other] Максимум { $limit } алертів на токени. Видали алерт, щоб додати новий.
    }
limit-user-nft =
    { $limit ->
        [one] Максимум { $limit } алерт на NFT. Видали алерт, щоб додати новий.
        [few] Максимум { $limit } алерти на NFT. Видали алерт, щоб додати новий.
        [many] Максимум { $limit } алертів на NFT. Видали алерт, щоб додати новий.
       *[other] Максимум { $limit } алертів на NFT. Видали алерт, щоб додати новий.
    }
limit-global-alerts-token = Price Bird досяг ліміту алертів на токени. Спробуй пізніше.
limit-global-alerts-nft = Price Bird досяг ліміту алертів на NFT. Спробуй пізніше.
limit-global-assets-token = Price Bird уже відстежує максимальну кількість токенів. Додай алерт на токен, який уже відстежується, або спробуй пізніше.
limit-global-assets-nft = Price Bird уже відстежує максимальну кількість NFT-колекцій. Додай алерт на колекцію, яка вже відстежується, або спробуй пізніше.

## Alert list

no-alerts = Тут поки немає алертів. Використай <code>/alert BTC 10%</code> або створи його в меню.
alerts-list =
    📌 <b>Активні алерти</b> ({ $total })
    Натисни на алерт, щоб редагувати.
delete-alert-usage = Використання: /deletealert 123
active-alert-not-found = Активний алерт не знайдено.
alert-deleted = Видалено алерт #{ $id }.
nothing-to-cancel = Немає чого скасовувати.
asset-fallback = актив
market-cap-short = Кап.

## Alert descriptions

describe-percent = { $symbol }: зміна { $threshold } вгору чи вниз
describe-price-above = { $symbol } вище { $threshold }
describe-price-below = { $symbol } нижче { $threshold }
describe-mcap-above = { $symbol }: капіталізація вище { $threshold }
describe-mcap-below = { $symbol }: капіталізація нижче { $threshold }
describe-absolute = { $symbol }: зміна на { $threshold }
market-token = токен
market-cex = CEX
market-nft = флор NFT
direction-up = Вгору
direction-down = Вниз
direction-both = Вгору чи вниз

## Alert settings

invalid-alert = Некоректний алерт.
alert-not-found = Алерт не знайдено.
alert-not-editable = Алерт більше не можна редагувати.
alert-deleted-toast = Видалено
clear-expiry-before-resume = Прибери термін дії перед відновленням.
field-market = Ринок: { $value }
field-status = Статус: { $value }
field-mode = Режим: { $value }
field-threshold = Поріг: { $value }
field-baseline = Базова ціна: { $value }
field-cooldown = Кулдаун: { $value }
field-direction = Напрямок: { $value }
field-expires = Термін дії: { $value }
field-note = Нотатка: { $value }
status-active = ▶️ активний
status-paused = ⏸ на паузі
note-none = немає
mode-one-time-removed = одноразовий, видаляється після спрацювання
mode-repeat-rebase = повторюваний, базова ціна оновлюється після кожного спрацювання
mode-repeat-reset = повторюваний, після скидання умови
button-pause = ⏸ Пауза
button-resume = ▶️ Відновити
button-cooldown = ⏱ Кулдаун: { $value }
button-direction = Напрямок: { $value }
button-threshold = ✏️ Поріг
button-note = 📝 Нотатка
button-expires = ⏳ Термін дії: { $value }
button-delete = 🗑 Видалити
button-confirm-delete = ✅ Так, видалити
button-back-to-alerts = ↩️ До алертів
confirm-delete = 🗑 Видалити <b>{ $description }</b>?
expiry-never = ніколи
expiry-expired = завершився
expiry-in = через { $duration }
expiry-at = { $date } (через { $duration })
prompt-note = Надішли нотатку, до 300 символів. Надішли -, щоб очистити.
prompt-cooldown = Надішли кулдаун, напр. 15m, 2h або 1d. Поточний: { $current }
prompt-expiry = Надішли термін дії, напр. 24h, 2d, 3mo або 1y. Надішли -, щоб не обмежувати. Поточний: { $current }
prompt-threshold-percent = Надішли новий поріг у %. Поточний: { $current }
prompt-threshold-price = Надішли нову ціну в { $units }. Поточна: { $current }
prompt-threshold-mcap = Надішли нову капіталізацію в { $units }. Поточна: { $current }
units-usd = USD (напр. $0.023, 23m)
units-native = USD або { $symbol } (напр. $0.023, 23m, 1.2 { $symbol })

## Input errors

error-positive-number = Надішли коректне додатне число.
error-threshold-format = Надішли додатне скінченне число з не більше ніж 36 знаками після коми.
error-threshold-range = Поріг має бути додатним, скінченним і мати не більше 36 знаків після коми.
error-amount-format = Надішли число, напр. 0.023, 100k, 23m, 1b, за бажанням з одиницею: $0.023, 1.2 ETH.
error-amount-not-positive = Значення має бути додатним числом.
error-invalid-number = Некоректне число: { $value }
error-currency-usd = Цей актив оцінюється в USD, а не в { $unit }.
error-currency-native = Цей актив оцінюється в USD або { $symbol }, а не в { $unit }.
error-duration-format = Використай число з одиницею: 15m, 24h, 2d, 5w, 3mo, 1y (також 15 min, 5 years).
error-duration-not-positive = Тривалість має бути додатною.
error-duration-too-short = Використай щонайменше 1 хвилину.
error-duration-too-long = Використай щонайбільше { $max }.
error-note-length = Використай від 1 до 300 символів або -, щоб очистити нотатку.
error-alert-usage = Використання: /alert BTC 10% або /alert ETH > 70000
error-alert-missing-parts = Бракує запиту активу або умови алерту.
error-alert-condition = Умова має бути відсотком, напр. 10%, або порогом, напр. > 70000, > 100k чи < 0.8 ETH.
error-no-price = Немає доступної коректної ціни.
error-mcap-unavailable = Фактична капіталізація недоступна для цього активу.
error-url-https = Використай HTTPS URL на порту 443.
error-url-invalid = Використай HTTPS URL на порту 443, без облікових даних чи фрагментів.
error-url-public = Адреса вебхука має бути публічною.

## Settings

settings-private-only = Відкрий приватний чат із Price Bird, щоб керувати налаштуваннями.
settings-text =
    Налаштування доставки

    Вмикай або вимикай сповіщення Price Bird. Встанови свій часовий пояс, а потім обери години тиші для беззвучних алертів. Обери посилання на монету для токен-алертів. Вимкнення сповіщень скасовує заплановані доставки в Telegram. Алерти продовжують перевірятися. Постав окремі алерти на паузу через /alerts.
settings-text-connections =
    Налаштування доставки

    Вмикай або вимикай сповіщення Price Bird. Встанови свій часовий пояс, а потім обери години тиші для беззвучних алертів. Обери посилання на монету для токен-алертів. Алерти продовжують перевірятися. Постав окремі алерти на паузу через /alerts.

    Обери, куди надсилати алерти. Увімкни Price Bird, підключений застосунок або обидва варіанти. Вимкнення напрямку скасовує його заплановані доставки.
settings-trenchbook-hint = <a href="{ $url }">Trenchbook</a> використовує той самий акаунт Telegram; спершу запусти його бота.
settings-bird = Сповіщення Price Bird: { $state }
settings-timezone = Часовий пояс: { $timezone }
settings-quiet-hours = Години тиші: { $value }
settings-coin-link = Посилання на монету: { $provider }
settings-language = 🌐 Мова: { $language }
settings-connection = { $name }: { $state }
settings-connect = Підключити { $name }
settings-add-webhook = Додати власний вебхук
state-on = увімкнено
state-off = вимкнено
language-prompt = Обери мову:
quiet-hours-text =
    Години тиші: { $value }
    Алерти Price Bird надходитимуть без звуку.
quiet-from = від { $time }
quiet-to = до { $time }
quiet-turn-off = Вимкнути
quiet-turn-on = Увімкнути 22:00-07:00
timezone-text =
    Часовий пояс: { $timezone }
    Години тиші використовують цей місцевий час. Фіксований зсув UTC не переходить автоматично на літній час.
coin-link-text =
    Посилання на монету: { $provider }
    Це посилання додається до токен-алертів, коли сервіс підтримує актив.
invalid-timezone-setting = Некоректне налаштування часового поясу.
invalid-quiet-hours-setting = Некоректне налаштування годин тиші.
invalid-coin-link = Некоректне посилання на монету.
invalid-connection-action = Некоректна дія з підключенням.
connection-not-found = Підключення не знайдено.
integration-not-found = Інтеграцію не знайдено.
admin-only-destination = Цей напрямок доступний лише адмінам.
admin-only-integrations = Інтеграції доступні лише адмінам.
admin-only-custom-webhooks = Власні вебхуки доступні лише адмінам.
connections-limit = Можна підключити до { $limit } застосунків.
custom-webhook-prompt =
    Надішли назву та HTTPS URL вебхука, наприклад:
    Мій застосунок https://example.com/webhook

    /cancel, щоб скасувати.
custom-webhook-connected =
    Підключено { $name }. Збережи цей секрет підпису на своєму отримувачі:
    { $secret }

    Запити підписуються HMAC-SHA256. Налаштуй свій отримувач, а тоді увімкни підключення в Налаштуваннях.
webhook-name-too-long = Використай назву довжиною до 80 символів.
webhook-name-and-url = Надішли назву, а тоді HTTPS URL.
new-signing-secret =
    Новий секрет підпису. Онови отримувач перед тим, як вмикати доставку:
    { $secret }
enable-connection-first = Спершу увімкни це підключення.
delivery-already-pending = Доставка вже очікує.
connection-host = Хост: { $host }
host-unavailable = недоступний
connection-notifications = Сповіщення: { $state }
connection-last-delivery = Остання доставка: { $status }
button-enable = Увімкнути
button-disable = Вимкнути
button-send-test = Надіслати тест
button-retry-failure = Повторити останню помилку
button-rotate-secret = Оновити секрет підпису
button-disconnect = Відключити

## Notifications

notification-test = Тестове підключення Price Bird. Жоден алерт не спрацював.
notification-rule = <b>Правило:</b> { $rule }
notification-price = <b>Ціна:</b> { $price }
notification-floor = <b>Флор:</b> { $native } { $symbol } ({ $usd })
notification-market-cap = <b>Капіталізація:</b> { $value }
notification-source = <b>Джерело:</b> { $source }
notification-links = <b>Посилання:</b> { $links }
notification-note = <b>Нотатка:</b> { $note }
rule-percent-both = Зміна { $threshold } вгору чи вниз
rule-percent-up = Зміна { $threshold } вгору
rule-percent-down = Зміна { $threshold } вниз
rule-price-above = Ціна вище { $threshold }
rule-price-below = Ціна нижче { $threshold }
rule-mcap-above = Капіталізація вище { $threshold }
rule-mcap-below = Капіталізація нижче { $threshold }
rule-absolute = Зміна ціни на { $threshold }

## Admin

admin-usage = Використання: /{ $command } 123456789
admin-whitelisted = Додано у вайтлист { $telegram_id }.
admin-suspended = Заблоковано { $telegram_id }.
admin-promoted = Призначено адміном { $telegram_id }.
admin-no-users = Немає користувачів.
admin-stats =
    Користувачі: { $users }
    Активні алерти: { $active_alerts }
    Активи, що відстежуються: { $watched_assets }
admin-debug-connect-trenchbook = Спершу підключи й увімкни Trenchbook.
admin-debug-no-alert = Немає попереднього алерту для повторного відтворення.
admin-debug-queued = Алерт #{ $alert_id } поставлено в чергу для Trenchbook.
