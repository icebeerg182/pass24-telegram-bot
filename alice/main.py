#!/usr/bin/env python3
"""HTTP webhook для навыка Яндекс Алисы."""
import logging
import sys

from flask import Flask, jsonify, request

from alice.config import ALICE_HOST, ALICE_PORT, ALICE_WEBHOOK_TOKEN
from alice.handler import handle_alice_request

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("pass24-alice")

app = Flask(__name__)


def _check_token(token: str | None) -> bool:
    if not ALICE_WEBHOOK_TOKEN:
        log.error("ALICE_WEBHOOK_TOKEN is not set")
        return False
    return token == ALICE_WEBHOOK_TOKEN


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "pass24-alice"})


@app.post("/alice/webhook/<token>")
def alice_webhook(token: str):
    if not _check_token(token):
        return jsonify({"error": "not found"}), 404

    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "invalid json"}), 400

    try:
        response = handle_alice_request(body)
    except Exception:
        log.exception("Handler crash")
        response = {
            "version": "1.0",
            "response": {
                "text": "Внутренняя ошибка сервера.",
                "tts": "Внутренняя ошибка сервера.",
                "end_session": True,
            },
        }

    return jsonify(response)


def main() -> None:
    if not ALICE_WEBHOOK_TOKEN:
        log.error("Set ALICE_WEBHOOK_TOKEN in .env before starting Alice webhook")
        sys.exit(1)

    log.info(
        "Starting Alice webhook on %s:%s (path token configured)",
        ALICE_HOST,
        ALICE_PORT,
    )
    app.run(host=ALICE_HOST, port=ALICE_PORT, threaded=True)


if __name__ == "__main__":
    main()
