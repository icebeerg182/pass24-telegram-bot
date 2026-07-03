#!/bin/bash
# Вставьте в открытую SSH-сессию на вашем сервере (один раз)
set -eu
REMOTE_DIR="/opt/pass24-telegram-bot"
SERVICE="pass24-telegram-bot.service"
cd "$REMOTE_DIR"
find "$REMOTE_DIR" -type f \( -name "*.sh" -o -name "*.py" -o -name "*.service" \) -exec sed -i 's/\r$//' {} + 2>/dev/null || true
sed -i 's/\r$//' "$REMOTE_DIR/.env" 2>/dev/null || true
if ! python3 -m venv /tmp/_pass24_venv_test 2>/dev/null; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq && apt-get install -y -qq python3-venv python3-pip
fi
rm -rf /tmp/_pass24_venv_test "$REMOTE_DIR/.venv"
python3 -m venv "$REMOTE_DIR/.venv"
"$REMOTE_DIR/.venv/bin/pip" install -q --upgrade pip
"$REMOTE_DIR/.venv/bin/pip" install -q -r "$REMOTE_DIR/requirements.txt"
"$REMOTE_DIR/.venv/bin/python" "$REMOTE_DIR/deploy/smoke_test.py"
cp "$REMOTE_DIR/deploy/pass24-telegram-bot.service" "/etc/systemd/system/$SERVICE"
sed -i 's/\r$//' "/etc/systemd/system/$SERVICE"
systemctl daemon-reload
systemctl enable "$SERVICE"
systemctl restart "$SERVICE"
systemctl --no-pager status "$SERVICE"
echo "=== BOT READY ==="
