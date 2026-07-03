# Docker-деплой

Рекомендуемый способ запуска на сервере — **Docker Compose**.

Миграция со старого systemd: [MIGRATE_TO_DOCKER.md](MIGRATE_TO_DOCKER.md)

## Требования

- Docker + Docker Compose v2
- Исходящий HTTPS: `api.telegram.org`, `mobile-api.pass24online.ru`
- Файл `.env` в каталоге проекта

## Быстрый старт на сервере

```bash
cd /opt/pass24-telegram-bot
cp .env.example .env   # если .env ещё нет
# заполнить .env
mkdir -p data
docker compose up -d --build
docker compose logs -f
```

## Обновление

```bash
git pull
bash deploy/docker-up.sh
```

## Команды

| Команда | Действие |
|---|---|
| `docker compose ps` | Статус |
| `docker compose logs -f` | Логи |
| `docker compose restart` | Перезапуск |
| `docker compose down` | Остановка |
| `docker compose exec pass24-telegram-bot python deploy/smoke_test.py` | Проверка PASS24 API |

## Legacy: systemd

Старый способ через `pass24-telegram-bot.service` описан в [DEPLOY.md](DEPLOY.md).  
Для новых установок используйте Docker.
