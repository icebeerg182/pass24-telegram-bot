#!/usr/bin/env python3
"""Remote deploy via SSH. Reads secrets from .env in project root."""
import os
import sys
from pathlib import Path

try:
    import paramiko
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "paramiko"])
    import paramiko

from dotenv import load_dotenv

LOCAL = Path(__file__).resolve().parent.parent
load_dotenv(LOCAL / ".env")

HOST = os.getenv("WAICORE_SSH_HOST", "178.17.52.193")
USER = os.getenv("WAICORE_SSH_USER", "root")
PASSWORD = os.getenv("WAICORE_SSH_PASSWORD", "")
REMOTE = "/opt/pass24-telegram-bot"

FILES_TO_UPLOAD = [
    "pass24_api_client",
    "bot",
    "requirements.txt",
    "deploy",
    "README.md",
    "docs",
    ".env.example",
    ".gitattributes",
]

INSTALL_SCRIPT = r"""#!/bin/bash
set -eu
REMOTE_DIR="/opt/pass24-telegram-bot"
SERVICE="pass24-telegram-bot.service"
cd "$REMOTE_DIR"
find "$REMOTE_DIR" -type f \( -name "*.sh" -o -name "*.py" -o -name "*.service" \) -exec sed -i 's/\r$//' {} + 2>/dev/null || true
sed -i 's/\r$//' "$REMOTE_DIR/.env" 2>/dev/null || true
if ! python3 -m venv /tmp/_pass24_venv_test 2>/dev/null; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq python3-venv python3-pip
fi
rm -rf /tmp/_pass24_venv_test
rm -rf "$REMOTE_DIR/.venv"
python3 -m venv "$REMOTE_DIR/.venv"
"$REMOTE_DIR/.venv/bin/pip" install -q --upgrade pip
"$REMOTE_DIR/.venv/bin/pip" install -q -r "$REMOTE_DIR/requirements.txt"
cd "$REMOTE_DIR"
"$REMOTE_DIR/.venv/bin/python" "$REMOTE_DIR/deploy/smoke_test.py"
cp "$REMOTE_DIR/deploy/pass24-telegram-bot.service" "/etc/systemd/system/$SERVICE"
sed -i 's/\r$//' "/etc/systemd/system/$SERVICE"
systemctl daemon-reload
systemctl enable "$SERVICE"
systemctl restart "$SERVICE"
systemctl --no-pager status "$SERVICE" || true
echo DEPLOY_OK
"""


def upload_dir(sftp, local: Path, remote: str) -> None:
    if local.is_file():
        sftp.put(str(local), remote)
        return
    try:
        sftp.mkdir(remote)
    except OSError:
        pass
    for item in local.iterdir():
        rpath = f"{remote}/{item.name}"
        if item.is_dir():
            upload_dir(sftp, item, rpath)
        else:
            sftp.put(str(item), rpath)


def main() -> int:
    if not PASSWORD:
        print("Set WAICORE_SSH_PASSWORD in .env", file=sys.stderr)
        return 1
    if not (LOCAL / ".env").exists():
        print("Create .env from .env.example", file=sys.stderr)
        return 1

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"==> Connecting to {HOST}")
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    client.exec_command(f"mkdir -p {REMOTE}")[1].channel.recv_exit_status()

    print("==> upload files")
    sftp = client.open_sftp()
    for name in FILES_TO_UPLOAD:
        local_path = LOCAL / name
        if not local_path.exists():
            continue
        remote_path = f"{REMOTE}/{name}"
        if local_path.is_dir():
            upload_dir(sftp, local_path, remote_path)
        else:
            sftp.put(str(local_path), remote_path)
    sftp.put(str(LOCAL / ".env"), f"{REMOTE}/.env")
    sftp.close()

    print("==> run install")
    stdin, stdout, stderr = client.exec_command(INSTALL_SCRIPT, get_pty=True)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out)
    if err:
        print(err, file=sys.stderr)
    client.close()

    if code != 0 or "DEPLOY_OK" not in out:
        return code or 1
    print("==> SUCCESS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
