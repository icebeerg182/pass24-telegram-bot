# PASS24 Telegram Bot

**Версия: 0.0.1**

Telegram-бот для заказа **автомобильных пропусков** через API жителя [PASS24.online](https://pass24online.ru/) (`mobile-api.pass24online.ru`).

Основан на клиенте [dmtrbrlkv/pass24](https://github.com/dmtrbrlkv/pass24).

## Возможности

- Сообщение в чат → пропуск создаётся сразу
- Гибкий формат: марка до/после номера, пробелы, две строки
- Словарь сокращений марок (`мерс`, `жигули`, `li` → LiXiang, …)
- Кнопки **Изменить** и **Удалить** под созданным пропуском
- Доступ: доверенные пользователи + временное открытие `/open 12|24|48`
- Фильтр адреса (например, **«Ренессанс»**)
- Запуск в **Docker** (рекомендуется) или systemd (legacy)

## Быстрый старт (Docker)

```bash
cp .env.example .env
# заполнить .env
mkdir -p data
docker compose up -d --build
docker compose logs -f
```

Подробно: [docs/DOCKER.md](docs/DOCKER.md)

## Быстрый старт (локально без Docker)

```bash
cp .env.example .env
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m bot.main
```

## Формат сообщения

```
мерс А121МР777
А121МР77 BMW
BMW А121МР77 серый
BMW А 121 МР 77
BMW
A121MP77
```

## Доступ к боту

1. `/myid` — узнать Telegram ID
2. `.env`: `TELEGRAM_ADMIN_USER_IDS=ваш_id`
3. `/allow 123456789` — постоянный доступ
4. `/open 24` — открыть для всех на 24 часа (админ)

## Переменные окружения

| Переменная | Описание |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_ADMIN_USER_IDS` | Админы бота |
| `TELEGRAM_ALLOWED_USER_IDS` | Белый список (опционально) |
| `PASS24_PHONE` / `PASS24_PASSWORD` | Учётка PASS24 |
| `PASS24_ADDRESS_KEYWORD` | Подстрока в названии адреса |
| `PASS24_PASS_HOURS` | Длительность пропуска (часы) |

Полный список: `.env.example`

## Деплой на сервер

| Способ | Документация |
|---|---|
| **Docker** (рекомендуется) | [docs/DOCKER.md](docs/DOCKER.md) |
| Миграция systemd → Docker | [docs/MIGRATE_TO_DOCKER.md](docs/MIGRATE_TO_DOCKER.md) |
| systemd (legacy) | [docs/DEPLOY.md](docs/DEPLOY.md) |

## GitHub

Публикация и теги версий: [docs/GITHUB.md](docs/GITHUB.md)

```powershell
cd C:\Users\icebeerg\Projects\pass24-telegram-bot
git add .
git commit -m "Release 0.0.1: Docker deployment"
git tag -a v0.0.1 -m "Version 0.0.1"
git push origin main
git push origin v0.0.1
```

## Структура проекта

```
pass24_api_client/   # клиент PASS24 API
bot/                 # Telegram-бот
deploy/              # скрипты деплоя
docs/                # документация
Dockerfile
docker-compose.yml
VERSION              # 0.0.1
CHANGELOG.md
```

## Безопасность

- Не коммитьте `.env`
- `data/allowed_users.json` — только на сервере
- Ограничьте доступ через `TELEGRAM_ADMIN_USER_IDS`

## Лицензия

Код API-клиента основан на [dmtrbrlkv/pass24](https://github.com/dmtrbrlkv/pass24). PASS24 не публикует документацию mobile API — используйте на свой риск.
