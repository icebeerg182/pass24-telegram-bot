#!/usr/bin/env python3
"""Проверка учётных данных из .env (Telegram + PASS24)."""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*_args, **_kwargs) -> bool:
        return False


def normalize_phone(raw: str) -> str:
    s = raw.strip().replace(" ", "").replace("-", "")
    if s.startswith("8") and len(s) == 11:
        s = "+7" + s[1:]
    elif s.startswith("7") and not s.startswith("+"):
        s = "+" + s
    return s


def validate_telegram(token: str) -> tuple[bool, str]:
    import requests

    token = token.strip()
    if not re.match(r"^\d+:[A-Za-z0-9_-]+$", token):
        return False, "неверный формат токена (ожидается 123456789:ABC...)"

    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=20)
        data = r.json()
    except requests.RequestException as e:
        return False, f"нет связи с Telegram API: {e}"

    if not data.get("ok"):
        return False, data.get("description", str(data))

    user = data["result"]
    name = user.get("username")
    label = f"@{name}" if name else user.get("first_name", "бот")
    return True, label


def validate_pass24(phone: str, password: str, keyword: str) -> tuple[bool, str]:
    from pass24_api_client import Pass24ApiClient
    from pass24_api_client.api_client import AddressError, AuthError

    phone = normalize_phone(phone)
    password = password.strip()
    keyword = keyword.strip()

    if not phone.startswith("+") or len(phone) < 11:
        return False, "телефон должен быть в формате +79XXXXXXXXX"

    try:
        client = Pass24ApiClient(phone, password, keyword)
        client.login()
        addr = client.get_address_name()
        models = len(client.get_vehicle_models())
        vtype = client.resolve_vehicle_type_id()
        return True, f"адрес «{addr}», марок: {models}, тип ТС: {vtype}"
    except AuthError as e:
        return False, f"PASS24: {e}"
    except AddressError as e:
        return False, f"адрес не найден: {e}"
    except Exception as e:
        return False, str(e)


def list_pass24_addresses(phone: str, password: str) -> list[str]:
    import requests

    phone = normalize_phone(phone)
    r = requests.post(
        "https://mobile-api.pass24online.ru/v1/auth/login",
        json={"phone": phone, "password": password.strip()},
        timeout=30,
    )
    data = r.json()
    if data.get("error"):
        raise RuntimeError(data["error"].get("message", str(data["error"])))

    token = data["body"]
    r2 = requests.get(
        "https://mobile-api.pass24online.ru/v1/profile/addresses",
        json={"token": token},
        timeout=30,
    )
    payload = r2.json()
    if payload.get("error"):
        raise RuntimeError(payload["error"].get("message", str(payload["error"])))

    names: list[str] = []
    for item in payload.get("body", []) or []:
        name = item.get("name") or item.get("title") or str(item)
        names.append(name)
    return names


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate bot .env credentials")
    parser.add_argument("--env", default=str(ROOT / ".env"), help="path to .env file")
    parser.add_argument("--telegram-only", action="store_true")
    parser.add_argument("--pass24-only", action="store_true")
    parser.add_argument("--list-addresses", action="store_true")
    args = parser.parse_args()

    env_path = Path(args.env)
    if env_path.exists():
        load_dotenv(env_path, interpolate=False)
    elif not args.list_addresses:
        print(f"Файл не найден: {env_path}", file=sys.stderr)
        return 1

    phone = os.getenv("PASS24_PHONE", "")
    password = os.getenv("PASS24_PASSWORD", "")
    keyword = os.getenv("PASS24_ADDRESS_KEYWORD", "")

    if args.list_addresses:
        try:
            for name in list_pass24_addresses(phone, password):
                print(name)
        except Exception as e:
            print(f"Ошибка: {e}", file=sys.stderr)
            return 1
        return 0

    failed = False

    if not args.pass24_only:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        ok, msg = validate_telegram(token)
        if ok:
            print(f"Telegram OK — {msg}")
        else:
            print(f"Telegram FAIL — {msg}", file=sys.stderr)
            failed = True

    if not args.telegram_only:
        ok, msg = validate_pass24(phone, password, keyword)
        if ok:
            print(f"PASS24 OK — {msg}")
        else:
            print(f"PASS24 FAIL — {msg}", file=sys.stderr)
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
