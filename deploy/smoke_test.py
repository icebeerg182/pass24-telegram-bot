#!/usr/bin/env python3
"""Quick PASS24 connectivity check after deploy."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from pass24_api_client import Pass24ApiClient

phone = os.environ["PASS24_PHONE"]
password = os.environ["PASS24_PASSWORD"]
keyword = os.getenv("PASS24_ADDRESS_KEYWORD", "Ренессанс")

client = Pass24ApiClient(phone, password, keyword)
client.login()
print("login ok")
print("address:", client.get_address_name())
print("models:", len(client.get_vehicle_models()))

types = client.get_vehicle_types()
print("vehicle types:", len(types))
for name, vid in types.items():
    print(f"  {vid}: {name}")
try:
    print("resolved vehicle type:", client.resolve_vehicle_type_id())
except Exception as e:
    print("resolve vehicle type error:", e)
