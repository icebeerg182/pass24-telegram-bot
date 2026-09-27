import logging
import re

from pass24_api_client import Pass24ApiClient
from pass24_api_client.api_client import AddressError, AuthError, RequestError

from alice.config import (
    BOT_REQUIRE_FULL_PLATE,
    PASS24_ADDRESS_KEYWORD,
    PASS24_PASS_HOURS,
    PASS24_PASSWORD,
    PASS24_PHONE,
    PASS24_VEHICLE_TYPE_KEYWORD,
)
from alice.voice_numbers import normalize_spoken_numbers
from bot.parser import ParseError, parse_message

log = logging.getLogger("pass24-alice")

_client: Pass24ApiClient | None = None

# Префиксы, которые Алиса может оставить в команде после активации навыка
_COMMAND_PREFIX_RE = re.compile(
    r"^(?:"
    r"закажи\s+пропуск|оформи\s+пропуск|создай\s+пропуск|"
    r"заказать\s+пропуск|оформить\s+пропуск|создать\s+пропуск|"
    r"пропуск\s+на|пропуск|закажи|оформи|создай"
    r")\s+",
    re.IGNORECASE,
)


def get_client() -> Pass24ApiClient:
    global _client
    if _client is None:
        _client = Pass24ApiClient(
            phone=PASS24_PHONE,
            password=PASS24_PASSWORD,
            address_keyword=PASS24_ADDRESS_KEYWORD,
            vehicle_type_keyword=PASS24_VEHICLE_TYPE_KEYWORD,
        )
    return _client


def extract_command_text(body: dict) -> str:
    request = body.get("request") or {}
    for key in ("command", "original_utterance"):
        value = (request.get(key) or "").strip()
        if value:
            return value
    return ""


def normalize_command(text: str) -> str:
    text = normalize_spoken_numbers(text.strip())
    text = re.sub(r"^алиса\s+", "", text, flags=re.IGNORECASE)
    text = _COMMAND_PREFIX_RE.sub("", text, count=1).strip()
    return text


def create_pass_from_text(text: str) -> dict:
    client = get_client()
    models = client.get_vehicle_models()
    parsed = parse_message(
        text,
        models,
        require_full_plate=BOT_REQUIRE_FULL_PLATE,
    )
    result = client.create_pass(
        plate_number=parsed.plate,
        vehicle_model=parsed.brand_canonical,
        expiration_hours=PASS24_PASS_HOURS,
    )
    return {
        "brand": parsed.brand_canonical,
        "plate": parsed.plate,
        "address": client.get_address_name(),
        "pass_id": result.get("id"),
        "number": result.get("number"),
    }


def format_pass_success(info: dict) -> str:
    number = info.get("number")
    extra = f", номер пропуска {number}" if number else ""
    return (
        f"Готово. Пропуск на {info['brand']} {info['plate']}"
        f"{extra}. Адрес: {info['address']}."
    )


def format_error(exc: Exception) -> str:
    if isinstance(exc, ParseError):
        first_line = str(exc).split("\n", 1)[0]
        return f"Не поняла. {first_line}. Скажите, например: мазда 656."
    if isinstance(exc, AuthError):
        return "Ошибка входа в PASS24. Проверьте настройки на сервере."
    if isinstance(exc, AddressError):
        return "Не найден адрес в PASS24. Проверьте PASS24_ADDRESS_KEYWORD."
    if isinstance(exc, RequestError):
        return f"PASS24 отклонил запрос: {exc}"
    log.exception("Unexpected error")
    return "Что-то пошло не так. Попробуйте ещё раз."
