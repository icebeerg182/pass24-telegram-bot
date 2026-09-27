#!/usr/bin/env python3
"""Сгенерировать файл .shortcut для импорта в приложение «Команды» (Siri)."""
from __future__ import annotations

import argparse
import plistlib
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "shortcuts" / "Pass-Cambridge.shortcut"


def _text_token_string(base: str, attachment: dict) -> dict:
    attach_key = "{" + f"{len(base)}, 1" + "}"
    return {
        "Value": {
            "attachmentsByRange": {
                ("{0, " + str(len(base)) + "}"): {
                    "Type": "String",
                    "Value": base,
                },
                attach_key: attachment,
            },
            "string": base + "\ufffc",
        },
        "WFSerializationType": "WFTextTokenString",
    }


def _action_output_ref(action_uuid: str, output_name: str = "Text") -> dict:
    return {
        "Type": "ActionOutput",
        "OutputName": output_name,
        "OutputUUID": action_uuid,
    }


def build_shortcut(base_url: str, name: str = "Пропуск Кембридж") -> dict:
    if not base_url.endswith("?q="):
        if "?" in base_url:
            raise ValueError("URL должен заканчиваться на ?q=")
        base_url = base_url.rstrip("/") + "?q="

    ask_uuid = str(uuid.uuid4()).upper()
    download_uuid = str(uuid.uuid4()).upper()
    speak_uuid = str(uuid.uuid4()).upper()
    show_uuid = str(uuid.uuid4()).upper()

    return {
        "WFWorkflowActions": [
            {
                "WFWorkflowActionIdentifier": "is.workflow.actions.ask",
                "WFWorkflowActionParameters": {
                    "WFAskActionPrompt": "Марка и номер?",
                    "WFInputType": "Text",
                },
                "UUID": ask_uuid,
            },
            {
                "WFWorkflowActionIdentifier": "is.workflow.actions.downloadurl",
                "WFWorkflowActionParameters": {
                    "WFHTTPMethod": "GET",
                    "WFURL": _text_token_string(
                        base_url,
                        _action_output_ref(ask_uuid, "Text"),
                    ),
                },
                "UUID": download_uuid,
            },
            {
                "WFWorkflowActionIdentifier": "is.workflow.actions.speaktext",
                "WFWorkflowActionParameters": {
                    "WFText": _text_token_string(
                        "",
                        _action_output_ref(download_uuid, "Contents of URL"),
                    ),
                    "WFSpeakTextLanguage": "ru-RU",
                },
                "UUID": speak_uuid,
            },
            {
                "WFWorkflowActionIdentifier": "is.workflow.actions.showresult",
                "WFWorkflowActionParameters": {
                    "Text": _text_token_string(
                        "",
                        _action_output_ref(download_uuid, "Contents of URL"),
                    ),
                },
                "UUID": show_uuid,
            },
        ],
        "WFWorkflowClientRelease": "3.0",
        "WFWorkflowClientVersion": "2605.0.2",
        "WFWorkflowHasOutputFallback": False,
        "WFWorkflowIcon": {
            "WFWorkflowIconGlyphNumber": 59511,
            "WFWorkflowIconStartColor": 4282601983,
        },
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowName": name,
        "WFWorkflowOutputContentItemClasses": ["WFStringContentItem"],
        "WFWorkflowTypes": ["NCWidget", "WatchKit", "ActionExtension"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Siri Shortcut file")
    parser.add_argument(
        "--base-url",
        help="https://domain/siri/pass/TOKEN?q= (или из ALICE_PUBLIC_BASE_URL + TOKEN)",
    )
    parser.add_argument("--name", default="Пропуск Кембридж")
    parser.add_argument("--output", default=str(DEFAULT_OUT))
    parser.add_argument("--template", action="store_true", help="Шаблон с YOUR-DOMAIN/YOUR-TOKEN")
    args = parser.parse_args()

    if args.template:
        base_url = "https://YOUR-DOMAIN/siri/pass/YOUR-TOKEN?q="
    elif args.base_url:
        base_url = args.base_url
    else:
        try:
            from dotenv import load_dotenv
            import os

            load_dotenv(ROOT / ".env", interpolate=False)
            public = os.getenv("ALICE_PUBLIC_BASE_URL", "").rstrip("/")
            token = os.getenv("ALICE_WEBHOOK_TOKEN") or os.getenv("SIRI_WEBHOOK_TOKEN")
            if not public or not token:
                print("Задайте --base-url или ALICE_PUBLIC_BASE_URL + ALICE_WEBHOOK_TOKEN в .env", file=sys.stderr)
                return 1
            base_url = f"{public}/siri/pass/{token}?q="
        except ImportError:
            print("Установите python-dotenv или передайте --base-url", file=sys.stderr)
            return 1

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    data = build_shortcut(base_url, name=args.name)
    out.write_bytes(plistlib.dumps(data, fmt=plistlib.FMT_BINARY))
    print(f"OK: {out}")
    if args.template:
        print("Замените YOUR-DOMAIN и YOUR-TOKEN в команде после импорта (шаг «Получить URL»).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
