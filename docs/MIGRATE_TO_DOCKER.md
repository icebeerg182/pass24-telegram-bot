# Миграция на Docker (с systemd)

Пошаговая инструкция для сервера **без затрагивания других сервисов**.

Бот будет работать в **отдельном контейнере** `pass24-telegram-bot`. Другие Docker-контейнеры и systemd-сервисы на сервере не меняются.

---

## Что будет сделано

| Было | Станет |
|---|---|
| `systemd` unit `pass24-telegram-bot.service` | Остановлен и отключён |
| Python venv в `/opt/pass24-telegram-bot/.venv` | Не используется (можно удалить позже) |
| Код + `.env` в `/opt/pass24-telegram-bot` | Тот же каталог |
| `data/allowed_users.json` | Сохраняется (volume) |

**Важно:** перед запуском Docker обязательно остановите systemd-бота. Два экземпляра с одним токеном Telegram конфликтуют.

---

## Шаг 1. Подключитесь к серверу

```bash
ssh root@178.17.52.193
```

---

## Шаг 2. Резервная копия

```bash
BACKUP=/root/pass24-backup-$(date +%Y%m%d)
mkdir -p "$BACKUP"
cp -a /opt/pass24-telegram-bot/.env "$BACKUP/"
cp -a /opt/pass24-telegram-bot/data "$BACKUP/" 2>/dev/null || true
echo "Бэкап: $BACKUP"
```

---

## Шаг 3. Остановить старый systemd-бот

```bash
systemctl stop pass24-telegram-bot.service
systemctl disable pass24-telegram-bot.service
systemctl status pass24-telegram-bot.service
```

Должно быть `inactive (dead)`.

---

## Шаг 4. Установить Docker (если ещё нет)

Проверка:

```bash
docker --version
docker compose version
```

Если команды не найдены:

```bash
apt-get update
apt-get install -y docker.io docker-compose-v2
systemctl enable --now docker
```

Это **не** переустанавливает систему и не трогает другие сервисы — только добавляет Docker.

---

## Шаг 5. Обновить код из GitHub

```bash
cd /opt/pass24-telegram-bot
git pull
```

Если репозитория нет:

```bash
cd /opt
mv pass24-telegram-bot pass24-telegram-bot-old
git clone git@github.com:icebeerg182/pass24-telegram-bot.git
cp pass24-telegram-bot-old/.env pass24-telegram-bot/
cp -a pass24-telegram-bot-old/data pass24-telegram-bot/ 2>/dev/null || true
cd pass24-telegram-bot
```

---

## Шаг 6. Запустить контейнер

**Автоматически:**

```bash
cd /opt/pass24-telegram-bot
sed -i 's/\r$//' deploy/migrate-to-docker.sh deploy/docker-up.sh
bash deploy/migrate-to-docker.sh
```

**Или вручную:**

```bash
cd /opt/pass24-telegram-bot
mkdir -p data
docker compose build
docker compose up -d
```

---

## Шаг 7. Проверка

```bash
docker compose ps
docker compose logs -f --tail=50 pass24-telegram-bot
```

В Telegram: `/start` → `BMW А121МР77` → пропуск создаётся.

---

## Шаг 8. Уборка (опционально, после проверки)

Удалить старый Python venv:

```bash
rm -rf /opt/pass24-telegram-bot/.venv
```

Удалить systemd unit:

```bash
rm -f /etc/systemd/system/pass24-telegram-bot.service
systemctl daemon-reload
```

Старую папку после `git clone` (если создавали):

```bash
rm -rf /opt/pass24-telegram-bot-old
```

---

## Обновление бота в будущем

На сервере:

```bash
cd /opt/pass24-telegram-bot
git pull
bash deploy/docker-up.sh
```

С Windows (после `git push`):

```powershell
ssh root@178.17.52.193 "cd /opt/pass24-telegram-bot && git pull && bash deploy/docker-up.sh"
```

---

## Откат на systemd (если что-то пошло не так)

```bash
cd /opt/pass24-telegram-bot
docker compose down
bash deploy/finish-on-server.sh
systemctl enable --now pass24-telegram-bot.service
```

---

## Частые проблемы

### Бот не отвечает / дублирует сообщения

Убедитесь, что systemd **остановлен** и работает **только** Docker:

```bash
systemctl is-active pass24-telegram-bot.service   # должен быть inactive
docker compose ps                                # pass24-telegram-bot Up
```

### `permission denied` на data/

```bash
chown -R 10001:10001 /opt/pass24-telegram-bot/data
docker compose restart
```

### Конфликт имён контейнера

Контейнер называется `pass24-telegram-bot` — уникальное имя, другие контейнеры не затрагиваются.

```bash
docker ps -a | grep pass24
```
