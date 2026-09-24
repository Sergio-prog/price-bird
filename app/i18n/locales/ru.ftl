## Commands and profile

command-start = Открыть главное меню
command-help = Показать список команд
command-newalert = Создать алерт по шагам
command-alert = Создать алерт текстом, напр. BTC 10%
command-examples = Показать примеры алертов
command-alerts = Управление алертами
command-settings = Настройки уведомлений
command-language = Сменить язык
command-deletealert = Удалить алерт по id
command-cancel = Отменить текущее действие
command-stats = Показать статистику бота
command-users = Список пользователей
command-whitelist = Разрешить доступ по Telegram id
command-suspend = Заблокировать по Telegram id
command-promote = Назначить админом
command-broadcast = Отправить сообщение пользователям

profile-description =
    Price Bird следит за ценами токенов, CEX-парами, капитализацией и флорами NFT — и присылает уведомление в Telegram, когда срабатывает твоё правило.

    Создавай алерты на процент, пробой вверх или вниз. Настраивай одноразовые или повторяющиеся уведомления, кулдауны, срок действия и заметки. Данные берутся у живых рыночных провайдеров: если данных нет, цена не выдумывается.

    Используй /newalert, чтобы пройти шаги, или /alert BTC 10% для быстрого алерта.
profile-short-description = Алерты на токены, CEX, капитализацию и флоры NFT. Задай правило — Price Bird последит за ним.

## Start, help and examples

start-name-fallback = друг
start =
    👋 <b>{ $name }</b>, добро пожаловать в <b>Price Bird</b>.

    Ставь алерты на токены, CEX-пары, капитализацию и флоры NFT. Price Bird следит за рыночными данными в реальном времени и пишет тебе, когда срабатывает правило.

    Выбери вариант ниже или отправь <code>/alert BTC 10%</code>, чтобы начать.

    📣 <a href="{ $channel_url }">Канал</a>
help-title = <b>Доступные команды</b>
examples =
    <b>📚 Примеры</b>

    <b>⚡ Быстрая команда</b>
    <code>/alert BTC 10%</code> - изменение в любую сторону
    <code>/alert SOL +5%</code> - только рост
    <code>/alert PEPE -15%</code> - только падение
    <code>/alert ETH &gt; 4000</code>
    <code>/alert BTC/USDT &lt; 90000</code>
    <code>/alert BONK &lt; 0.0₄5</code>
    <code>/alert PEPE &gt; 5b mc</code> - капитализация

    <b>🖼 Флоры NFT</b>
    <code>/alert milady floor 10%</code>
    <code>/alert pudgy penguins floor 15%</code>
    <code>/alert boredapeyachtclub floor &lt; 8</code>

    <b>🧭 По шагам</b>
    Используй <code>/newalert</code>, если поиск даёт много совпадений или нужны кнопки.

## Access

access-denied = Доступ запрещён.
access-denied-whitelist = Доступ запрещён. Попроси админа добавить твой Telegram ID в вайтлист.
access-pending = Доступ на рассмотрении.
access-pending-whitelist = Доступ на рассмотрении. Попроси админа добавить твой Telegram ID в вайтлист.
admin-required = Нужны права админа.
private-chat-required = Открой Price Bird в личном чате.

## Main menu and navigation

menu-new-alert = 🔔 Новый алерт
menu-active-alerts = 📌 Активные алерты
menu-examples = 📚 Примеры
menu-settings = ⚙️ Настройки
button-back = ↩️ Назад
button-back-to-menu = ↩️ Назад в меню
button-menu = 🏠 Меню
button-add-another = ➕ Добавить ещё
button-edit-alert = ✏️ Изменить алерт
button-alert-settings = ⚙️ Настройки алерта

## Alert wizard

asset-type-prompt = За каким рынком следим?
asset-type-token = 🪙 Монеты / CEX
asset-type-nft = 🖼 Флор NFT
query-prompt-token = 🔎 Отправь тикер, адрес токена или пула либо CEX-пару. Например: <code>BONK</code> или <code>BTC</code>
query-prompt-nft = 🖼 Отправь название коллекции NFT или адрес контракта. Например: <code>milady</code>
provider-failed-token = Не удалось найти активы. Провайдер сейчас недоступен. Попробуй позже.
provider-failed-nft = Не удалось найти коллекции NFT. Провайдер сейчас недоступен. Попробуй позже.
provider-misconfigured-token = Поиск активов недоступен: провайдер не настроен. Попроси админа проверить настройки бота.
provider-misconfigured-nft = Поиск NFT недоступен: отсутствует или истёк ключ OpenSea API. Попроси админа обновить его.
no-matches-token = Активы не найдены. Попробуй тикер, адрес токена или пула либо более короткое название.
no-matches-nft = Коллекции не найдены. Попробуй slug коллекции, адрес контракта или более короткое название.
candidates-prompt = Выбери актив для отслеживания. Сначала самые торгуемые.
sources-prompt = Показать результаты из:
source-all = Все
button-source-filter = 🔀 Источник: { $source }
alert-type-prompt =
    { $asset }

    Выбери, когда алерт должен сработать:
