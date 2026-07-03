# PASS24 Telegram Bot

**Версия: 0.0.1**

Telegram-бот для заказа **автомобильных пропусков** через API жителя [PASS24.online](https://pass24online.ru/).

## Возможности

- Пропуск по сообщению: `BMW А121МР77`, `мерс А121МР777`, две строки и т.д.
- Кнопки **Изменить** / **Удалить** под созданным пропуском
- Доступ: `/allow`, `/deny`, `/open 12|24|48`, `/close`
- Фильтр адреса при нескольких объектах в аккаунте (`PASS24_ADDRESS_KEYWORD`)

## Быстрый старт (Docker)

```bash
cp .env.example .env
# заполнить .env
mkdir -p data
docker compose up -d --build
docker compose logs -f
```

## Документация

| Файл | Описание |
|---|---|
| [docs/SERVER_INSTALL.md](docs/SERVER_INSTALL.md) | Установка на сервер |
| [docs/DOCKER.md](docs/DOCKER.md) | Docker-команды |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Как устроен бот |
| [CHANGELOG.md](CHANGELOG.md) | История версий |

## Переменные окружения

См. `.env.example` — минимум: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ADMIN_USER_IDS`, `PASS24_PHONE`, `PASS24_PASSWORD`.

## Структура

```
pass24_api_client/   # клиент PASS24 API
bot/                 # Telegram-бот
Dockerfile
docker-compose.yml
deploy/              # smoke-test и docker-up.sh
docs/
```

## Безопасность

Не коммитьте `.env` и `data/allowed_users.json`.
