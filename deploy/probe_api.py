#!/usr/bin/env python3
"""Probe PASS24 API for vehicle types (debug)."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", interpolate=False)

import requests

BASE = "https://mobile-api.pass24online.ru/v1/"
phone = os.environ["PASS24_PHONE"]
password = os.environ["PASS24_PASSWORD"]
keyword = os.getenv("PASS24_ADDRESS_KEYWORD", "")


def post(path, body, token=None):
    if token:
        body = {**body, "token": token}
    r = requests.post(BASE + path, json=body, timeout=30)
    return r.status_code, r.json()


def get(path, token):
    r = requests.get(BASE + path, json={"token": token}, timeout=30)
    return r.status_code, r.json()


_, login = post("auth/login", {"phone": phone, "password": password})
token = login["body"]
print("login ok")

paths = [
    "vehicle-types",
    "vehicleTypes",
    "transport-types",
    "profile/objects",
    "profile/addresses",
    "passes/options",
    "passes/form",
    "passes/settings",
]

for path in paths:
    print(f"\n=== GET {path} ===")
    try:
        code, data = get(path, token)
        print("status", code)
        print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])
    except Exception as e:
        print("err", e)

# address-scoped probe
_, addr_data = get("profile/addresses", token)
addresses = addr_data.get("body") or []
addr = next((a for a in addresses if keyword.lower() in (a.get("name") or "").lower()), addresses[0] if addresses else None)
if addr:
    print(f"\n=== matched address id={addr['id']} name={addr.get('name')} ===")
    print(json.dumps(addr, ensure_ascii=False, indent=2)[:4000])

    for path in (f"addresses/{addr['id']}/vehicle-types", f"addresses/{addr['id']}/options"):
        print(f"\n=== GET {path} ===")
        try:
            code, data = get(path, token)
            print("status", code)
            print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])
        except Exception as e:
            print("err", e)