alert-type-percent = 📈 Изменение %
alert-type-above = 🚀 Пробой вверх
alert-type-below = 🩸 Падение ниже
threshold-percent =
    { $asset }

    📈 Отправь % изменения, при котором сработает алерт, напр. <code>10</code>.
    <code>+5%</code> следит только за ростом, <code>-5%</code> только за падением.
threshold-above =
    { $asset }

    🚀 Отправь цену в { $currency }, при пробое выше которой сработает алерт:
    { $hint }
threshold-below =
    { $asset }

    🩸 Отправь цену в { $currency }, при падении ниже которой сработает алерт:
    { $hint }
threshold-mcap-above =
    { $asset }

    🚀 Отправь капитализацию в { $currency }, при пробое выше которой сработает алерт. FDV не используется.
    { $hint }
threshold-mcap-below =
    { $asset }

    🩸 Отправь капитализацию в { $currency }, при падении ниже которой сработает алерт. FDV не используется.
    { $hint }
threshold-unit-hint = 💡 Сокращения: 100k, 23m, 1b, 1e-6, 0.0₄5. Добавь единицу, чтобы задать другую валюту, напр. <code>$0.023</code>.
threshold-unit-hint-native = 💡 Сокращения: 100k, 23m, 1b, 1e-6, 0.0₄5. Добавь единицу, чтобы задать другую валюту, напр. <code>$0.023</code> или <code>1.2 { $symbol }</code>.
threshold-mcap-hint = 📊 Добавь <code>mc</code> для капитализации, напр. <code>17m mc</code>.
button-default-percent = По умолчанию (10%)
button-metric-price = 💲 Цена
button-metric-mcap = 📊 Капитализация
button-currency = Валюта: { $currency }
button-one-time = Одноразовый: { $state }
usd-only = Этот актив торгуется только в USD.

## Alert creation

alert-create-failed = Не удалось создать алерт: { $reason }
alert-created =
    ✅ <b>{ $symbol }</b> добавлен в список отслеживания.

    🎯 Условие: { $condition }
    📍 Базовая цена: { $baseline }
    🏦 Рынок: { $market }
    🔁 Режим: { $mode }
mode-repeat = повторяющийся
mode-one-time = одноразовый
condition-percent-both = Изменение { $threshold } в любую сторону
condition-percent-up = Рост на { $threshold }
condition-percent-down = Падение на { $threshold }
condition-price-above = Цена выше { $threshold }
condition-price-below = Цена ниже { $threshold }
condition-mcap-above = Капитализация выше { $threshold }
condition-mcap-below = Капитализация ниже { $threshold }
condition-default = Ценовой алерт

## Alert limits

limit-user-token =
    { $limit ->
        [one] Максимум { $limit } алерт на токены. Удали алерт, чтобы добавить новый.
        [few] Максимум { $limit } алерта на токены. Удали алерт, чтобы добавить новый.
        [many] Максимум { $limit } алертов на токены. Удали алерт, чтобы добавить новый.
       *[other] Максимум { $limit } алерта на токены. Удали алерт, чтобы добавить новый.
    }
limit-user-nft =
    { $limit ->
        [one] Максимум { $limit } алерт на NFT. Удали алерт, чтобы добавить новый.
        [few] Максимум { $limit } алерта на NFT. Удали алерт, чтобы добавить новый.
        [many] Максимум { $limit } алертов на NFT. Удали алерт, чтобы добавить новый.
       *[other] Максимум { $limit } алерта на NFT. Удали алерт, чтобы добавить новый.
    }
limit-global-alerts-token = Price Bird достиг лимита алертов на токены. Попробуй позже.
limit-global-alerts-nft = Price Bird достиг лимита алертов на NFT. Попробуй позже.
limit-global-assets-token = Price Bird уже отслеживает максимальное число токенов. Добавь алерт на уже отслеживаемый токен или попробуй позже.
limit-global-assets-nft = Price Bird уже отслеживает максимальное число коллекций NFT. Добавь алерт на уже отслеживаемую коллекцию или попробуй позже.

