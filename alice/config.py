import os

from dotenv import load_dotenv

load_dotenv(interpolate=False)


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name, "").strip().lower()
    if not val:
        return default
    return val in ("1", "true", "yes", "y", "on", "да")


PASS24_PHONE = os.environ.get("PASS24_PHONE", "")
PASS24_PASSWORD = os.environ.get("PASS24_PASSWORD", "")
PASS24_ADDRESS_KEYWORD = os.getenv("PASS24_ADDRESS_KEYWORD", "")
PASS24_PASS_HOURS = int(os.getenv("PASS24_PASS_HOURS", "24"))
PASS24_VEHICLE_TYPE_KEYWORD = os.getenv("PASS24_VEHICLE_TYPE_KEYWORD", "легков")

BOT_REQUIRE_FULL_PLATE = _env_bool("BOT_REQUIRE_FULL_PLATE", default=True)

ALICE_HOST = os.getenv("ALICE_HOST", "0.0.0.0")
ALICE_PORT = int(os.getenv("ALICE_PORT", "8080"))
ALICE_WEBHOOK_TOKEN = os.getenv("ALICE_WEBHOOK_TOKEN", "").strip()
# Siri Shortcuts: отдельный токен или тот же, что у Алисы
SIRI_WEBHOOK_TOKEN = os.getenv("SIRI_WEBHOOK_TOKEN", "").strip() or ALICE_WEBHOOK_TOKEN
ALICE_SKILL_INVOCATION = os.getenv("ALICE_SKILL_INVOCATION", "пропуск пасс24").strip()

ALICE_ALLOWED_USER_IDS = {
    x.strip()
    for x in os.getenv("ALICE_ALLOWED_USER_IDS", "").split(",")
    if x.strip()
}
