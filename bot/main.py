#!/usr/bin/env python3
"""Telegram-бот для заказа пропусков PASS24 (житель)."""
import logging
import os
from functools import wraps

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.access import AccessControl, PUBLIC_HOURS
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
async def cmd_open(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        hours_list = "/".join(str(h) for h in PUBLIC_HOURS)
        await update.message.reply_text(
            f"Использование: /open <часы>\n"
            f"Доступные варианты: {hours_list}\n\n"
            "На это время бот открыт для всех — можно делиться ссылкой."
        )
        return
    try:
        hours = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Укажите число часов: 12, 24 или 48.")
        return

    if hours not in PUBLIC_HOURS:
        await update.message.reply_text(f"Допустимо только: {', '.join(map(str, PUBLIC_HOURS))} часов.")
        return

    until = ACCESS.open_public(hours)
    await update.message.reply_text(
        f"🌐 Бот открыт для всех на {hours} ч.\n"
        f"До: {until.strftime('%d.%m.%Y %H:%M')} (МСК)\n\n"
        "Можно пересылать ссылку на бота.\n"
        "Досрочно закрыть: /close"
    )


@admin_only
async def cmd_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if ACCESS.close_public():
        await update.message.reply_text(
            "🔒 Временный доступ закрыт.\n"
            "Снова только доверенные пользователи."
        )
    else:
        await update.message.reply_text("Временный доступ сейчас не активен.")


@admin_only
async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    users = ACCESS.list_users()
    lines = ["Список доступа:"]
    lines.append(f"Админы (.env): {', '.join(map(str, users['admins'])) or '—'}")
    lines.append(f"Из .env: {', '.join(map(str, users['env'])) or '—'}")
    lines.append(f"Добавлены через бота: {', '.join(map(str, users['bot'])) or '—'}")

    public_until = ACCESS.public_status()
    if public_until:
        lines.append(f"\n🌐 Открыт для всех до: {public_until} (МСК)")
    elif ACCESS.is_open():
        lines.append("\n⚠️ Списки пустые — доступ открыт всем.")
    else:
        lines.append("\n🔒 Только доверенные пользователи.")

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
        "Отправьте марку и госномер — пропуск создаётся сразу.\n\n"
        "Примеры:\n"
        "<code>мерс А121МР777</code>\n"
        "<code>А121МР77 BMW</code>\n"
        "<code>BMW А 121 МР 77</code>\n"
        "<code>BMW А121МР77 серый</code>\n\n"
        "/help — справка\n"
        "/myid — ваш Telegram ID",
        parse_mode="HTML",
    )


@allowed_only
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_help = ""
    if ACCESS.is_admin(_user_id(update)):
        hours_list = "/".join(str(h) for h in PUBLIC_HOURS)
        admin_help = (
            "\n\nКоманды администратора:\n"
            "/allow <id> — выдать постоянный доступ\n"
            "/deny <id> — забрать доступ\n"
            "/users — список пользователей\n"
            f"/open <{hours_list}> — открыть бот для всех на N часов\n"
            "/close — закрыть временный доступ"
        )
    await update.message.reply_text(
        "Форматы сообщения (марка и номер в любом порядке):\n"
        "• мерс А121МР777\n"
        "• А121МР77 BMW\n"
        "• BMW А121МР77 серый\n"
        "• BMW А 121 МР 77\n"
        "• в две строки: BMW + номер\n\n"
        "Цвет и модель (5er и т.п.) игнорируются.\n"
        f"Пропуск на «{PASS24_ADDRESS_KEYWORD}», разовый на {PASS24_PASS_HOURS} ч."
        f"{admin_help}"
    )


async def _create_pass_reply(update: Update, parsed) -> None:
    client = get_client()
    try:
        result = client.create_pass(
            plate_number=parsed.plate,
            vehicle_model=parsed.brand_canonical,
            expiration_hours=PASS24_PASS_HOURS,
        )
        plate = result.get("guestData", {}).get("plateNumber", parsed.plate)
        model = result.get("guestData", {}).get("model", {}).get("name", parsed.brand_canonical)
        starts = result.get("startsAt", "—")
        expires = result.get("expiresAt", "—")
        number = result.get("number", "")
        msg = (
            f"✅ Пропуск создан"
            + (f" №{number}" if number else "")
            + f"\n🚗 {model}\n🔢 {plate}\n"
            f"🕐 {starts} — {expires}"
        )
        await update.message.reply_text(msg)
    except AuthError as e:
        client.invalidate_token()
        await update.message.reply_text(f"Ошибка авторизации PASS24: {e}")
    except AddressError as e:
        await update.message.reply_text(f"Ошибка адреса: {e}")
    except RequestError as e:
        client.invalidate_token()
        try:
            types = client.get_vehicle_types()
            type_hint = ", ".join(f"{n} ({i})" for n, i in types.items()) if types else "не найдены"
        except Exception:
            type_hint = "не удалось получить"
        await update.message.reply_text(
            f"Ошибка PASS24: {e}\n\nТипы ТС для адреса: {type_hint}"
        )
    except Exception as e:
        log.exception("create_pass")
        await update.message.reply_text(f"Неожиданная ошибка: {e}")


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

    await update.message.reply_text(
        f"🚗 {parsed.brand_canonical}\n🔢 {parsed.plate}\n\nСоздаю пропуск…"
    )
    await _create_pass_reply(update, parsed)


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
    app.add_handler(CommandHandler("open", cmd_open))
    app.add_handler(CommandHandler("close", cmd_close))
    app.add_handler(CommandHandler("users", cmd_users))
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    if ACCESS.is_public_active():
        mode = f"public until {ACCESS.public_status()}"
    elif ACCESS.is_open():
        mode = "open"
    else:
        mode = f"restricted ({len(ACCESS.all_allowed())} users)"
    log.info("Starting bot (address: %s, access: %s)", PASS24_ADDRESS_KEYWORD, mode)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
