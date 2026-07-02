#!/bin/bash
# Install on Linux server only. Use LF line endings.
set -eu

REMOTE_DIR="/opt/pass24-telegram-bot"
SERVICE="pass24-telegram-bot.service"

cd "$REMOTE_DIR"

# Fix CRLF if files were uploaded from Windows
find "$REMOTE_DIR" -type f \( -name "*.sh" -o -name "*.py" -o -name "*.service" \) -exec sed -i 's/\r$//' {} + 2>/dev/null || true
sed -i 's/\r$//' "$REMOTE_DIR/.env" 2>/dev/null || true

echo "==> Ensure python3-venv"
if ! python3 -m venv /tmp/_pass24_venv_test 2>/dev/null; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq python3-venv python3-pip
fi
rm -rf /tmp/_pass24_venv_test

echo "==> Create venv"
python3 -m venv "$REMOTE_DIR/.venv"
"$REMOTE_DIR/.venv/bin/pip" install -q --upgrade pip
"$REMOTE_DIR/.venv/bin/pip" install -q -r "$REMOTE_DIR/requirements.txt"

echo "==> Smoke test PASS24"
cd "$REMOTE_DIR"
"$REMOTE_DIR/.venv/bin/python" "$REMOTE_DIR/deploy/smoke_test.py"

echo "==> Install systemd unit ($SERVICE only)"
cp "$REMOTE_DIR/deploy/pass24-telegram-bot.service" "/etc/systemd/system/$SERVICE"
systemctl daemon-reload
systemctl enable "$SERVICE"
systemctl restart "$SERVICE"
systemctl --no-pager status "$SERVICE" || true

echo "==> Done"
