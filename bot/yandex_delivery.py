"""Публичный трекинг Яндекс Доставки (share-ссылка)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import requests

from bot.brands import resolve_brand
from bot.parser import ParseError, ParsedPass, normalize_plate

log = logging.getLogger("pass24-bot.yandex")

SHARED_ROUTE_INFO_URL = (
    "https://ya-authproxy.taxi.yandex.ru/4.0/cargo-c2c/v1/shared-route/info"
)

# dostavka.yandex.ru/route/#uuid  или  /route/uuid  (+ возможные зеркала)
YANDEX_ROUTE_LINK_RE = re.compile(
    r"(?i)https?://(?:[\w.-]+\.)?"
    r"(?:dostavka\.yandex\.(?:ru|com)|taxi\.yandex\.(?:ru|com))"
    r"/route/?(?:#|/)?"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
)


class YandexDeliveryError(Exception):
    pass


@dataclass
class YandexCourierVehicle:
    sharing_key: str
    brand_token: str
    brand_canonical: str
    plate: str
    vehicle_model_raw: str
    summary: str = ""


def extract_sharing_key(text: str) -> str | None:
    text = (text or "").strip()
    if not text:
        return None
    m = YANDEX_ROUTE_LINK_RE.search(text)
    if m:
        return m.group(1).lower()
    # Голый UUID в сообщении рядом со словом яндекс/доставка/route
    m2 = re.search(
        r"(?i)(?:yandex|яндекс|dostavka|доставк|route).{0,80}"
        r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
        text,
    )
    if m2:
        return m2.group(1).lower()
    # Сообщение — только ссылка-хеш без домена уже после Telegram preview strip
    m3 = re.fullmatch(
        r"(?i)#?([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
        text,
    )
    if m3 and ("dostavka" in text.lower() or "yandex" in text.lower() or "route" in text.lower()):
        return m3.group(1).lower()
    return None


def _resolve_brand_from_vehicle_model(
    vehicle_model: str,
    pass24_models: dict[str, int],
) -> tuple[str, str]:
    raw = (vehicle_model or "").strip()
    if not raw:
        raise YandexDeliveryError("В трекинге нет модели автомобиля")

    # Hyundai Creta → сначала полное, потом первое слово
    candidates = [raw]
    parts = raw.split()
    if parts:
        candidates.append(parts[0])
    if len(parts) >= 2:
        candidates.append(f"{parts[0]} {parts[1]}")

    for token in candidates:
        found = resolve_brand(token, pass24_models)
        if found:
            return token, found

    raise YandexDeliveryError(
        f"Марка «{raw}» не найдена в справочнике PASS24. "
        "Создайте пропуск вручную: марка и госномер."
    )


def fetch_shared_route(sharing_key: str, timeout: float = 20.0) -> dict:
    try:
        r = requests.post(
            SHARED_ROUTE_INFO_URL,
            json={"key": sharing_key},
            headers={
                "Accept": "application/json",
                "Accept-Language": "ru",
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )
    except requests.RequestException as e:
        raise YandexDeliveryError(f"Не удалось открыть трекинг Яндекса: {e}") from e

    if r.status_code == 404:
        raise YandexDeliveryError(
            "Заказ по ссылке не найден или уже недоступен."
        )
    if r.status_code >= 400:
        detail = ""
        try:
            detail = r.json().get("message") or r.text[:200]
        except Exception:
            detail = r.text[:200]
        raise YandexDeliveryError(
            f"Яндекс Доставка ответила {r.status_code}: {detail}"
        )

    try:
        return r.json()
    except ValueError as e:
        raise YandexDeliveryError("Некорректный ответ Яндекс Доставки") from e


def vehicle_from_shared_route(
    data: dict,
    sharing_key: str,
    pass24_models: dict[str, int],
) -> YandexCourierVehicle:
    performer = data.get("performer") or {}
    model_raw = (performer.get("vehicle_model") or "").strip()
    number_raw = (performer.get("vehicle_number") or "").strip()

    if not number_raw and not model_raw:
        # Иногда номер только в description: "серый Hyundai Creta • ..."
        desc = data.get("description") or ""
        raise YandexDeliveryError(
            "Курьер ещё не назначен или машина не указана.\n"
            f"Статус: {data.get('summary') or '—'}\n"
            f"{desc}".strip()
        )

    if not number_raw:
        raise YandexDeliveryError(
            "В трекинге нет госномера. Подождите назначения курьера или введите номер вручную."
        )

    plate = normalize_plate(number_raw)
    if len(plate) < 7:
        raise YandexDeliveryError(f"Странный госномер из трекинга: {number_raw}")

    brand_token, brand_canonical = _resolve_brand_from_vehicle_model(
        model_raw or "Не задана",
        pass24_models,
    )

    return YandexCourierVehicle(
        sharing_key=sharing_key,
        brand_token=brand_token,
        brand_canonical=brand_canonical,
        plate=plate,
        vehicle_model_raw=model_raw,
        summary=(data.get("summary") or "").strip(),
    )


def parse_yandex_delivery_link(
    text: str,
    pass24_models: dict[str, int],
) -> ParsedPass | None:
    """Если в тексте share-ссылка Яндекс Доставки — вернуть ParsedPass, иначе None."""
    key = extract_sharing_key(text)
    if not key:
        return None

    log.info("Yandex delivery link detected: %s", key)
    data = fetch_shared_route(key)
    vehicle = vehicle_from_shared_route(data, key, pass24_models)
    return ParsedPass(
        brand_token=vehicle.brand_token,
        brand_canonical=vehicle.brand_canonical,
        plate=vehicle.plate,
    )


def try_parse_yandex_or_raise(
    text: str,
    pass24_models: dict[str, int],
) -> ParsedPass | None:
    """None если это не ссылка; ParseError/YandexDeliveryError при ошибке парсинга ссылки."""
    key = extract_sharing_key(text)
    if not key:
        return None
    try:
        return parse_yandex_delivery_link(text, pass24_models)
    except YandexDeliveryError as e:
        raise ParseError(str(e)) from e
