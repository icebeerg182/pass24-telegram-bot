#!/usr/bin/env python3
"""Показать справочники PASS24 — типы ТС, марки, адреса."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(
    os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
    interpolate=False,
)

from pass24_api_client import Pass24ApiClient

phone = os.environ["PASS24_PHONE"]
password = os.environ["PASS24_PASSWORD"]
keyword = os.getenv("PASS24_ADDRESS_KEYWORD", "Ренессанс")

client = Pass24ApiClient(phone, password, keyword)
client.login()
print("login ok\n")

addr = client._get_address_record()
print("=== address record (trimmed) ===")
print(json.dumps(addr, ensure_ascii=False, indent=2)[:5000])

print("\n=== vehicle types ===")
types = client.get_vehicle_types()
for name, vid in types.items():
    print(f"  {vid}: {name}")
if not types:
    print("  (пусто)")

print("\n=== resolve vehicle type ===")
try:
    print("  id:", client.resolve_vehicle_type_id())
except Exception as e:
    print(f"  error: {e}")

print("\n=== vehicle models (first 10) ===")
models = client.get_vehicle_models()
for name in list(models.keys())[:10]:
    print(f"  {models[name]}: {name}")
