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


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name, "").strip().lower()
    if not val:
        return default
    return val in ("1", "true", "yes", "y", "on", "да")


BOT_ASK_VEHICLE_TYPE = _env_bool("BOT_ASK_VEHICLE_TYPE")
BOT_CONFIRM_BEFORE_CREATE = _env_bool("BOT_CONFIRM_BEFORE_CREATE")
BOT_ENABLE_ADDRESS_PICKER = _env_bool("BOT_ENABLE_ADDRESS_PICKER")
ADDRESS_BUTTON_LABEL = "📍 Адрес"

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
    rows = [
        [KeyboardButton("/myid"), KeyboardButton("/users")],
        [
            KeyboardButton("/open 12"),
            KeyboardButton("/open 24"),
            KeyboardButton("/open 48"),
        ],
        [KeyboardButton("/close")],
        [KeyboardButton("/allow"), KeyboardButton("/deny"), KeyboardButton("/help")],
    ]
    if BOT_ENABLE_ADDRESS_PICKER:
        rows.insert(0, [KeyboardButton(ADDRESS_BUTTON_LABEL)])
    return ReplyKeyboardMarkup(
        rows,
        resize_keyboard=True,
        is_persistent=True,
    )


def _user_keyboard() -> ReplyKeyboardMarkup | ReplyKeyboardRemove:
    if BOT_ENABLE_ADDRESS_PICKER:
        return ReplyKeyboardMarkup(
            [[KeyboardButton(ADDRESS_BUTTON_LABEL)]],
            resize_keyboard=True,
            is_persistent=True,
        )
    return ReplyKeyboardRemove()


def _reply_keyboard_for_user(uid: int | None) -> ReplyKeyboardMarkup | ReplyKeyboardRemove:
    if ACCESS.is_admin(uid):
        return _admin_keyboard()
    return _user_keyboard()


def _user_address_id(context: ContextTypes.DEFAULT_TYPE) -> int | None:
    value = context.user_data.get("address_id")
    return int(value) if value is not None else None


def _current_address_name(client: Pass24ApiClient, context: ContextTypes.DEFAULT_TYPE) -> str:
    try:
        return client.get_address_name(address_id=_user_address_id(context))
    except Exception as e:
        return f"(ошибка: {e})"


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


def _vehicle_type_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🚗 Легковой", callback_data="vtype:легков"),
                InlineKeyboardButton("🚛 Грузовой", callback_data="vtype:грузовой"),
            ],
            [InlineKeyboardButton("❌ Отмена", callback_data="pcreate:no")],
        ]
    )


def _pass_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Создать пропуск", callback_data="pcreate:yes"),
                InlineKeyboardButton("❌ Отмена", callback_data="pcreate:no"),
            ]
        ]
    )


