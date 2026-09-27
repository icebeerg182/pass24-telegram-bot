import logging

from alice.config import ALICE_ALLOWED_USER_IDS, ALICE_SKILL_INVOCATION, BOT_REQUIRE_FULL_PLATE
from alice.service import (
    create_pass_from_text,
    extract_command_text,
    format_error,
    format_pass_success,
    normalize_command,
)

log = logging.getLogger("pass24-alice")


def _alice_response(text: str, *, end_session: bool) -> dict:
    return {
        "version": "1.0",
        "response": {
            "text": text,
            "tts": text,
            "end_session": end_session,
        },
    }


def _welcome_text() -> str:
    if BOT_REQUIRE_FULL_PLATE:
        example = "мерс А121МР77"
    else:
        example = "мазда 656"
    invocation = ALICE_SKILL_INVOCATION or "пропуск пасс24"
    return (
        f"Назовите марку и номер. Например: {example}. "
        f"Или скажите: закажи {invocation} {example}."
    )


def _user_id(body: dict) -> str | None:
    session = body.get("session") or {}
    user = session.get("user") or {}
    return user.get("user_id") or session.get("user_id")


def _is_allowed(user_id: str | None) -> bool:
    if not ALICE_ALLOWED_USER_IDS:
        return True
    return bool(user_id and user_id in ALICE_ALLOWED_USER_IDS)


def handle_alice_request(body: dict) -> dict:
    request = body.get("request") or {}
    req_type = request.get("type", "SimpleUtterance")

    if req_type == "Ping":
        return _alice_response("Ок", end_session=True)

    if not _is_allowed(_user_id(body)):
        log.warning("Access denied for user_id=%s", _user_id(body))
        return _alice_response("У вас нет доступа к этому навыку.", end_session=True)

    command = normalize_command(extract_command_text(body))
    session = body.get("session") or {}
    is_new = bool(session.get("new"))

    if not command:
        if is_new:
            return _alice_response(_welcome_text(), end_session=False)
        return _alice_response(
            "Не услышала марку и номер. Повторите, например: мазда 656.",
            end_session=False,
        )

    log.info("Alice command: %s", command)

    try:
        info = create_pass_from_text(command)
        text = format_pass_success(info)
        log.info("Pass created: %s %s (id=%s)", info["brand"], info["plate"], info.get("pass_id"))
        return _alice_response(text, end_session=True)
    except Exception as exc:
        log.warning("Pass failed: %s", exc)
        return _alice_response(format_error(exc), end_session=False)
