# Установка на сервер (Docker)

Версия **0.0.1**. Бот работает в контейнере `pass24-telegram-bot` (long polling).  
**Порты на сервере открывать не нужно.**

---

## Установка одной командой (рекомендуется)

После клонирования репозитория:

```bash
cd /opt/pass24-telegram-bot
bash deploy/install.sh
```

Скрипт **интерактивный**:

1. Проверяет и при необходимости ставит Docker
2. Запрашивает токен Telegram, ID админов, логин/пароль PASS24
3. **Проверяет каждый кред** (Telegram `getMe`, PASS24 login)
4. При нескольких адресах показывает список и помогает выбрать `PASS24_ADDRESS_KEYWORD`
5. Создаёт `.env`, собирает образ и запускает бот
6. Запускает smoke-test в контейнере

Полный цикл с нуля:

```bash
git clone git@github.com:YOUR_GITHUB_USER/pass24-telegram-bot.git /opt/pass24-telegram-bot
cd /opt/pass24-telegram-bot
bash deploy/install.sh
```

---

## Ручная установка

### 1. Docker

```bash
apt-get update
apt-get install -y docker.io docker-compose-v2
systemctl enable --now docker
```

### 2. Настроить `.env`

```bash
cp .env.example .env
nano .env
chmod 600 .env
mkdir -p data
```

Проверка кредов без запуска бота:

```bash
python3 deploy/validate_env.py
```

### 3. Запуск

```bash
docker compose up -d --build
```

---

## Проверка

```bash
docker compose ps
docker compose logs -f --tail=50
docker compose exec pass24-telegram-bot python deploy/smoke_test.py
```

В Telegram: `/start` → `BMW А121МР77`

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
| `bash deploy/install.sh` | Переустановка / новый `.env` |
| `python3 deploy/validate_env.py` | Проверка `.env` |
