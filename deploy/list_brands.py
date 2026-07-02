#!/usr/bin/env python3
"""Поиск марок в справочнике PASS24 — для настройки aliases."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(
    os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
    interpolate=False,
)

from bot.brands import resolve_brand, suggest_brands
from pass24_api_client import Pass24ApiClient

query = " ".join(sys.argv[1:]).strip() or "жигули"
phone = os.environ["PASS24_PHONE"]
password = os.environ["PASS24_PASSWORD"]

client = Pass24ApiClient(phone, password)
models = client.get_vehicle_models()
print(f"Справочник PASS24: {len(models)} марок\n")
print(f"Запрос: {query!r}")

resolved = resolve_brand(query, models)
print(f"resolve_brand: {resolved!r}")

suggestions = suggest_brands(query, models)
if suggestions:
    print("suggest:", ", ".join(suggestions))

print("\nПохожие в справочнике:")
q = query.lower()
matches = [n for n in models if q in n.lower()]
for name in sorted(matches)[:20]:
    print(f"  {models[name]}: {name}")
if not matches:
    print("  (нет прямых вхождений — попробуйте: python deploy/list_brands.py lada")
