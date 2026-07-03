#!/usr/bin/env python3
"""Telegram-бот для заказа пропусков PASS24 (житель)."""
import logging
import os
from dataclasses import dataclass
from functools import wraps

from dotenv import load_dotenv
from telegram import (
    BotCommand,
    BotCommandScopeChat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot import __version__
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
PASS24_ADDRESS_KEYWORD = os.getenv("PASS24_ADDRESS_KEYWORD", "")
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


@dataclass
class PassUiRecord:
    chat_id: int
    message_id: int
    user_id: int
    pass_id: int
    text: str


# pass_id -> UI message (для кнопок изменить/удалить)
_pass_ui: dict[int, PassUiRecord] = {}


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


def _admin_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("/myid"), KeyboardButton("/users")],
            [
                KeyboardButton("/open 12"),
                KeyboardButton("/open 24"),
                KeyboardButton("/open 48"),
            ],
            [KeyboardButton("/close")],
            [KeyboardButton("/allow"), KeyboardButton("/deny"), KeyboardButton("/help")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


async def _setup_bot_commands(application: Application) -> None:
    default_cmds = [
        BotCommand("start", "Начало работы"),
        BotCommand("help", "Справка"),
        BotCommand("myid", "Мой Telegram ID"),
    ]
    await application.bot.set_my_commands(default_cmds)

    admin_cmds = default_cmds + [
        BotCommand("users", "Список доступа"),
        BotCommand("allow", "Выдать доступ (нужен ID)"),
        BotCommand("deny", "Забрать доступ (нужен ID)"),
        BotCommand("open", "Открыть для всех на N часов"),
        BotCommand("close", "Закрыть временный доступ"),
    ]
    for admin_id in ACCESS.admins:
        try:
            await application.bot.set_my_commands(
                admin_cmds,
                scope=BotCommandScopeChat(chat_id=admin_id),
            )
        except Exception as e:
            log.warning("Cannot set admin menu for %s: %s", admin_id, e)


def _pass_keyboard(pass_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✏️ Изменить", callback_data=f"pedit:{pass_id}"),
                InlineKeyboardButton("🗑 Удалить", callback_data=f"pdel:{pass_id}"),
            ]
        ]
    )


def _delete_confirm_keyboard(pass_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Да, удалить", callback_data=f"pdely:{pass_id}"),
                InlineKeyboardButton("❌ Отмена", callback_data=f"pdeln:{pass_id}"),
            ]
        ]
    )


def _format_pass_message(result: dict, header: str = "✅ Пропуск создан") -> str:
    guest = result.get("guestData") or {}
    plate = guest.get("plateNumber", "—")
    model = guest.get("model", {})
    model_name = model.get("name") if isinstance(model, dict) else guest.get("model") or "—"
    starts = result.get("startsAt", "—")
    expires = result.get("expiresAt", "—")
    number = result.get("number", "")
    return (
        header
        + (f" №{number}" if number else "")
        + f"\n🚗 {model_name}\n🔢 {plate}\n"
        f"🕐 {starts} — {expires}"
    )


def _register_pass_ui(pass_id: int, message: Message, user_id: int, text: str) -> None:
    _pass_ui[pass_id] = PassUiRecord(
        chat_id=message.chat_id,
        message_id=message.message_id,
        user_id=user_id,
        pass_id=pass_id,
        text=text,
    )


def _get_pass_ui(pass_id: int) -> PassUiRecord | None:
    return _pass_ui.get(pass_id)


async def _safe_delete_message(message: Message | None) -> None:
    if not message:
        return
    try:
        await message.delete()
    except Exception as e:
        log.debug("Could not delete message: %s", e)


async def _reply_pass_error(update: Update, client: Pass24ApiClient, e: Exception) -> None:
    if isinstance(e, AuthError):
        client.invalidate_token()
        await update.message.reply_text(f"Ошибка авторизации PASS24: {e}")
    elif isinstance(e, AddressError):
        await update.message.reply_text(f"Ошибка адреса: {e}")
    elif isinstance(e, RequestError):
        client.invalidate_token()
        try:
            types = client.get_vehicle_types()
            type_hint = ", ".join(f"{n} ({i})" for n, i in types.items()) if types else "не найдены"
        except Exception:
            type_hint = "не удалось получить"
        await update.message.reply_text(
            f"Ошибка PASS24: {e}\n\nТипы ТС для адреса: {type_hint}"
        )
    else:
        log.exception("pass error")
        await update.message.reply_text(f"Неожиданная ошибка: {e}")


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
    uid = _user_id(update)
    markup = _admin_keyboard() if ACCESS.is_admin(uid) else ReplyKeyboardRemove()
    await update.message.reply_text(
        "Бот заказа пропусков PASS24.\n\n"
        f"Адрес: {addr}\n\n"
        "Отправьте марку и госномер — пропуск создаётся сразу.\n"
        "Под сообщением о пропуске можно изменить или удалить его.\n\n"
        "Примеры:\n"
        "<code>мерс А121МР777</code>\n"
        "<code>А121МР77 BMW</code>\n"
        "<code>BMW А 121 МР 77</code>\n\n"
        "/help — справка\n"
        "/myid — ваш Telegram ID",
        parse_mode="HTML",
        reply_markup=markup,
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
        "После создания — кнопки «Изменить» и «Удалить».\n"
        f"Пропуск разовый на {PASS24_PASS_HOURS} ч."
        f"{admin_help}"
    )


async def _send_pass_created(
    update: Update,
    result: dict,
    creating_msg: Message | None = None,
) -> None:
    await _safe_delete_message(creating_msg)
    pass_id = result.get("id")
    if not pass_id:
        await update.message.reply_text(_format_pass_message(result))
        return

    msg = await update.message.reply_text(
        _format_pass_message(result),
        reply_markup=_pass_keyboard(pass_id),
    )
    _register_pass_ui(pass_id, msg, update.effective_user.id, msg.text)


