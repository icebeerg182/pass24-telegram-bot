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

from bot.access import AccessControl
from bot.parser import ParseError, parse_message
from pass24_api_client import Pass24ApiClient
from pass24_api_client.api_client import AddressError, AuthError, RequestError

load_dotenv(interpolate=False)

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("pass24-bot")

PASS24_PHONE = os.environ["PASS24_PHONE"]
PASS24_PASSWORD = os.environ["PASS24_PASSWORD"]
PASS24_ADDRESS_KEYWORD = os.getenv("PASS24_ADDRESS_KEYWORD", "Ренессанс")
PASS24_PASS_HOURS = int(os.getenv("PASS24_PASS_HOURS", "24"))
PASS24_VEHICLE_TYPE_KEYWORD = os.getenv("PASS24_VEHICLE_TYPE_KEYWORD", "легков")

ACCESS = AccessControl(
    env_allowed={
        int(x.strip())
        for x in os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").split(",")
        if x.strip()
    },
    env_admins={
        int(x.strip())
        for x in os.getenv("TELEGRAM_ADMIN_USER_IDS", "").split(",")
        if x.strip()
    },
)

_client: Pass24ApiClient | None = None
_pending: dict[int, dict] = {}


def vehicle_type_label(keyword: str) -> str:
    if keyword.startswith("груз"):
        return "Грузовой"
    return "Легковой"


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


def _user_id(update: Update) -> int | None:
    user = update.effective_user
    return user.id if user else None


async def _deny_access(update: Update) -> None:
    uid = _user_id(update)
    name = update.effective_user.full_name if update.effective_user else "—"
    text = (
        f"Доступ к боту закрыт.\n\n"
        f"Ваш Telegram ID: <code>{uid}</code>\n"
        f"Имя: {name}\n\n"
        "Отправьте этот ID администратору — он добавит вас командой "
        f"<code>/allow {uid}</code>."
    )
    if update.message:
        await update.message.reply_text(text, parse_mode="HTML")
    elif update.callback_query:
        await update.callback_query.answer("Доступ запрещён", show_alert=True)


def allowed_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = _user_id(update)
        if not ACCESS.is_allowed(uid):
            await _deny_access(update)
            return
        return await func(update, context)

    return wrapper


def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = _user_id(update)
        if not ACCESS.is_admin(uid):
            if update.message:
                await update.message.reply_text("Команда только для администратора.")
            return
        return await func(update, context)

    return wrapper


def _type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🚗 Легковой", callback_data="type_legkov"),
                InlineKeyboardButton("🚛 Грузовой", callback_data="type_gruz"),
            ],
            [InlineKeyboardButton("❌ Отмена", callback_data="confirm_no")],
        ]
    )


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Создать пропуск", callback_data="confirm_yes"),
                InlineKeyboardButton("❌ Отмена", callback_data="confirm_no"),
            ]
        ]
    )


def _type_prompt_text(data: dict) -> str:
    return (
        f"🚗 {data['brand']}\n"
        f"🔢 {data['plate']}\n"
        f"📍 {data['addr']}\n\n"
        "Выберите тип транспорта:"
    )


def _confirm_text(data: dict) -> str:
    vlabel = vehicle_type_label(data["vehicle_type_keyword"])
    icon = "🚛" if data["vehicle_type_keyword"].startswith("груз") else "🚗"
    return (
        f"{icon} {vlabel}\n"
        f"🚗 {data['brand']}\n"
        f"🔢 {data['plate']}\n"
        f"📍 {data['addr']}\n"
        f"📅 Разовый пропуск, {PASS24_PASS_HOURS} ч.\n\n"
        "Создать пропуск?"
    )


async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = _user_id(update)
    user = update.effective_user
    await update.message.reply_text(
        f"Ваш Telegram ID: <code>{uid}</code>\n"
        f"Имя: {user.full_name if user else '—'}\n\n"
        "Передайте ID администратору, если нужен доступ к боту.",
        parse_mode="HTML",
    )


@admin_only
async def cmd_allow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(
            "Использование: /allow <telegram_id>\n"
            "Пример: /allow 123456789"
        )
        return
    try:
        new_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return

    if ACCESS.allow(new_id):
        await update.message.reply_text(f"✅ Пользователь {new_id} добавлен.")
    else:
        await update.message.reply_text(f"Пользователь {new_id} уже имеет доступ.")


