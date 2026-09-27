# PASS24 Telegram Bot

Telegram-бот для заказа **автомобильных пропусков** через mobile API жителя [PASS24.online](https://pass24online.ru/).

**Версия:** 0.0.6 · **Репозиторий:** [github.com/icebeerg182/pass24-telegram-bot](https://github.com/icebeerg182/pass24-telegram-bot)

## Для кого

Для жителей ЖК с пропускной системой PASS24, у которых уже есть аккаунт в приложении PASS24.online (логин по телефону). Бот работает как мобильное приложение: создаёт разовые пропуска на ваш адрес.

## Возможности

- Пропуск одним сообщением: `BMW А121МР77`, `мерс А121МР777`, `маруся А123ВС77`; для адресов без региона — `BMW А121МР`
- Словарь сокращений марок + fallback через **Groq LLM**, если парсер не распознал бренд
- Ссылка Яндекс Доставки (`dostavka.yandex.ru/route/#…`) — автоподстановка марки и номера курьера
- Нормализация длинных названий (Wheely и т.п.): `Mercedes-Maybach S-Класс Z223, У 061 ЕН 550`
- Кнопки **Изменить** / **Удалить** под созданным пропуском
- Управление доступом: белый список, временное открытие на 12/24/48 часов
- Выбор адреса (`PASS24_ADDRESS_KEYWORD` или кнопка «📍 Адрес»)
- Опционально: тип ТС (легковой/грузовой) и подтверждение перед созданием

## Быстрый старт на сервере

Нужны: Linux-сервер с Docker, токен бота от [@BotFather](https://t.me/BotFather), логин и пароль PASS24.

```bash
git clone https://github.com/icebeerg182/pass24-telegram-bot.git /opt/pass24-telegram-bot
cd /opt/pass24-telegram-bot
bash deploy/install.sh
```

Скрипт интерактивно запросит креды, проверит Telegram и PASS24 и запустит контейнер.  
Входящие порты не нужны — long polling.

Подробнее: [docs/SERVER_INSTALL.md](docs/SERVER_INSTALL.md)

## Локальный запуск (Docker)

```bash
git clone https://github.com/icebeerg182/pass24-telegram-bot.git
cd pass24-telegram-bot
cp .env.example .env
# заполнить .env
python3 deploy/validate_env.py
mkdir -p data
docker compose up -d --build
docker compose logs -f
```

## Команды бота

| Команда | Кто | Описание |
|---|---|---|
| `BMW А121МР77` | все | Создать пропуск |
| ссылка `dostavka.yandex.ru/route/#…` | все | Взять марку/номер из трекинга |
| `/start`, `/help` | все | Справка |
| `/myid` | все | Узнать свой Telegram ID |
| `/allow <id>` | админ | Постоянный доступ |
| `/deny <id>` | админ | Забрать доступ |
| `/open 12\|24\|48` | админ | Открыть бот для всех на N часов |
| `/close` | админ | Закрыть временный доступ |
| `/users` | админ | Список доступа |

## Переменные окружения

См. [`.env.example`](.env.example). Минимум:

| Переменная | Описание |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен от @BotFather |
| `TELEGRAM_ADMIN_USER_IDS` | Telegram ID админов |
| `PASS24_PHONE` | Телефон аккаунта PASS24 |
| `PASS24_PASSWORD` | Пароль PASS24 |

Опционально: `PASS24_ADDRESS_KEYWORD`, `PASS24_PASS_HOURS`, `TELEGRAM_ALLOWED_USER_IDS`.

Поведение бота:

| Переменная | По умолчанию | Описание |
|---|---|---|
| `BOT_ASK_VEHICLE_TYPE` | `false` | Спрашивать легковой/грузовой |
| `BOT_CONFIRM_BEFORE_CREATE` | `true` | Подтверждение перед созданием |
| `BOT_ENABLE_ADDRESS_PICKER` | `false` | Кнопка «📍 Адрес» |
| `BOT_REQUIRE_FULL_PLATE` | `true` | `true` — номер с регионом; `false` — достаточно `А121МР` |

LLM fallback (опционально, [Groq](https://console.groq.com/)):

| Переменная | По умолчанию | Описание |
|---|---|---|
| `BOT_LLM_BRAND_RESOLVER` | `false` | Включить LLM, если парсер не нашёл марку |
| `BOT_LLM_PROVIDER` | `groq` | Провайдер |
| `BOT_LLM_API_KEY` | пусто | API-ключ Groq |
| `BOT_LLM_MODEL` | `llama-3.3-70b-versatile` | Модель |

Удачные ответы LLM пишутся в `data/brands_learned.json` (не коммитить).

## Документация

| Файл | Описание |
|---|---|
| [docs/SERVER_INSTALL.md](docs/SERVER_INSTALL.md) | Установка на сервер |
| [docs/DOCKER.md](docs/DOCKER.md) | Docker-команды и обновление |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Как устроен бот |
| [CHANGELOG.md](CHANGELOG.md) | История версий |

## Структура проекта

```
pass24_api_client/   # клиент PASS24 mobile API
bot/                 # Telegram-бот (парсер, LLM fallback, handlers)
deploy/              # install.sh, validate_env.py, smoke_test.py
Dockerfile
docker-compose.yml
docs/
```

## Безопасность

- Не коммитьте `.env`, `data/allowed_users.json`, `data/brands_learned.json`
- Храните токен бота, пароль PASS24 и `BOT_LLM_API_KEY` только на сервере
- После первого запуска задайте себя в `TELEGRAM_ADMIN_USER_IDS`

## Основа проекта

Клиент `pass24_api_client/` основан на [dmtrbrlkv/pass24](https://github.com/dmtrbrlkv/pass24) — Python-клиент mobile API `mobile-api.pass24online.ru`.

Этот репозиторий — отдельный проект (Telegram-бот, Docker, парсер, LLM fallback), а не форк на GitHub.

## Лицензия

Проект не аффилирован с PASS24.online. Используйте на свой риск; API может измениться без предупреждения.