## Alert list

no-alerts = Тут пока пусто. Используй <code>/alert BTC 10%</code> или создай алерт в меню.
alerts-list =
    📌 <b>Активные алерты</b> ({ $total })
    Нажми на алерт, чтобы изменить его.
delete-alert-usage = Использование: /deletealert 123
active-alert-not-found = Активный алерт не найден.
alert-deleted = Алерт #{ $id } удалён.
nothing-to-cancel = Нечего отменять.
asset-fallback = актив
market-cap-short = Кап.

## Alert descriptions

describe-percent-both = { $symbol }: изменение { $threshold }
describe-percent-up = { $symbol }: рост на { $threshold }
describe-percent-down = { $symbol }: падение на { $threshold }
describe-price-above = { $symbol } выше { $threshold }
describe-price-below = { $symbol } ниже { $threshold }
describe-mcap-above = { $symbol }: капитализация выше { $threshold }
describe-mcap-below = { $symbol }: капитализация ниже { $threshold }
describe-absolute = { $symbol }: изменение на { $threshold }
market-token = токен
market-cex = CEX
market-nft = флор NFT
direction-up = Вверх
direction-down = Вниз
direction-both = Вверх или вниз

## Alert settings

invalid-alert = Некорректный алерт.
alert-not-found = Алерт не найден.
alert-not-editable = Алерт больше нельзя редактировать.
alert-deleted-toast = Удалено
clear-expiry-before-resume = Сначала убери срок действия, потом возобнови.
field-market = 🏦 Рынок: { $value }
field-status = Статус: { $value }
field-mode = 🔁 Режим: { $value }
field-threshold = 🎯 Порог: { $value }
field-baseline = 📍 Базовая цена: { $value }
field-cooldown = ⏱ Кулдаун: { $value }
field-direction = ↕️ Направление: { $value }
field-expires = ⏳ Срок действия: { $value }
field-note = 📝 Заметка: { $value }
status-active = ▶️ активен
status-paused = ⏸ на паузе
note-none = нет
mode-one-time-removed = одноразовый, удаляется после срабатывания
mode-repeat-rebase = повторяющийся, базовая цена сдвигается к цене срабатывания
mode-repeat-reset = повторяющийся, срабатывает снова после сброса условия
button-pause = ⏸ Пауза
button-resume = ▶️ Возобновить
button-cooldown = ⏱ Кулдаун: { $value }
button-direction = Направление: { $value }
button-threshold = ✏️ Порог
button-note = 📝 Заметка
button-expires = ⏳ Срок: { $value }
button-delete = 🗑 Удалить
button-confirm-delete = ✅ Да, удалить
button-back-to-alerts = ↩️ Назад к алертам
confirm-delete = 🗑 Удалить <b>{ $description }</b>?
expiry-never = никогда
expiry-expired = истёк
expiry-in = через { $duration }
expiry-at = { $date } (через { $duration })
prompt-note = Отправь заметку, до 300 символов. Отправь -, чтобы её очистить.
prompt-cooldown = Отправь кулдаун, например 10s, 1m, 15m или 2h. Текущий: { $current }
prompt-expiry = Отправь срок действия, например 24h, 2d, 3mo или 1y. Отправь -, чтобы алерт не истекал. Текущий: { $current }
prompt-threshold-percent = Отправь новый порог в %. Текущий: { $current }
prompt-threshold-price = Отправь новую цену в { $units }. Текущая: { $current }
prompt-threshold-mcap = Отправь новую капитализацию в { $units }. Текущая: { $current }
units-usd = USD (напр. $0.023, 23m)
units-native = USD или { $symbol } (напр. $0.023, 23m, 1.2 { $symbol })

## Input errors