async def _create_and_reply(update: Update, parsed, creating_msg: Message | None = None) -> None:
    client = get_client()
    try:
        result = client.create_pass(
            plate_number=parsed.plate,
            vehicle_model=parsed.brand_canonical,
            expiration_hours=PASS24_PASS_HOURS,
        )
        await _send_pass_created(update, result, creating_msg)
    except (AuthError, AddressError, RequestError, Exception) as e:
        await _safe_delete_message(creating_msg)
        await _reply_pass_error(update, client, e)


async def _update_pass_and_reply(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    pass_id: int,
    parsed,
) -> None:
    client = get_client()
    ui = _get_pass_ui(pass_id)
    progress = await update.message.reply_text("Обновляю пропуск…")

    try:
        result = client.update_pass(
            pass_id=pass_id,
            plate_number=parsed.plate,
            vehicle_model=parsed.brand_canonical,
        )
        new_pass_id = result.get("id", pass_id)
        text = _format_pass_message(result, header="✅ Пропуск обновлён")

        if ui:
            try:
                await context.bot.edit_message_text(
                    chat_id=ui.chat_id,
                    message_id=ui.message_id,
                    text=text,
                    reply_markup=_pass_keyboard(new_pass_id),
                )
                if new_pass_id != pass_id:
                    _pass_ui.pop(pass_id, None)
                _pass_ui[new_pass_id] = PassUiRecord(
                    ui.chat_id,
                    ui.message_id,
                    update.effective_user.id,
                    new_pass_id,
                    text,
                )
            except Exception:
                msg = await update.message.reply_text(
                    text, reply_markup=_pass_keyboard(new_pass_id)
                )
                _register_pass_ui(new_pass_id, msg, update.effective_user.id, text)
        else:
            msg = await update.message.reply_text(
                text, reply_markup=_pass_keyboard(new_pass_id)
            )
            _register_pass_ui(new_pass_id, msg, update.effective_user.id, text)

        await _safe_delete_message(progress)
        context.user_data.pop("editing_pass_id", None)
    except (AuthError, AddressError, RequestError, Exception) as e:
        await _safe_delete_message(progress)
        await _reply_pass_error(update, client, e)


@allowed_only
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text or ""
    client = get_client()

    editing_pass_id = context.user_data.get("editing_pass_id")
    if editing_pass_id:
        try:
            models = client.get_vehicle_models()
            parsed = parse_message(text, models)
        except ParseError as e:
            await update.message.reply_text(str(e))
            return
        await _update_pass_and_reply(update, context, int(editing_pass_id), parsed)
        return

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

    creating_msg = await update.message.reply_text(
        f"🚗 {parsed.brand_canonical}\n🔢 {parsed.plate}\n\nСоздаю пропуск…"
    )
    await _create_and_reply(update, parsed, creating_msg)


@allowed_only
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    data = query.data or ""

    if data.startswith("pedit:"):
        pass_id = int(data.split(":", 1)[1])
        ui = _get_pass_ui(pass_id)
        if not ui or ui.user_id != uid:
            await query.answer("Нет доступа к этому пропуску", show_alert=True)
            return
        context.user_data["editing_pass_id"] = pass_id
        await query.edit_message_text(
            ui.text + "\n\n✏️ Отправьте новую марку и госномер:",
            reply_markup=None,
        )
        return

    if data.startswith("pdel:"):
        pass_id = int(data.split(":", 1)[1])
        ui = _get_pass_ui(pass_id)
        if not ui or ui.user_id != uid:
            await query.answer("Нет доступа к этому пропуску", show_alert=True)
            return
        await query.edit_message_text(
            ui.text + "\n\n🗑 Удалить этот пропуск?",
            reply_markup=_delete_confirm_keyboard(pass_id),
        )
        return

    if data.startswith("pdeln:"):
        pass_id = int(data.split(":", 1)[1])
        ui = _get_pass_ui(pass_id)
        if not ui or ui.user_id != uid:
            return
        await query.edit_message_text(
            ui.text,
            reply_markup=_pass_keyboard(pass_id),
        )
        return

    if data.startswith("pdely:"):
        pass_id = int(data.split(":", 1)[1])
        ui = _get_pass_ui(pass_id)
        if not ui or ui.user_id != uid:
            await query.answer("Нет доступа", show_alert=True)
            return

        client = get_client()
        await query.edit_message_text(ui.text + "\n\nУдаляю…", reply_markup=None)
        try:
            client.delete_pass(pass_id)
            _pass_ui.pop(pass_id, None)
            await query.edit_message_text("🗑 Пропуск удалён", reply_markup=None)
        except (AuthError, RequestError) as e:
            client.invalidate_token()
            await query.edit_message_text(
                f"Не удалось удалить пропуск: {e}",
                reply_markup=_pass_keyboard(pass_id),
            )
        except Exception as e:
            log.exception("delete_pass")
            await query.edit_message_text(
                f"Ошибка при удалении: {e}",
                reply_markup=_pass_keyboard(pass_id),
            )
        return


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = (
        Application.builder()
        .token(token)
        .post_init(_setup_bot_commands)
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
    app.add_handler(CallbackQueryHandler(on_callback))

    if ACCESS.is_public_active():
        mode = f"public until {ACCESS.public_status()}"
    elif ACCESS.is_open():
        mode = "open"
    else:
        mode = f"restricted ({len(ACCESS.all_allowed())} users)"
    log.info("Starting bot v%s (address: %s, access: %s)", __version__, PASS24_ADDRESS_KEYWORD, mode)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
