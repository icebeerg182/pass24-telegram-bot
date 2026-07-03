# PASS24 Telegram Bot

**Версия: 0.0.1** · Docker only

Telegram-бот для заказа **автомобильных пропусков** через API жителя [PASS24.online](https://pass24online.ru/).

## Возможности

- Пропуск по сообщению: `BMW А121МР77`, `мерс А121МР777`, две строки и т.д.
- Кнопки **Изменить** / **Удалить** под созданным пропуском
- Доступ: `/allow`, `/open 12|24|48`, `/close`
- Фильтр адреса (например, «Ренессанс»)

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
| [docs/SERVER_INSTALL.md](docs/SERVER_INSTALL.md) | Установка на сервер с нуля |
| [docs/DOCKER.md](docs/DOCKER.md) | Docker-команды |
| [docs/GITHUB.md](docs/GITHUB.md) | Публикация на GitHub |
| [CHANGELOG.md](CHANGELOG.md) | История версий |

## GitHub — чистая публикация v0.0.1

На ПК (один коммит, без старой истории):

```powershell
cd C:\Users\icebeerg\Projects\pass24-telegram-bot
powershell -ExecutionPolicy Bypass -File deploy\git_fresh_publish.ps1
```

## Переменные окружения

См. `.env.example` — минимум: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ADMIN_USER_IDS`, `PASS24_PHONE`, `PASS24_PASSWORD`.

## Структура

```
pass24_api_client/   # клиент PASS24 API
bot/                 # Telegram-бот
Dockerfile
docker-compose.yml
VERSION
docs/
deploy/
```

## Безопасность

Не коммитьте `.env` и `data/allowed_users.json`.
