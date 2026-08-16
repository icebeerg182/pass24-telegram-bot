"""LLM fallback для определения марки (Groq OpenAI-compatible API)."""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from pathlib import Path

import requests

log = logging.getLogger("pass24-bot.llm")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"
CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "brands_learned.json"

_lock = threading.Lock()
_cache: dict[str, str] | None = None


def llm_enabled() -> bool:
    flag = os.getenv("BOT_LLM_BRAND_RESOLVER", "").strip().lower()
    if flag not in ("1", "true", "yes", "y", "on", "да"):
        return False
    return bool(os.getenv("BOT_LLM_API_KEY", "").strip())


def _cache_key(text: str) -> str:
    s = text.strip().lower().replace("ё", "е")
    s = re.sub(r"\s+", " ", s)
    return s


def _load_cache() -> dict[str, str]:
    global _cache
    with _lock:
        if _cache is not None:
            return _cache
        if CACHE_PATH.exists():
            try:
                raw = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    _cache = {str(k): str(v) for k, v in raw.items()}
                else:
                    _cache = {}
            except Exception:
                log.exception("Failed to load LLM brand cache")
                _cache = {}
        else:
            _cache = {}
        return _cache


def _save_cache() -> None:
    with _lock:
        if _cache is None:
            return
        try:
            CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            CACHE_PATH.write_text(
                json.dumps(_cache, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except Exception:
            log.exception("Failed to save LLM brand cache")


def _match_catalog_name(name: str, pass24_models: dict[str, int]) -> str | None:
    if not name:
        return None
    if name in pass24_models:
        return name
    lower = {k.lower(): k for k in pass24_models}
    return lower.get(name.strip().lower())


def _call_groq(user_text: str, catalog_names: list[str], timeout: float = 8.0) -> str | None:
    api_key = os.getenv("BOT_LLM_API_KEY", "").strip()
    model = os.getenv("BOT_LLM_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    catalog_blob = "\n".join(catalog_names)

    system = (
        "You map messy vehicle brand mentions to an official catalog name.\n"
        "Return ONLY valid JSON with exactly these keys: brand, confidence.\n"
        'Format: {"brand":"<exact catalog name>","confidence":"high"} '
        'OR {"brand":null,"confidence":"low"}\n'
        "Rules:\n"
        "- brand MUST be copied EXACTLY from the catalog list, or null\n"
        "- Prefer manufacturer brand, not model (Hyundai Creta -> Hyundai)\n"
        "- Mercedes-Maybach -> Mercedes-Benz; Maybach only if text is specifically Maybach\n"
        "- Russian slang: бэха/бмв/бумер -> BMW, мерс/мерин -> Mercedes-Benz, "
        "соллерс/солерс -> Sollers, фольц/фолькс -> Volkswagen\n"
        "- Ignore colors, class names (S-Class/S-Класс), chassis codes (Z223), plates\n"
        "- confidence=high only when clearly sure; otherwise brand=null and confidence=low\n"
        "- NEVER invent a guess for unrelated gibberish\n"
        "Examples:\n"
        'Input «бэха а123мр77» -> {"brand":"BMW","confidence":"high"}\n'
        'Input «мерс с-класс z223» -> {"brand":"Mercedes-Benz","confidence":"high"}\n'
        'Input «xyz quantumcar» -> {"brand":null,"confidence":"low"}'
    )
    user = (
        f"User text:\n{user_text}\n\n"
        f"Catalog brands (one per line):\n{catalog_blob}\n\n"
        'Respond with JSON: {"brand": ..., "confidence": ...}'
    )

    resp = requests.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "temperature": 0,
            "max_tokens": 80,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=timeout,
    )
    if resp.status_code >= 400:
        log.warning("Groq HTTP %s: %s", resp.status_code, resp.text[:300])
        return None

    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError):
        log.warning("Unexpected Groq response: %s", resp.text[:300])
        return None

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # иногда модель оборачивает в ```json
        m = re.search(r"\{.*\}", content, re.S)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None

    if not isinstance(data, dict):
        return None

    brand = data.get("brand")
    confidence = str(data.get("confidence") or "").strip().lower()
    if confidence and confidence not in ("high", "medium", "ok", "sure"):
        # low / unknown → отказ, даже если brand заполнен
        if confidence in ("low", "no", "none", "unsure", "unknown"):
            return None

    if brand is None or brand == "" or str(brand).lower() in ("null", "none"):
        # на случай кривого ключа — ищем значение из каталога только при high
        if confidence in ("high", "medium", "ok", "sure", ""):
            for value in data.values():
                if isinstance(value, str) and value.strip() and value.strip().lower() not in (
                    "null",
                    "none",
                    "high",
                    "low",
                    "medium",
                ):
                    brand = value.strip()
                    break
            else:
                return None
        else:
            return None
    return str(brand).strip()


def resolve_brand_via_llm(
    user_text: str,
    pass24_models: dict[str, int],
) -> str | None:
    """Вернуть каноническое имя марки из каталога PASS24 или None."""
    if not llm_enabled() or not user_text.strip() or not pass24_models:
        return None

    key = _cache_key(user_text)
    cache = _load_cache()
    cached = cache.get(key)
    if cached:
        matched = _match_catalog_name(cached, pass24_models)
        if matched:
            log.info("LLM brand cache hit: %r -> %s", user_text[:80], matched)
            return matched

    catalog_names = sorted(pass24_models.keys(), key=str.lower)
    try:
        raw = _call_groq(user_text, catalog_names)
    except requests.RequestException as e:
        log.warning("Groq request failed: %s", e)
        return None

    matched = _match_catalog_name(raw or "", pass24_models)
    if not matched:
        log.info("LLM brand not in catalog for %r (raw=%r)", user_text[:80], raw)
        return None

    with _lock:
        cache[key] = matched
    _save_cache()
    log.info("LLM brand resolved: %r -> %s", user_text[:80], matched)
    return matched
