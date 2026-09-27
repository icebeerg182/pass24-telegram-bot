"""Обработчик запросов из Apple Shortcuts (Siri)."""
import logging
import re

from alice.service import (
    create_pass_from_text,
    format_error,
    format_pass_success,
    normalize_command,
)

log = logging.getLogger("pass24-alice")

# Фразы активации Shortcut, которые не являются маркой/номером
_SIRI_PREFIX_RE = re.compile(
    r"^(?:"
    r"пропуск\s+кембридж|кембридж\s+пропуск|кембридж|"
    r"pass\s+cambridge|cambridge"
    r")\s+",
    re.IGNORECASE,
)


def normalize_siri_query(text: str) -> str:
    text = normalize_command(text.strip())
    text = _SIRI_PREFIX_RE.sub("", text, count=1).strip()
    return text


def handle_siri_pass(query: str) -> str:
    text = normalize_siri_query(query)
    if not text:
        return "Скажите марку и номер. Например: мазда 656 или лисян 7 8 7."

    log.info("Siri query: %s", text)
    try:
        info = create_pass_from_text(text)
        log.info(
            "Siri pass created: %s %s (id=%s)",
            info["brand"],
            info["plate"],
            info.get("pass_id"),
        )
        return format_pass_success(info)
    except Exception as exc:
        log.warning("Siri pass failed: %s", exc)
        return format_error(exc)
