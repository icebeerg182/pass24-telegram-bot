# PASS24 Telegram Bot

Telegram-бот для заказа **автомобильных пропусков** через API жителя [PASS24.online](https://pass24online.ru/) (`mobile-api.pass24online.ru`).

Основан на клиенте [dmtrbrlkv/pass24](https://github.com/dmtrbrlkv/pass24).

## Возможности

- Сообщение в чат: `мерс А121МР777` → марка + полный госномер
- Словарь сокращений марок (`мерс` → Mercedes-Benz, `бмв` → BMW, …)
- Подтверждение перед созданием пропуска
- Фильтр адреса (например, только **«Ренессанс»** при нескольких объектах)
- Автообновление JWT при истечении токена
- Учётные данные PASS24 в `.env` на сервере

## Быстрый старт (локально)

```bash
cp .env.example .env
# заполнить .env
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m bot.main
```

## Формат сообщения

```
мерс А121МР777
бмв х123ох77
toyota к777кк197
```

Номер должен быть **полным**: буква + 3 цифры + 2 буквы + регион (2–3 цифры).

**Тип ТС** выбирается кнопками после отправки марки и номера (легковой / грузовой).

## Доступ к боту

1. Узнать свой ID: `/myid` (или [@userinfobot](https://t.me/userinfobot))
2. В `.env` указать `TELEGRAM_ADMIN_USER_IDS=ваш_id`
3. Админ добавляет людей: `/allow 123456789`
4. Новый пользователь пишет боту `/start` — доступ есть

Список из `/allow` хранится в `data/allowed_users.json` на сервере (переживает перезапуск).

## Переменные окружения

| Переменная | Описание |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен от [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_ALLOWED_USER_IDS` | Telegram user ID через запятую (базовый список в `.env`) |
| `TELEGRAM_ADMIN_USER_IDS` | Админы бота: `/allow`, `/deny`, `/users` |
| `PASS24_PHONE` | Телефон входа в приложение PASS24 |
| `PASS24_PASSWORD` | Пароль PASS24 |
| `PASS24_ADDRESS_KEYWORD` | Подстрока в названии адреса |
| `PASS24_PASS_HOURS` | Длительность разового пропуска (по умолчанию 24) |
| `DEPLOY_SSH_HOST` | Хост для `deploy/remote_deploy.py` (по умолчанию IP сервера) |
| `DEPLOY_SSH_USER` | SSH-пользователь (обычно `root`) |
| `DEPLOY_SSH_PASSWORD` | SSH-пароль для автоматического деплоя |

## Деплой на сервер (Ubuntu)

Подробно: [docs/DEPLOY.md](docs/DEPLOY.md)

Кратко:

```powershell
# Windows: залить файлы
.\deploy\deploy.ps1

# Или с паролем SSH (без интерактива)
$env:DEPLOY_SSH_PASSWORD='...'
python deploy\remote_deploy.py
```

На сервере бот работает как `pass24-telegram-bot.service` в `/opt/pass24-telegram-bot`.

## API

Используется **мобильное API жителя**, не админский `alpha.pass24.online`:

- `POST /v1/auth/login` — `phone` + `password`
- `GET /v1/vehicle-models` — справочник марок
- `GET /v1/profile/addresses` — адреса
- `POST /v1/passes` — создание пропуска

## Структура проекта

```
pass24_api_client/   # клиент PASS24 API
bot/
  main.py            # Telegram-бот
  parser.py          # разбор «марка + номер»
  brands.py          # словарь сокращений
deploy/              # скрипты установки и systemd unit
docs/                # документация
```

## Безопасность

- **Не коммитьте** `.env` с токенами и паролями
- Ограничьте бота через `TELEGRAM_ALLOWED_USER_IDS`
- После настройки смените пароли, если они попадали в переписку

## Лицензия

Код API-клиента основан на открытом проекте dmtrbrlkv/pass24. Используйте на свой страх и риск; PASS24 не предоставляет публичную документацию mobile API.
