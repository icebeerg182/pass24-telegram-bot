# Установка на сервер (Docker, с нуля)

Версия **0.0.1**. Бот работает в одном контейнере `pass24-telegram-bot`.  
Другие сервисы на сервере **не затрагиваются**.

---

## Шаг 0. Остановить старый systemd-бот (если был)

```bash
systemctl stop pass24-telegram-bot.service 2>/dev/null || true
systemctl disable pass24-telegram-bot.service 2>/dev/null || true
```

---

## Шаг 1. Сохранить `.env`

```bash
cp /opt/pass24-telegram-bot/.env /root/pass24.env.backup
```

Если файла нет — создадите на шаге 4 из `.env.example`.

---

## Шаг 2. Удалить старую установку

```bash
rm -rf /opt/pass24-telegram-bot
```

Опционально убрать systemd unit:

```bash
rm -f /etc/systemd/system/pass24-telegram-bot.service
systemctl daemon-reload
```

---

## Шаг 3. Установить Docker (если нет)

```bash
docker --version
docker compose version
```

Если не установлен:

```bash
apt-get update
apt-get install -y docker.io docker-compose-v2
systemctl enable --now docker
```

---

## Шаг 4. Клонировать репозиторий

```bash
git clone git@github.com:icebeerg182/pass24-telegram-bot.git /opt/pass24-telegram-bot
cd /opt/pass24-telegram-bot
```

HTTPS (если SSH не настроен на сервере):

```bash
git clone https://github.com/icebeerg182/pass24-telegram-bot.git /opt/pass24-telegram-bot
```

---

## Шаг 5. Настроить `.env`

```bash
cp /root/pass24.env.backup .env
# или: cp .env.example .env && nano .env
chmod 600 .env
mkdir -p data
```

Минимум в `.env`:

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ADMIN_USER_IDS=151373114
PASS24_PHONE=+79...
PASS24_PASSWORD=...
PASS24_ADDRESS_KEYWORD=Ренессанс
```

---

## Шаг 6. Запустить

```bash
cd /opt/pass24-telegram-bot
docker compose up -d --build
```

---

## Шаг 7. Проверка

```bash
docker compose ps
docker compose logs -f --tail=50
```

В Telegram: `/start` → `BMW А121МР77`

---

## Обновление

```bash
cd /opt/pass24-telegram-bot
git pull
docker compose up -d --build
```

---

## Полезные команды

```bash
docker compose restart          # перезапуск
docker compose down             # остановка
docker compose logs -f          # логи
```

---

## Если на сервере нет SSH-ключа для GitHub

На сервере:

```bash
ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519_github
cat ~/.ssh/id_ed25519_github.pub
```

Добавьте ключ в GitHub → Settings → SSH keys, затем:

```bash
git clone git@github.com:icebeerg182/pass24-telegram-bot.git /opt/pass24-telegram-bot
```

Или клонируйте по HTTPS (для private repo понадобится Personal Access Token).
