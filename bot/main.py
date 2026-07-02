#!/usr/bin/env python3
"""Telegram-бот для заказа пропусков PASS24 (житель)."""
import logging
import os
from functools import wraps

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.parser import ParseError, parse_message
from pass24_api_client import Pass24ApiClient
from pass24_api_client.api_client import AddressError, AuthError, RequestError

load_dotenv()

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("pass24-bot")

PASS24_PHONE = os.environ["PASS24_PHONE"]
PASS24_PASSWORD = os.environ["PASS24_PASSWORD"]
PASS24_ADDRESS_KEYWORD = os.getenv("PASS24_ADDRESS_KEYWORD", "Ренессанс")
PASS24_PASS_HOURS = int(os.getenv("PASS24_PASS_HOURS", "24"))
ALLOWED_IDS = {
    int(x.strip())
    for x in os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").split(",")
    if x.strip()
}

_client: Pass24ApiClient | None = None
_pending: dict[int, dict] = {}


def get_client() -> Pass24ApiClient:
    global _client
    if _client is None:
        _client = Pass24ApiClient(
            phone=PASS24_PHONE,
            password=PASS24_PASSWORD,
            address_keyword=PASS24_ADDRESS_KEYWORD,
        )
    return _client


def allowed_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id if update.effective_user else None
        if ALLOWED_IDS and uid not in ALLOWED_IDS:
            if update.message:
                await update.message.reply_text("Доступ запрещён.")
            return
        return await func(update, context)

    return wrapper


@allowed_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    client = get_client()
    try:
        addr = client.get_address_name()
    except Exception as e:
        addr = f"(ошибка: {e})"
    await update.message.reply_text(
        "Бот заказа пропусков PASS24.\n\n"
        f"Адрес: {addr}\n\n"
        "Отправьте сообщение в формате:\n"
        "<code>мерс А121МР777</code>\n\n"
        "Марка (сокращение или полное название) + полный госномер.\n"
        "/help — справка",
        parse_mode="HTML",
    )


@allowed_only
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Примеры:\n"
        "• мерс А121МР777\n"
        "• бмв х123ох77\n"
        "• toyota к777кк197\n\n"
        "Номер должен быть полным (буква, 3 цифры, 2 буквы, регион).\n"
        "Пропуск создаётся на адрес «Ренессанс», разовый на 24 часа."
    )


@allowed_only
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text or ""
    client = get_client()
    try:
        models = client.get_vehicle_models()
        parsed = parse_message(text, models)
    except ParseError as e:
        await update.message.reply_text(str(e))
        return
    except Exception as e:
        log.exception("parse error")
        await update.message.reply_text(f"Ошибка: {e}")
        return

    try:
        addr = client.get_address_name()
    except Exception:
        addr = PASS24_ADDRESS_KEYWORD

    uid = update.effective_user.id
    _pending[uid] = {
        "brand": parsed.brand_canonical,
        "plate": parsed.plate,
    }

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Создать", callback_data="confirm_yes"),
                InlineKeyboardButton("❌ Отмена", callback_data="confirm_no"),
            ]
        ]
    )
    await update.message.reply_text(
        f"🚗 {parsed.brand_canonical}\n"
        f"🔢 {parsed.plate}\n"
        f"📍 {addr}\n"
        f"📅 Разовый пропуск, {PASS24_PASS_HOURS} ч.\n\n"
        "Подтвердить?",
        reply_markup=keyboard,
    )


@allowed_only
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id

    if query.data == "confirm_no":
        _pending.pop(uid, None)
        await query.edit_message_text("Отменено.")
        return

    if query.data != "confirm_yes":
        return

    data = _pending.pop(uid, None)
    if not data:
        await query.edit_message_text("Заявка устарела. Отправьте номер снова.")
        return

    client = get_client()
    await query.edit_message_text("Создаю пропуск…")

    try:
        result = client.create_pass(
            plate_number=data["plate"],
            vehicle_model=data["brand"],
            expiration_hours=PASS24_PASS_HOURS,
        )
        plate = result.get("guestData", {}).get("plateNumber", data["plate"])
        model = result.get("guestData", {}).get("model", {}).get("name", data["brand"])
        starts = result.get("startsAt", "—")
        expires = result.get("expiresAt", "—")
        number = result.get("number", "")
        msg = (
            f"✅ Пропуск создан"
            + (f" №{number}" if number else "")
            + f"\n🚗 {model}\n🔢 {plate}\n"
            f"🕐 {starts} — {expires}"
        )
        await query.edit_message_text(msg)
    except AuthError as e:
        client.invalidate_token()
        await query.edit_message_text(f"Ошибка авторизации PASS24: {e}")
    except AddressError as e:
        await query.edit_message_text(f"Ошибка адреса: {e}")
    except RequestError as e:
        client.invalidate_token()
        await query.edit_message_text(f"Ошибка PASS24: {e}")
    except Exception as e:
        log.exception("create_pass")
        await query.edit_message_text(f"Неожиданная ошибка: {e}")


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = (
        Application.builder()
        .token(token)
        .build()
    )
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(CallbackQueryHandler(on_callback))

    log.info("Starting bot (address filter: %s)", PASS24_ADDRESS_KEYWORD)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
