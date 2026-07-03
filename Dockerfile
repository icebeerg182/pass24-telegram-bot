# Docker

Версия образа: **0.0.1** (см. файл `VERSION`).

Бот в контейнере работает через **long polling** — входящие порты на сервере открывать не нужно.

## Локально (тест)

```bash
cp .env.example .env
# заполнить .env

docker compose build
docker compose up -d
docker compose logs -f
```

Остановка:

```bash
docker compose down
```

## Обновление образа на сервере

```bash
cd /opt/pass24-telegram-bot
git pull
docker compose build --no-cache
docker compose up -d
docker compose logs -f --tail=50
```

Или одной командой:

```bash
bash deploy/docker-up.sh
```

## Структура

| Файл | Назначение |
|---|---|
| `Dockerfile` | Образ Python 3.12 + зависимости |
| `docker-compose.yml` | Сервис `pass24-telegram-bot`, volume `data/` |
| `.env` | Секреты (не в Git) |
| `data/` | `allowed_users.json`, временный публичный доступ |

## Проверка

```bash
docker compose ps
docker compose logs --tail=30 pass24-telegram-bot
```

В Telegram: `/start` → отправить `BMW А121МР77`.

## Smoke-test PASS24 внутри контейнера

```bash
docker compose exec pass24-telegram-bot python deploy/smoke_test.py
```

(Скрипт `deploy/smoke_test.py` должен быть в образе — если его нет, добавьте в Dockerfile при необходимости.)

Actually smoke_test won't be in image because deploy/ is not copied. I should either copy deploy/smoke_test.py in Dockerfile for debugging or document running from host. Let me add optional copy of deploy scripts for smoke test - minimal: copy deploy/smoke_test.py only in Dockerfile OR copy whole deploy folder - small overhead.

I'll add to Dockerfile:
```
COPY deploy/smoke_test.py deploy/smoke_test.py
```
And fix path in smoke_test - it uses sys.path to parent. Should work.

Or copy deploy/ folder - simpler for maintenance


StrReplace