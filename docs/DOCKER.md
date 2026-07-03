# Docker-деплой

Версия **0.0.1**. Установка с нуля: [SERVER_INSTALL.md](SERVER_INSTALL.md)

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

Файлы `deploy/install.sh` и `pass24-telegram-bot.service` оставлены в репозитории, но **не используются**. Запуск только через Docker.
