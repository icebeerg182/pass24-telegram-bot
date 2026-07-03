# Деплой на сервер (Ubuntu)

> **Рекомендуется:** [DOCKER.md](DOCKER.md) и [MIGRATE_TO_DOCKER.md](MIGRATE_TO_DOCKER.md)  
> Ниже — **legacy**-установка через systemd (Python venv).

Бот ставится **изолированно**: только `/opt/pass24-telegram-bot` и systemd unit `pass24-telegram-bot.service`. Другие сервисы не трогаются.

## Требования на сервере

- Ubuntu 24.04 (или Debian-подобный)
- `python3`, `python3-venv` (скрипт установит при необходимости)
- Исходящий HTTPS до `mobile-api.pass24online.ru` и `api.telegram.org`

## 1. Подготовка `.env` локально

```bash
cp .env.example .env
```

Заполните все поля. Для деплоя по SSH добавьте `DEPLOY_SSH_PASSWORD`.

## 2. Деплой с Windows (PowerShell)

```powershell
cd C:\path\to\pass24-telegram-bot
# отредактируйте deploy\deploy.ps1 — уберите секреты, используйте .env
.\deploy\deploy.ps1
```

Или автоматически через Paramiko:

```powershell
$env:DEPLOY_SSH_PASSWORD='ваш_ssh_пароль'
# TELEGRAM_* и PASS24_* читаются из .env в корне проекта
python deploy\remote_deploy.py
```

## 3. Деплой вручную на сервере

Если файлы уже в `/opt/pass24-telegram-bot`:

```bash
bash /opt/pass24-telegram-bot/deploy/finish-on-server.sh
```

## 4. Проверка

```bash
systemctl status pass24-telegram-bot.service
journalctl -u pass24-telegram-bot.service -f
```

Smoke-test PASS24 без бота:

```bash
/opt/pass24-telegram-bot/.venv/bin/python /opt/pass24-telegram-bot/deploy/smoke_test.py
```

Ожидаемый вывод:

```
login ok
address: ...Ренессанс...
models: <число>
```

## 5. Обновление версии

```powershell
python deploy\remote_deploy.py
```

Скрипт перезаливает файлы и перезапускает только `pass24-telegram-bot.service`.

## Частые проблемы

### CRLF (`$'\r': command not found`)

Файлы загружены с Windows. На сервере:

```bash
find /opt/pass24-telegram-bot -type f \( -name "*.sh" -o -name "*.py" \) -exec sed -i 's/\r$//' {} +
```

В репозитории для `*.sh` задан `.gitattributes` с `eol=lf`.

### `python3-venv` не найден

```bash
apt-get update && apt-get install -y python3-venv python3-pip
```

### Адрес «Ренессанс» не найден

Проверьте список адресов в smoke_test / приложении PASS24. Уточните `PASS24_ADDRESS_KEYWORD` в `.env`.
