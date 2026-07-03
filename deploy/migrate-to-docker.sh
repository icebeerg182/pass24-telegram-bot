#!/bin/bash
# Миграция с systemd на Docker (запускать на сервере от root).
set -eu

INSTALL_DIR="/opt/pass24-telegram-bot"
SERVICE="pass24-telegram-bot.service"
BACKUP_DIR="/opt/pass24-telegram-bot-backup-$(date +%Y%m%d-%H%M%S)"

echo "==> 1. Резервная копия .env и data/"
mkdir -p "$BACKUP_DIR"
[ -f "$INSTALL_DIR/.env" ] && cp -a "$INSTALL_DIR/.env" "$BACKUP_DIR/"
[ -d "$INSTALL_DIR/data" ] && cp -a "$INSTALL_DIR/data" "$BACKUP_DIR/"

echo "==> 2. Остановка systemd-сервиса (если был)"
if systemctl is-active --quiet "$SERVICE" 2>/dev/null; then
  systemctl stop "$SERVICE"
  echo "    stopped $SERVICE"
fi
if systemctl is-enabled --quiet "$SERVICE" 2>/dev/null; then
  systemctl disable "$SERVICE"
  echo "    disabled $SERVICE"
fi

echo "==> 3. Проверка Docker"
if ! command -v docker >/dev/null; then
  echo "Docker не установлен. Установите:"
  echo "  apt-get update && apt-get install -y docker.io docker-compose-v2"
  echo "  systemctl enable --now docker"
  exit 1
fi

echo "==> 4. Обновление кода"
cd "$INSTALL_DIR"
if [ -d .git ]; then
  git pull
else
  echo "    Нет git — убедитесь, что файлы Dockerfile и docker-compose.yml на месте"
fi

echo "==> 5. .env"
if [ ! -f .env ] && [ -f "$BACKUP_DIR/.env" ]; then
  cp "$BACKUP_DIR/.env" .env
fi
if [ ! -f .env ]; then
  echo "    ОШИБКА: нет .env в $INSTALL_DIR"
  exit 1
fi

echo "==> 6. data/"
mkdir -p data
if [ -d "$BACKUP_DIR/data" ] && [ ! -f data/allowed_users.json ]; then
  cp -a "$BACKUP_DIR/data/"* data/ 2>/dev/null || true
fi

echo "==> 7. Запуск Docker"
docker compose build
docker compose up -d

echo "==> 8. Статус"
docker compose ps
echo ""
echo "Готово. Бэкап: $BACKUP_DIR"
echo "Логи:   docker compose -f $INSTALL_DIR/docker-compose.yml logs -f"
echo ""
echo "Опционально удалить старый venv:"
echo "  rm -rf $INSTALL_DIR/.venv"
echo "Опционально удалить unit-файл:"
echo "  rm -f /etc/systemd/system/$SERVICE && systemctl daemon-reload"