error-positive-number = Отправь корректное положительное число.
error-threshold-format = Отправь положительное конечное число не более чем с 36 знаками после запятой.
error-threshold-range = Порог должен быть положительным, конечным и не более чем с 36 знаками после запятой.
error-amount-format = Отправь число вида 0.023, 100k, 23m, 1b, 1e-6 или 0.0₄5, можно с единицей: $0.023, 1.2 ETH.
error-amount-not-positive = Значение должно быть положительным числом.
error-percent-format = Отправь процент вида 10, 2.5%, +5% или -5%.
error-currency-usd = Этот актив торгуется в USD, а не в { $unit }.
error-currency-native = Этот актив торгуется в USD или { $symbol }, а не в { $unit }.
error-duration-format = Укажи число с единицей: 15m, 24h, 2d, 5w, 3mo, 1y (также 15 min, 5 years).
error-duration-not-positive = Длительность должна быть положительной.
error-duration-too-short = Минимум { $min }.
error-duration-too-long = Максимум { $max }.
error-note-length = От 1 до 300 символов, или - чтобы очистить заметку.
error-alert-usage = Использование: /alert BTC 10%, /alert SOL +5% или /alert ETH > 70000
error-alert-missing-parts = Не хватает запроса актива или условия алерта.
error-alert-condition = Условие должно быть процентом, например 10%, +5% или -5%, или порогом, например > 70000, < 0.8 ETH или > 17m mc.
error-no-price = Нет доступной цены.
error-mcap-unavailable = Фактическая капитализация для этого актива недоступна.
error-url-https = Используй HTTPS-ссылку на порту 443.
error-url-invalid = Используй HTTPS-ссылку на порту 443, без логина/пароля и без фрагментов.
error-url-public = Адрес вебхука должен быть публичным.

## Settings

settings-private-only = Открой личный чат с Price Bird, чтобы управлять настройками.
settings-text =
    Настройки доставки

    Включай и выключай уведомления Price Bird. Установи свой часовой пояс, затем выбери часы тишины для беззвучных алертов. Выбери ссылку на монету для токен-алертов. При выключении уведомлений отменяются ожидающие отправки в Telegram. Алерты продолжают проверяться. Отдельные алерты можно поставить на паузу в /alerts.
settings-text-connections =
    Настройки доставки

    Включай и выключай уведомления Price Bird. Установи свой часовой пояс, затем выбери часы тишины для беззвучных алертов. Выбери ссылку на монету для токен-алертов. Алерты продолжают проверяться. Отдельные алерты можно поставить на паузу в /alerts.

    Выбери, куда отправлять алерты. Включи Price Bird, подключённое приложение или оба варианта. При выключении канала доставки отменяются его ожидающие отправки.
settings-trenchbook-hint = <a href="{ $url }">Trenchbook</a> использует тот же аккаунт Telegram; сначала запусти его бота.
settings-bird = Уведомления Price Bird: { $state }
settings-timezone = Часовой пояс: { $timezone }
settings-quiet-hours = Часы тишины: { $value }
settings-coin-link = Ссылка на монету: { $provider }
settings-language = 🌐 Язык: { $language }
settings-connection = { $name }: { $state }
settings-connect = Подключить { $name }
settings-add-webhook = Добавить свой вебхук
state-on = вкл
state-off = выкл
language-prompt = Выбери язык:
quiet-hours-text =
    Часы тишины: { $value }
    Алерты Price Bird будут приходить без звука.
quiet-from = с { $time }
quiet-to = до { $time }
quiet-turn-off = Выключить
quiet-turn-on = Включить 22:00-07:00
timezone-text =
    Часовой пояс: { $timezone }
    Часы тишины используют это местное время. Фиксированное смещение UTC не переходит автоматически на летнее время.
coin-link-text =
    Ссылка на монету: { $provider }
    Эта ссылка добавляется в токен-алерты, когда сервис поддерживает актив.
invalid-timezone-setting = Некорректная настройка часового пояса.
invalid-quiet-hours-setting = Некорректная настройка часов тишины.
invalid-coin-link = Некорректная ссылка на монету.
invalid-connection-action = Некорректное действие с подключением.
connection-not-found = Подключение не найдено.
integration-not-found = Интеграция не найдена.
admin-only-destination = Этот канал доставки доступен только админам.
admin-only-integrations = Интеграции доступны только админам.
admin-only-custom-webhooks = Свои вебхуки доступны только админам.
connections-limit = Можно подключить до { $limit } приложений.
custom-webhook-prompt =
    Отправь название и HTTPS-адрес вебхука, например:
    My app https://example.com/webhook

    /cancel, чтобы остановить.
custom-webhook-connected =
    { $name } подключён. Сохрани этот секрет подписи на своей стороне:
    { $secret }

    Запросы подписываются HMAC-SHA256. Настрой приёмник, затем включи подключение в настройках.
webhook-name-too-long = Название должно быть не длиннее 80 символов.
webhook-name-and-url = Отправь название, а затем HTTPS-ссылку.
new-signing-secret =
    Новый секрет подписи. Обнови приёмник перед включением доставки:
    { $secret }
