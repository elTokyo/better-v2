import logging
from functools import wraps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import storage
import auth
import config
from parser import parse_predictions, format_time_local

logger = logging.getLogger(__name__)

# Состояния ожидания ввода: {chat_id: mode}
# mode: "predictions" | "timezone" | "password" | "admin_ban" | "admin_remove"
PENDING_INPUT: dict[int, str] = {}


# ── Декоратор для защиты команд ──────────────────────────────────────────────

def require_auth(func):
    """Команда доступна только авторизованным пользователям."""
    @wraps(func)
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if not auth.is_authorized(chat_id):
            await update.message.reply_text(
                "🔒 Доступ закрыт. Введи /start и пароль для авторизации."
            )
            return
        return await func(update, ctx)
    return wrapper


def require_admin(func):
    """Команда доступна только админу."""
    @wraps(func)
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if not auth.is_admin(chat_id):
            await update.message.reply_text("⛔ Только для админа.")
            return
        return await func(update, ctx)
    return wrapper


# ── /start: запрос пароля для новых пользователей ────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    if auth.is_authorized(chat_id):
        await _send_help(update)
        return

    # Не настроен пароль — авторизуем всех (режим разработки)
    if not config.ACCESS_PASSWORD:
        auth.authorize(chat_id, user.username or "", user.first_name or "")
        await _send_help(update)
        return

    PENDING_INPUT[chat_id] = "password"
    await update.message.reply_text(
        "🔒 *Доступ к боту по паролю*\n\n"
        "Введи пароль одним сообщением:",
        parse_mode="Markdown",
    )


