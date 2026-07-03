# PASS24 Telegram Bot

Telegram-бот для заказа **автомобильных пропусков** через mobile API жителя [PASS24.online](https://pass24online.ru/).

**Версия:** 0.0.1 · **Репозиторий:** [github.com/icebeerg182/pass24-telegram-bot](https://github.com/icebeerg182/pass24-telegram-bot)

## Для кого

Для жителей ЖК с пропускной системой PASS24, у которых уже есть аккаунт в приложении PASS24.online (логин по телефону). Бот работает как мобильное приложение: создаёт разовые пропуска на ваш адрес.

## Возможности

- Пропуск одним сообщением: `BMW А121МР77`, `мерс А121МР777`, марка и номер в двух строках
- Кнопки **Изменить** и **Удалить** под созданным пропуском
- Управление доступом: белый список, временное открытие на 12/24/48 часов
- Выбор адреса, если в аккаунте несколько объектов (`PASS24_ADDRESS_KEYWORD`)

## Быстрый старт на сервере

Нужны: Linux-сервер с Docker, токен бота от [@BotFather](https://t.me/BotFather), логин и пароль PASS24.

```bash
git clone https://github.com/icebeerg182/pass24-telegram-bot.git /opt/pass24-telegram-bot
cd /opt/pass24-telegram-bot
bash deploy/install.sh
```

Скрипт интерактивно запросит креды, проверит Telegram и PASS24 и запустит контейнер.  
Входящие порты на сервере не нужны — бот использует long polling.

Подробнее: [docs/SERVER_INSTALL.md](docs/SERVER_INSTALL.md)

## Локальный запуск (Docker)

```bash
git clone https://github.com/icebeerg182/pass24-telegram-bot.git
cd pass24-telegram-bot
cp .env.example .env
# заполнить .env
python3 deploy/validate_env.py   # проверка кредов
mkdir -p data
docker compose up -d --build
docker compose logs -f
```

## Команды бота

| Команда | Кто | Описание |
|---|---|---|
| `BMW А121МР77` | все | Создать пропуск |
| `/start`, `/help` | все | Справка |
| `/myid` | все | Узнать свой Telegram ID |
| `/allow <id>` | админ | Постоянный доступ пользователю |
| `/deny <id>` | админ | Забрать доступ |
| `/open 12\|24\|48` | админ | Открыть бот для всех на N часов |
| `/close` | админ | Закрыть временный доступ |
| `/users` | админ | Список пользователей с доступом |

## Переменные окружения

См. [`.env.example`](.env.example). Минимум:

| Переменная | Описание |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен от @BotFather |
| `TELEGRAM_ADMIN_USER_IDS` | Telegram ID админов (через запятую) |
| `PASS24_PHONE` | Телефон аккаунта PASS24 |
| `PASS24_PASSWORD` | Пароль PASS24 |

Опционально: `PASS24_ADDRESS_KEYWORD`, `PASS24_PASS_HOURS`, `TELEGRAM_ALLOWED_USER_IDS`.

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
bot/                 # Telegram-бот (парсер, доступ, handlers)
deploy/              # install.sh, validate_env.py, smoke_test.py
Dockerfile
docker-compose.yml
docs/
```

## Безопасность

- Не коммитьте `.env` и `data/allowed_users.json`
- Храните токен бота и пароль PASS24 только на сервере
- После первого запуска добавьте себя админом через `TELEGRAM_ADMIN_USER_IDS` в `.env`

## Основа проекта

Клиент `pass24_api_client/` основан на [dmtrbrlkv/pass24](https://github.com/dmtrbrlkv/pass24) — Python-клиент mobile API `mobile-api.pass24online.ru`.

## Лицензия

Проект не аффилирован с PASS24.online. Используйте на свой риск; API может измениться без предупреждения.
