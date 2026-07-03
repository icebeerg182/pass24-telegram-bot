# Установка на сервер (Docker)

Версия **0.0.1**. Бот работает в контейнере `pass24-telegram-bot` (long polling).  
**Порты на сервере открывать не нужно.**

---

## Требования

- Linux с **Docker** и **Docker Compose v2**
- Исходящий HTTPS: `api.telegram.org`, `mobile-api.pass24online.ru`
- Файл `.env` с секретами (в Git не хранится)

---

## 1. Подготовка

```bash
# если обновляете установку — сохраните настройки
[ -f /opt/pass24-telegram-bot/.env ] && cp /opt/pass24-telegram-bot/.env /root/pass24.env.backup

rm -rf /opt/pass24-telegram-bot

docker --version && docker compose version
```

Если Docker не установлен:

```bash
apt-get update
apt-get install -y docker.io docker-compose-v2
systemctl enable --now docker
```

---

## 2. Клонировать репозиторий

```bash
git clone https://github.com/YOUR_GITHUB_USER/pass24-telegram-bot.git /opt/pass24-telegram-bot
cd /opt/pass24-telegram-bot
```

SSH (если настроен ключ на сервере):

```bash
git clone git@github.com:YOUR_GITHUB_USER/pass24-telegram-bot.git /opt/pass24-telegram-bot
```

---

## 3. Настроить `.env`

```bash
cp /root/pass24.env.backup .env
# или: cp .env.example .env && nano .env

chmod 600 .env
mkdir -p data
```

Минимум в `.env`:

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ADMIN_USER_IDS=YOUR_TELEGRAM_ID
PASS24_PHONE=+79...
PASS24_PASSWORD=...
PASS24_ADDRESS_KEYWORD=
```

---

## 4. Запустить

```bash
docker compose up -d --build
```

---

## Проверка

```bash
docker compose ps
docker compose logs -f --tail=50
```

В Telegram: `/start` → `BMW А121МР77`

Проверка PASS24 API:

```bash
docker compose exec pass24-telegram-bot python deploy/smoke_test.py
```

---

## Обновление

```bash
cd /opt/pass24-telegram-bot
git pull
bash deploy/docker-up.sh
```

---

## Полезные команды

| Команда | Действие |
|---|---|
| `docker compose ps` | Статус |
| `docker compose logs -f` | Логи |
| `docker compose restart` | Перезапуск |
| `docker compose down` | Остановка |
