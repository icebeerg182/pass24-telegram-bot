#!/usr/bin/env python3
"""HTTP webhook для навыка Яндекс Алисы."""
import logging
import sys

from flask import Flask, Response, jsonify, request

from alice.config import ALICE_HOST, ALICE_PORT, ALICE_WEBHOOK_TOKEN, SIRI_WEBHOOK_TOKEN
from alice.handler import handle_alice_request
from alice.siri import handle_siri_pass

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("pass24-alice")

app = Flask(__name__)


def _check_alice_token(token: str | None) -> bool:
    if not ALICE_WEBHOOK_TOKEN:
        log.error("ALICE_WEBHOOK_TOKEN is not set")
        return False
    return token == ALICE_WEBHOOK_TOKEN


def _check_siri_token(token: str | None) -> bool:
    if not SIRI_WEBHOOK_TOKEN:
        log.error("SIRI_WEBHOOK_TOKEN is not set")
        return False
    return token == SIRI_WEBHOOK_TOKEN


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "pass24-alice", "siri": bool(SIRI_WEBHOOK_TOKEN)})


@app.get("/siri/pass/<token>")
def siri_pass(token: str):
    if not _check_siri_token(token):
        return Response("not found", status=404, mimetype="text/plain; charset=utf-8")

    query = (request.args.get("q") or request.args.get("text") or "").strip()
    text = handle_siri_pass(query)
    return Response(text, mimetype="text/plain; charset=utf-8")


@app.post("/alice/webhook/<token>")
def alice_webhook(token: str):
    if not _check_alice_token(token):
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
    if not ALICE_WEBHOOK_TOKEN and not SIRI_WEBHOOK_TOKEN:
        log.error("Set ALICE_WEBHOOK_TOKEN or SIRI_WEBHOOK_TOKEN in .env")
        sys.exit(1)

    log.info(
        "Starting pass24 voice API on %s:%s (alice=%s, siri=%s)",
        ALICE_HOST,
        ALICE_PORT,
        bool(ALICE_WEBHOOK_TOKEN),
        bool(SIRI_WEBHOOK_TOKEN),
    )
    app.run(host=ALICE_HOST, port=ALICE_PORT, threaded=True)


if __name__ == "__main__":
    main()