@admin_only
async def cmd_deny(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Использование: /deny <telegram_id>")
        return
    try:
        remove_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return

    if ACCESS.deny(remove_id):
        await update.message.reply_text(f"❌ Пользователь {remove_id} удалён из списка бота.")
    elif remove_id in ACCESS.env_allowed or remove_id in ACCESS.admins:
        await update.message.reply_text(
            "Этот ID задан в .env (TELEGRAM_ALLOWED_USER_IDS / TELEGRAM_ADMIN_USER_IDS). "
            "Уберите его оттуда вручную."
        )
    else:
        await update.message.reply_text(f"Пользователь {remove_id} не найден в списке бота.")


@admin_only
async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    users = ACCESS.list_users()
    lines = ["Список доступа:"]
    lines.append(f"Админы (.env): {', '.join(map(str, users['admins'])) or '—'}")
    lines.append(f"Из .env: {', '.join(map(str, users['env'])) or '—'}")
    lines.append(f"Добавлены через бота: {', '.join(map(str, users['bot'])) or '—'}")
    if ACCESS.is_open():
        lines.append("\n⚠️ Сейчас доступ открыт всем (списки пустые).")
    await update.message.reply_text("\n".join(lines))


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
        "Отправьте марку и госномер, например:\n"
        "<code>мерс А121МР777</code>\n\n"
        "Бот спросит тип ТС (легковой / грузовой) и предложит создать пропуск.\n\n"
        "/help — справка\n"
        "/myid — ваш Telegram ID",
        parse_mode="HTML",
    )


@allowed_only
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_help = ""
    if ACCESS.is_admin(_user_id(update)):
        admin_help = (
            "\n\nКоманды администратора:\n"
            "/allow <id> — выдать доступ\n"
            "/deny <id> — забрать доступ\n"
            "/users — список пользователей"
        )
    await update.message.reply_text(
        "Примеры:\n"
        "• мерс А121МР777\n"
        "• бмв х123ох77\n\n"
        "После сообщения выберите легковой или грузовой, затем подтвердите создание.\n"
        "Номер должен быть полным (буква, 3 цифры, 2 буквы, регион).\n"
        f"Пропуск на «{PASS24_ADDRESS_KEYWORD}», разовый на {PASS24_PASS_HOURS} ч."
        f"{admin_help}"
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
    data = {
        "brand": parsed.brand_canonical,
        "plate": parsed.plate,
        "addr": addr,
        "vehicle_type_keyword": None,
    }
    _pending[uid] = data

    await update.message.reply_text(
        _type_prompt_text(data),
        reply_markup=_type_keyboard(),
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

    data = _pending.get(uid)
    if not data:
        await query.edit_message_text("Заявка устарела. Отправьте номер снова.")
        return

    if query.data == "type_legkov":
        data["vehicle_type_keyword"] = "легков"
        _pending[uid] = data
        await query.edit_message_text(
            _confirm_text(data),
            reply_markup=_confirm_keyboard(),
        )
        return

    if query.data == "type_gruz":
        data["vehicle_type_keyword"] = "груз"
        _pending[uid] = data
        await query.edit_message_text(
            _confirm_text(data),
            reply_markup=_confirm_keyboard(),
        )
        return

    if query.data != "confirm_yes":
        return

    if not data.get("vehicle_type_keyword"):
        await query.edit_message_text(
            _type_prompt_text(data),
            reply_markup=_type_keyboard(),
        )
        return

    _pending.pop(uid, None)
    client = get_client()
    await query.edit_message_text("Создаю пропуск…")

    try:
        result = client.create_pass(
            plate_number=data["plate"],
            vehicle_model=data["brand"],
            expiration_hours=PASS24_PASS_HOURS,
            vehicle_type_keyword=data["vehicle_type_keyword"],
        )
        plate = result.get("guestData", {}).get("plateNumber", data["plate"])
        model = result.get("guestData", {}).get("model", {}).get("name", data["brand"])
        starts = result.get("startsAt", "—")
        expires = result.get("expiresAt", "—")
        number = result.get("number", "")
        vlabel = vehicle_type_label(data["vehicle_type_keyword"])
        msg = (
            f"✅ Пропуск создан"
            + (f" №{number}" if number else "")
            + f"\n{vlabel}\n🚗 {model}\n🔢 {plate}\n"
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
        try:
            types = client.get_vehicle_types()
            type_hint = ", ".join(f"{n} ({i})" for n, i in types.items()) if types else "не найдены"
        except Exception:
            type_hint = "не удалось получить"
        await query.edit_message_text(
            f"Ошибка PASS24: {e}\n\nТипы ТС для адреса: {type_hint}"
        )
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
    app.add_handler(CommandHandler("myid", cmd_myid))
    app.add_handler(CommandHandler("allow", cmd_allow))
    app.add_handler(CommandHandler("deny", cmd_deny))
    app.add_handler(CommandHandler("users", cmd_users))
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(CallbackQueryHandler(on_callback))

    mode = "open" if ACCESS.is_open() else f"restricted ({len(ACCESS.all_allowed())} users)"
    log.info("Starting bot (address: %s, access: %s)", PASS24_ADDRESS_KEYWORD, mode)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