def _address_keyboard(addresses: list[dict], selected_id: int | None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for addr in addresses:
        addr_id = addr.get("id")
        name = addr.get("name") or addr.get("title") or str(addr_id)
        prefix = "✓ " if selected_id == addr_id else ""
        rows.append(
            [InlineKeyboardButton(f"{prefix}{name}", callback_data=f"addr:{addr_id}")]
        )
    return InlineKeyboardMarkup(rows)


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


def _reply_target(update: Update) -> Message | None:
    return update.effective_message


async def _reply_pass_error(update: Update, client: Pass24ApiClient, e: Exception) -> None:
    target = _reply_target(update)
    if not target:
        return
    if isinstance(e, AuthError):
        client.invalidate_token()
        await target.reply_text(f"Ошибка авторизации PASS24: {e}")
    elif isinstance(e, AddressError):
        await target.reply_text(f"Ошибка адреса: {e}")
    elif isinstance(e, RequestError):
        client.invalidate_token()
        try:
            types = client.get_vehicle_types()
            type_hint = ", ".join(f"{n} ({i})" for n, i in types.items()) if types else "не найдены"
        except Exception:
            type_hint = "не удалось получить"
        await target.reply_text(
            f"Ошибка PASS24: {e}\n\nТипы ТС для адреса: {type_hint}"
        )
    else:
        log.exception("pass error")
        await target.reply_text(f"Неожиданная ошибка: {e}")


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

    try:
        until = ACCESS.open_public(hours)
    except Exception as e:
        log.exception("open_public failed")
        await update.message.reply_text(f"❌ Не удалось открыть доступ: {e}")
        return

    log.info("Public access opened for %s h until %s by admin %s", hours, until, _user_id(update))
    await update.message.reply_text(
        f"✅ Готово.\n\n"
        f"🌐 Бот открыт для всех на {hours} ч.\n"
        f"До: <b>{until.strftime('%d.%m.%Y %H:%M')}</b> (МСК)\n\n"
        "Можно пересылать ссылку на бота.\n"
        "Досрочно закрыть: /close",
        parse_mode="HTML",
    )


@admin_only
async def cmd_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        closed = ACCESS.close_public()
    except Exception as e:
        log.exception("close_public failed")
        await update.message.reply_text(f"❌ Не удалось закрыть доступ: {e}")
        return
    if closed:
        log.info("Public access closed by admin %s", _user_id(update))
        await update.message.reply_text(
            "✅ Готово.\n\n"
            "🔒 Временный доступ закрыт.\n"
            "Снова только доверенные пользователи."
        )
    else:
        await update.message.reply_text(
            "ℹ️ Временный доступ сейчас не активен.\n"
            + (
                "Бот и так открыт всем (пустые списки доступа в .env)."
                if ACCESS.is_open()
                else "Открыть: /open 12, /open 24 или /open 48."
            )
        )


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
    addr = _current_address_name(client, context)
    uid = _user_id(update)
    markup = _reply_keyboard_for_user(uid)

    hints = ["Отправьте марку и госномер."]
    if BOT_ASK_VEHICLE_TYPE:
        hints.append("Перед заказом бот спросит тип ТС: легковой или грузовой.")
    if BOT_CONFIRM_BEFORE_CREATE:
        hints.append("Перед созданием пропуска будет запрошено подтверждение.")
    if BOT_ENABLE_ADDRESS_PICKER:
        hints.append(f"Кнопка «{ADDRESS_BUTTON_LABEL}» — выбор адреса по умолчанию.")

    await update.message.reply_text(
        (
            "Бот заказа пропусков PASS24.\n\n"
            f"Адрес: {addr}\n\n"
            + "\n".join(hints)
            + "\n\nПримеры:\n"
            "<code>мерс А121МР777</code>\n"
            "<code>А121МР77 BMW</code>\n"
            "<code>BMW А 121 МР 77</code>\n\n"
            "/help — справка\n"
            "/myid — ваш Telegram ID"
        ),
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
    parts = [
        "Форматы сообщения (марка и номер в любом порядке):\n",
        "• мерс А121МР777\n",
        "• А121МР77 BMW\n",
        "• BMW А121МР77 серый\n",
        "• BMW А 121 МР 77\n",
        "• в две строки: BMW + номер\n\n",
        "После создания — кнопки «Изменить» и «Удалить».\n",
        f"Пропуск разовый на {PASS24_PASS_HOURS} ч.\n",
    ]
    if BOT_ENABLE_ADDRESS_PICKER:
        parts.append(f"Кнопка «{ADDRESS_BUTTON_LABEL}» — сменить адрес по умолчанию.\n")
    if BOT_ASK_VEHICLE_TYPE:
        parts.append("Перед заказом бот спросит тип ТС (легковой/грузовой).\n")
    if BOT_CONFIRM_BEFORE_CREATE:
        parts.append("Перед созданием пропуска бот запросит подтверждение.\n")
    else:
        parts.append("Пропуск создаётся сразу после распознавания марки и номера.\n")

    await update.message.reply_text("".join(parts) + admin_help)


async def _send_pass_created(
    update: Update,
    result: dict,
    creating_msg: Message | None = None,
) -> None:
    await _safe_delete_message(creating_msg)
    target = _reply_target(update)
    if not target:
        return
    pass_id = result.get("id")
    if not pass_id:
        await target.reply_text(_format_pass_message(result))
        return

    msg = await target.reply_text(
        _format_pass_message(result),
        reply_markup=_pass_keyboard(pass_id),
    )
    _register_pass_ui(pass_id, msg, update.effective_user.id, msg.text)


def _clear_pending_pass(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data.pop("pending_pass", None)


def _pending_pass_preview(pending: dict, address_name: str) -> str:
    vehicle_type = pending.get("vehicle_type")
    type_line = f"\n🚛 Тип: {vehicle_type}" if vehicle_type else ""
    return (
        f"🚗 {pending['brand']}\n"
        f"🔢 {pending['plate']}"
        f"{type_line}\n"
        f"📍 {address_name}\n"
        f"⏱ {PASS24_PASS_HOURS} ч."
    )


async def _create_pending_pass(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    creating_msg: Message | None = None,
) -> None:
    pending = context.user_data.get("pending_pass")
    if not pending:
        return

    client = get_client()
    address_id = _user_address_id(context)
    vehicle_type = pending.get("vehicle_type")
    try:
        result = client.create_pass(
            plate_number=pending["plate"],
            vehicle_model=pending["brand"],
            expiration_hours=PASS24_PASS_HOURS,
            vehicle_type_keyword=vehicle_type or PASS24_VEHICLE_TYPE_KEYWORD,
            address_id=address_id,
        )
        _clear_pending_pass(context)
        await _send_pass_created(update, result, creating_msg)
    except (AuthError, AddressError, RequestError, Exception) as e:
        await _safe_delete_message(creating_msg)
        await _reply_pass_error(update, client, e)


async def _ask_vehicle_type_step(update: Update, pending: dict) -> None:
    preview = _pending_pass_preview(pending, "—")
    await update.message.reply_text(
        f"{preview}\n\nВыберите тип транспорта:",
        reply_markup=_vehicle_type_keyboard(),
    )


async def _ask_confirm_step(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    pending: dict,
) -> None:
    client = get_client()
    address_name = _current_address_name(client, context)
    preview = _pending_pass_preview(pending, address_name)
    await update.message.reply_text(
        f"Проверьте данные:\n\n{preview}\n\nСоздать пропуск?",
        reply_markup=_pass_confirm_keyboard(),
    )


async def _continue_pass_flow(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    after_vehicle_type: bool = False,
) -> None:
    pending = context.user_data.get("pending_pass")
    if not pending:
        return

    if BOT_ASK_VEHICLE_TYPE and not after_vehicle_type and not pending.get("vehicle_type"):
        await _ask_vehicle_type_step(update, pending)
        return

    if BOT_CONFIRM_BEFORE_CREATE:
        await _ask_confirm_step(update, context, pending)
        return

    creating_msg = await update.message.reply_text("Создаю пропуск…")
    await _create_pending_pass(update, context, creating_msg)


async def _begin_pass_flow(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    parsed,
) -> None:
    context.user_data["pending_pass"] = {
        "brand": parsed.brand_canonical,
        "plate": parsed.plate,
    }
    await _continue_pass_flow(update, context)


async def _show_address_picker(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    client = get_client()
    try:
        addresses = client.list_addresses()
    except Exception as e:
        await update.message.reply_text(f"Не удалось получить адреса: {e}")
        return

    if not addresses:
        await update.message.reply_text("В аккаунте нет доступных адресов.")
        return

    selected_id = _user_address_id(context)
    if len(addresses) == 1:
        only = addresses[0]
        context.user_data["address_id"] = only.get("id")
        await update.message.reply_text(
            f"Адрес: {only.get('name', '—')}",
            reply_markup=_reply_keyboard_for_user(_user_id(update)),
        )
        return

    await update.message.reply_text(
        "Выберите адрес по умолчанию для пропусков:",
        reply_markup=_address_keyboard(addresses, selected_id),
    )


async def _create_and_reply(
    update: Update,
    parsed,
    context: ContextTypes.DEFAULT_TYPE,
    creating_msg: Message | None = None,
) -> None:
    client = get_client()
    try:
        result = client.create_pass(
            plate_number=parsed.plate,
            vehicle_model=parsed.brand_canonical,
            expiration_hours=PASS24_PASS_HOURS,
            address_id=_user_address_id(context),
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

    if BOT_ENABLE_ADDRESS_PICKER and text.strip() == ADDRESS_BUTTON_LABEL:
        await _show_address_picker(update, context)
        return

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

    if BOT_ASK_VEHICLE_TYPE or BOT_CONFIRM_BEFORE_CREATE:
        await _begin_pass_flow(update, context, parsed)
        return

    creating_msg = await update.message.reply_text(
        f"🚗 {parsed.brand_canonical}\n🔢 {parsed.plate}\n\nСоздаю пропуск…"
    )
    await _create_and_reply(update, parsed, context, creating_msg)


async def on_plain_slash_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Кнопки клавиатуры шлют /open 12 как текст без entity bot_command."""
    text = (update.message.text or "").strip()
    if not text.startswith("/"):
        return
    parts = text.split()
    cmd = parts[0].split("@")[0].lower()
    context.args = parts[1:]

    routes = {
        "/start": cmd_start,
        "/help": cmd_help,
        "/myid": cmd_myid,
        "/allow": cmd_allow,
        "/deny": cmd_deny,
        "/open": cmd_open,
        "/close": cmd_close,
        "/users": cmd_users,
    }
    handler = routes.get(cmd)
    if handler:
        await handler(update, context)


@allowed_only
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    data = query.data or ""

    if data.startswith("vtype:"):
        pending = context.user_data.get("pending_pass")
        if not pending:
            await query.edit_message_text("Заказ устарел. Отправьте марку и номер снова.")
            return
        pending["vehicle_type"] = data.split(":", 1)[1]
        if BOT_CONFIRM_BEFORE_CREATE:
            client = get_client()
            address_name = _current_address_name(client, context)
            preview = _pending_pass_preview(pending, address_name)
            await query.edit_message_text(
                f"Проверьте данные:\n\n{preview}\n\nСоздать пропуск?",
                reply_markup=_pass_confirm_keyboard(),
            )
            return
        await query.edit_message_text("Создаю пропуск…", reply_markup=None)
        creating_msg = query.message
        await _create_pending_pass(update, context, creating_msg)
        return

    if data.startswith("pcreate:"):
        action = data.split(":", 1)[1]
        if action == "no":
            _clear_pending_pass(context)
            await query.edit_message_text("❌ Заказ пропуска отменён.")
            return
        pending = context.user_data.get("pending_pass")
        if not pending:
            await query.edit_message_text("Заказ устарел. Отправьте марку и номер снова.")
            return
        await query.edit_message_text("Создаю пропуск…", reply_markup=None)
        await _create_pending_pass(update, context, query.message)
        return

    if data.startswith("addr:"):
        try:
            address_id = int(data.split(":", 1)[1])
        except ValueError:
            return
        client = get_client()
        try:
            name = client.get_address_name(address_id=address_id)
        except Exception as e:
            await query.edit_message_text(f"Не удалось выбрать адрес: {e}")
            return
        context.user_data["address_id"] = address_id
        await query.edit_message_text(f"✅ Адрес по умолчанию: {name}")
        return

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

    async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        log.exception("Unhandled error", exc_info=context.error)
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                f"❌ Ошибка бота: {context.error}"
            )

    app.add_error_handler(on_error)
    app.add_handler(CommandHandler("myid", cmd_myid))
    app.add_handler(CommandHandler("allow", cmd_allow))
    app.add_handler(CommandHandler("deny", cmd_deny))
    app.add_handler(CommandHandler("open", cmd_open))
    app.add_handler(CommandHandler("close", cmd_close))
    app.add_handler(CommandHandler("users", cmd_users))
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    # Кнопки ReplyKeyboard: "/open 12" без bot_command entity
    app.add_handler(
        MessageHandler(filters.Regex(r"^/\w+") & ~filters.COMMAND, on_plain_slash_command)
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(CallbackQueryHandler(on_callback))

    if ACCESS.is_public_active():
        mode = f"public until {ACCESS.public_status()}"
    elif ACCESS.is_open():
        mode = "open"
    else:
        mode = f"restricted ({len(ACCESS.all_allowed())} users)"
    log.info(
        "Starting bot v%s (address: %s, ask_vtype=%s, confirm=%s, addr_picker=%s, access: %s)",
        __version__,
        PASS24_ADDRESS_KEYWORD,
        BOT_ASK_VEHICLE_TYPE,
        BOT_CONFIRM_BEFORE_CREATE,
        BOT_ENABLE_ADDRESS_PICKER,
        mode,
    )
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