async def _send_help(update: Update):
    text = (
        "⚽ *Бот-помощник для прогнозов*\n\n"
        "📋 *Команды:*\n"
        "/add — добавить прогнозы\n"
        "/list — список активных\n"
        "/delete <id> — удалить один\n"
        "/clear — очистить все\n"
        "/settings — настройки\n\n"
        "🔔 Уведомления за *30* и *5* минут до матча.\n"
        "🗑 Автоудаление через *5 минут* после старта."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ── Команды (все защищены require_auth) ──────────────────────────────────────

@require_auth
async def cmd_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    PENDING_INPUT[chat_id] = "predictions"
    await update.message.reply_text(
        "📥 Вставь прогнозы — каждый отделяй пустой строкой.\n\n"
        "Пример:\n"
        "`Soccer. Brazil. 2-00`\n"
        "`Santa Cruz — Independencia ф1-4,5`",
        parse_mode="Markdown",
    )


@require_auth
async def cmd_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    preds = storage.load_predictions(chat_id)
    s = storage.load_settings(chat_id)

    if not preds:
        await update.message.reply_text("📋 Список пуст. Добавь через /add")
        return

    lines = [f"📋 *Активных прогнозов: {len(preds)}*\n"]
    for i, p in enumerate(preds, 1):
        t = format_time_local(p, s.timezone_offset)
        status = " 🔔" if p.notified_30 else ""
        status = " ✅" if p.notified_5 else status
        src = " 🤖" if p.source == "discord" else ""
        lines.append(f"{i}. ⏰ {t}{status}{src}\n   {p.text}\n   🆔 `{p.id}`")

    lines.append("\nДля удаления: `/delete <id>`")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@require_auth
async def cmd_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not ctx.args:
        await update.message.reply_text("Укажи ID: `/delete abc12345`", parse_mode="Markdown")
        return

    ok = storage.delete_prediction(chat_id, ctx.args[0])
    if ok:
        await update.message.reply_text(f"🗑 Удалён `{ctx.args[0]}`.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Не найден `{ctx.args[0]}`.", parse_mode="Markdown")


@require_auth
async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [[
        InlineKeyboardButton("✅ Да, очистить", callback_data="clear_yes"),
        InlineKeyboardButton("❌ Отмена", callback_data="clear_no"),
    ]]
    await update.message.reply_text("⚠️ Очистить все прогнозы?", reply_markup=InlineKeyboardMarkup(kb))


@require_auth
async def cmd_settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    s = storage.load_settings(chat_id)
    kb = [
        [InlineKeyboardButton(f"🌐 Часовой пояс: UTC+{s.timezone_offset}", callback_data="set_tz")],
    ]
    await update.message.reply_text(
        "⚙️ *Настройки*\n\nУведомления: за 30 и 5 минут.\nАвтоудаление: через 5 минут после старта.",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )


# ── Админ-команды ────────────────────────────────────────────────────────────

@require_admin
async def cmd_users(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    users = auth.list_users()
    if not users:
        await update.message.reply_text("📭 Авторизованных пользователей пока нет.")
        return

    lines = [f"👥 *Авторизованных пользователей: {len(users)}*\n"]
    for u in users:
        flag = "🚫" if u.banned else "✅"
        username = f"@{u.username}" if u.username else "—"
        date = u.authorized_at[:10] if u.authorized_at else "?"
        lines.append(
            f"{flag} *{u.first_name or 'Без имени'}*\n"
            f"   {username}\n"
            f"   🆔 `{u.chat_id}`\n"
            f"   📅 {date}"
        )

    lines.append("\n*Команды админа:*")
    lines.append("`/ban <chat_id>` — забанить")
    lines.append("`/unban <chat_id>` — разбанить")
    lines.append("`/remove <chat_id>` — удалить из вайтлиста")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@require_admin
async def cmd_ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Использование: `/ban 123456789`", parse_mode="Markdown")
        return
    try:
        target = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ chat_id должен быть числом.")
        return

    if target == config.ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нельзя забанить админа.")
        return

    ok = auth.set_banned(target, True)
    msg = f"🚫 Пользователь `{target}` забанен." if ok else f"❌ `{target}` не найден."
    await update.message.reply_text(msg, parse_mode="Markdown")


@require_admin
async def cmd_unban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Использование: `/unban 123456789`", parse_mode="Markdown")
        return
    try:
        target = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ chat_id должен быть числом.")
        return

    ok = auth.set_banned(target, False)
    msg = f"✅ Пользователь `{target}` разбанен." if ok else f"❌ `{target}` не найден."
    await update.message.reply_text(msg, parse_mode="Markdown")


@require_admin
async def cmd_remove(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Использование: `/remove 123456789`", parse_mode="Markdown")
        return
    try:
        target = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ chat_id должен быть числом.")
        return

    if target == config.ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Нельзя удалить админа.")
        return

    ok = auth.remove_user(target)
    msg = f"🗑 Пользователь `{target}` удалён из вайтлиста." if ok else f"❌ `{target}` не найден."
    await update.message.reply_text(msg, parse_mode="Markdown")


# ── Обработка текста ─────────────────────────────────────────────────────────

async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    mode = PENDING_INPUT.pop(chat_id, None)

    # ── Ввод пароля ──────────────────────────────────────────────────────────
    if mode == "password":
        entered = update.message.text.strip()
        if entered == config.ACCESS_PASSWORD:
            auth.authorize(chat_id, user.username or "", user.first_name or "")
            await update.message.reply_text("✅ Доступ открыт!")
            await _send_help(update)
            # Уведомить админа о новом пользователе
            if config.ADMIN_CHAT_ID and chat_id != config.ADMIN_CHAT_ID:
                try:
                    uname = f"@{user.username}" if user.username else "—"
                    await ctx.bot.send_message(
                        chat_id=config.ADMIN_CHAT_ID,
                        text=(
                            f"🆕 *Новый пользователь авторизовался*\n\n"
                            f"Имя: {user.first_name or '—'}\n"
                            f"Username: {uname}\n"
                            f"🆔 `{chat_id}`"
                        ),
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    logger.error(f"Не удалось уведомить админа: {e}")
        else:
            await update.message.reply_text("❌ Неверный пароль. Попробуй ещё раз через /start")
            # Уведомить админа о попытке
            if config.ADMIN_CHAT_ID:
                try:
                    uname = f"@{user.username}" if user.username else "—"
                    await ctx.bot.send_message(
                        chat_id=config.ADMIN_CHAT_ID,
                        text=(
                            f"⚠️ *Неверный пароль*\n\n"
                            f"От: {user.first_name or '—'} ({uname})\n"
                            f"🆔 `{chat_id}`"
                        ),
                        parse_mode="Markdown",
                    )
                except Exception:
                    pass
        return

    # ── Все остальные режимы требуют авторизации ─────────────────────────────
    if not auth.is_authorized(chat_id):
        await update.message.reply_text("🔒 Доступ закрыт. Введи /start и пароль.")
        return

    s = storage.load_settings(chat_id)

    if mode == "timezone":
        try:
            offset = int(update.message.text.strip().replace("+", ""))
            if not -12 <= offset <= 14:
                raise ValueError
            s.timezone_offset = offset
            storage.save_settings(s)
            await update.message.reply_text(f"✅ Часовой пояс: UTC+{offset}")
        except ValueError:
            await update.message.reply_text("❌ Введи число от -12 до 14")
        return

    if mode == "predictions":
        preds = parse_predictions(update.message.text, s.timezone_offset, source="manual")
        if not preds:
            await update.message.reply_text(
                "❌ Не нашёл время матча в тексте.\n"
                "Проверь формат: `2-00` или `14:30`",
                parse_mode="Markdown",
            )
            return

        added = storage.add_predictions(chat_id, preds)
        skipped = len(preds) - added

        lines = [f"✅ *Добавлено: {added}*" + (f"  (дублей: {skipped})" if skipped else "")]
        for i, p in enumerate(preds, 1):
            t = format_time_local(p, s.timezone_offset)
            lines.append(f"\n{i}. ⏰ {t}\n   {p.text}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    # Никакой режим не активен
    await update.message.reply_text("Используй /add чтобы добавить прогнозы, или /list.")


# ── Кнопки ───────────────────────────────────────────────────────────────────

async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    chat_id = q.message.chat_id
    await q.answer()

    if not auth.is_authorized(chat_id):
        await q.edit_message_text("🔒 Доступ закрыт.")
        return

    if q.data == "clear_yes":
        storage.clear_predictions(chat_id)
        await q.edit_message_text("🗑 Все прогнозы удалены.")

    elif q.data == "clear_no":
        await q.edit_message_text("Отмена.")

    elif q.data == "set_tz":
        PENDING_INPUT[chat_id] = "timezone"
        await q.edit_message_text(
            "🌐 Введи смещение UTC+N:\n`3` — Москва, `5` — Екатеринбург, `0` — UTC",
            parse_mode="Markdown",
        )
