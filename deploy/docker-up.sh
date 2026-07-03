#!/bin/bash
# Обновить и перезапустить Docker-контейнер бота на сервере.
set -eu
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "Создайте .env из .env.example"
  exit 1
fi

mkdir -p data

docker compose build
docker compose up -d
docker compose ps
echo ""
echo "Логи: docker compose logs -f pass24-telegram-bot"