enable-connection-first = Сначала включи это подключение.
delivery-already-pending = Доставка уже выполняется.
connection-host = Хост: { $host }
host-unavailable = недоступен
connection-notifications = Уведомления: { $state }
connection-last-delivery = Последняя доставка: { $status }
button-enable = Включить
button-disable = Выключить
button-send-test = Тест
button-retry-failure = Повторить попытку
button-rotate-secret = Сменить секрет подписи
button-disconnect = Отключить

## Notifications

notification-test = Проверка подключения Price Bird. Алерт не срабатывал.
notification-rule = 🎯 <b>Правило:</b> { $rule }
notification-price = 💵 <b>Цена:</b> { $price }
notification-floor = 🖼 <b>Флор:</b> { $native } { $symbol } ({ $usd })
notification-market-cap = 📊 <b>Капитализация:</b> { $value }
notification-dex = 🏦 <b>DEX:</b> { $dex }
notification-source = 🛰 <b>Источник:</b> { $source }
notification-links = 🔗 <b>Ссылки:</b> { $links }
notification-note = 📝 <b>Заметка:</b> { $note }
rule-percent-both = Изменение { $threshold } в любую сторону
rule-percent-up = Рост на { $threshold }
rule-percent-down = Падение на { $threshold }
rule-price-above = Цена выше { $threshold }
rule-price-below = Цена ниже { $threshold }
rule-mcap-above = Капитализация выше { $threshold }
rule-mcap-below = Капитализация ниже { $threshold }
rule-absolute = Изменение цены на { $threshold }

## Admin

admin-usage = Использование: /{ $command } 123456789
admin-whitelisted = { $telegram_id } добавлен в вайтлист.
admin-suspended = { $telegram_id } заблокирован.
admin-promoted = { $telegram_id } назначен админом.
admin-no-users = Пользователей нет.
admin-stats =
    Пользователи: { $users }
    Активные алерты: { $active_alerts }
    Отслеживаемые активы: { $watched_assets }
admin-debug-connect-trenchbook = Сначала подключи и включи Trenchbook.
admin-debug-no-alert = Нет предыдущего алерта для повтора.
admin-debug-queued = Алерт #{ $alert_id } поставлен в очередь для Trenchbook.

## Broadcast

broadcast-audience-prompt = 📣 <b>Новая рассылка</b>

    Кому отправить?
button-broadcast-all = 👥 Всем пользователям ({ $count })
button-broadcast-specific = 🎯 Отдельным пользователям
button-broadcast-cancel = ✖️ Отменить
broadcast-recipients-prompt = Отправьте Telegram ID или @username через пробел, запятую или с новой строки.
broadcast-recipients-found = 👥 Найдено получателей: { $count }
broadcast-recipients-missing = ⚠️ Не найдено: { $refs }
broadcast-recipients-none = Никто из этих пользователей не запускал бота. Отправьте другие ID или username.
broadcast-content-prompt = Отправьте пост: текст, фото, видео, GIF или файл. Форматирование и кастомные эмодзи сохранятся.
broadcast-confirm =
    📣 <b>Предпросмотр поста выше</b>

    👥 Получатели: <b>{ $count }</b> ({ $audience })
    🔘 Кнопки: { $buttons }
broadcast-audience-all = все пользователи
broadcast-audience-specific = выбранные пользователи
broadcast-buttons-none = нет
button-broadcast-add = ➕ Добавить кнопку
button-broadcast-remove = ↩️ Убрать последнюю кнопку
button-broadcast-send = ✅ Отправить { $count }
broadcast-button-text-prompt = Отправьте текст кнопки, до { $max } символов.
broadcast-button-action-prompt =
    Отправьте ссылку для <b>{ $text }</b> (https://…, t.me/… или tg://…)
    или callback data до { $max } байт.
broadcast-started = 📤 Отправляем { $count } пользователям…
broadcast-finished = 📣 Рассылка завершена: доставлено { $sent } из { $total }, ошибок { $failed }.
broadcast-cancelled = Рассылка отменена.
broadcast-expired = Эта рассылка уже неактивна.
broadcast-no-recipients = Некому отправлять.
error-broadcast-button-text = Текст кнопки должен содержать 1–{ $max } символов.
error-broadcast-button-url = Отправьте корректную ссылку https://, t.me/ или tg://.
error-broadcast-button-data = Callback data должна содержать 1–{ $max } байт.
error-broadcast-recipient = Это не Telegram ID и не @username: { $value }
error-broadcast-recipients-empty = Отправьте хотя бы один Telegram ID или @username.
