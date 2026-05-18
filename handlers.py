import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import storage
from parser import parse_predictions, format_prediction_line, format_time_local

logger = logging.getLogger(__name__)

# Состояния ожидания ввода: {chat_id: mode}
# mode: "predictions" | "timezone" | None
PENDING_INPUT: dict[int, str] = {}


# ── Команды ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    storage.save_settings(storage.load_settings(chat_id))  # init defaults

    text = (
        "⚽ *Бот-помощник для прогнозов*\n\n"
        "📋 *Команды:*\n"
        "/add — добавить прогнозы вручную\n"
        "/list — список активных прогнозов\n"
        "/delete <id> — удалить один прогноз\n"
        "/clear — очистить все\n"
        "/settings — настройки\n\n"
        "🔔 Уведомления приходят за *30* и *5* минут до матча.\n"
        "🗑 Матч автоматически удаляется через *5 минут* после старта."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    PENDING_INPUT[chat_id] = "predictions"
    await update.message.reply_text(
        "📥 Вставь прогнозы — каждый прогноз отделяй пустой строкой.\n\n"
        "Пример:\n"
        "`Soccer. Brazil. 2-00`\n"
        "`Santa Cruz — Independencia`\n"
        "`ф1-4,5`\n\n"
        "`Soccer. Australia. 11-00`\n"
        "`Hurstville — Mariners ТБ2.5`",
        parse_mode="Markdown",
    )


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


async def cmd_delete(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not ctx.args:
        await update.message.reply_text("Укажи ID: `/delete abc12345`", parse_mode="Markdown")
        return

    ok = storage.delete_prediction(chat_id, ctx.args[0])
    if ok:
        await update.message.reply_text(f"🗑 Прогноз `{ctx.args[0]}` удалён.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Прогноз `{ctx.args[0]}` не найден.", parse_mode="Markdown")


async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    kb = [[
        InlineKeyboardButton("✅ Да, очистить", callback_data="clear_yes"),
        InlineKeyboardButton("❌ Отмена", callback_data="clear_no"),
    ]]
    await update.message.reply_text("⚠️ Очистить все прогнозы?", reply_markup=InlineKeyboardMarkup(kb))


async def cmd_settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    s = storage.load_settings(chat_id)
    kb = [
        [InlineKeyboardButton(f"🌐 Часовой пояс: UTC+{s.timezone_offset}", callback_data="set_tz")],
    ]
    await update.message.reply_text(
        "⚙️ *Настройки*\n\nУведомления: за 30 и 5 минут (фиксировано).\n"
        "Автоудаление: через 5 минут после старта матча.",
        reply_markup=InlineKeyboardMarkup(kb),
        parse_mode="Markdown",
    )


# ── Обработка текстовых сообщений ────────────────────────────────────────────

async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    mode = PENDING_INPUT.pop(chat_id, None)

    if mode is None:
        await update.message.reply_text("Используй /add чтобы добавить прогнозы, или /list.")
        return

    text = update.message.text.strip()
    s = storage.load_settings(chat_id)

    if mode == "timezone":
        try:
            offset = int(text.replace("+", ""))
            if not -12 <= offset <= 14:
                raise ValueError
            s.timezone_offset = offset
            storage.save_settings(s)
            await update.message.reply_text(f"✅ Часовой пояс: UTC+{offset}")
        except ValueError:
            await update.message.reply_text("❌ Введи число от -12 до 14")
        return

    if mode == "predictions":
        preds = parse_predictions(text, s.timezone_offset, source="manual")
        if not preds:
            await update.message.reply_text(
                "❌ Не нашёл время матча в тексте.\n\n"
                "Проверь что есть время в формате `2-00` или `14:30`",
                parse_mode="Markdown",
            )
            return

        added = storage.add_predictions(chat_id, preds)
        skipped = len(preds) - added

        lines = [f"✅ *Добавлено: {added}*" + (f"  (пропущено дублей: {skipped})" if skipped else "")]
        for i, p in enumerate(preds, 1):
            t = format_time_local(p, s.timezone_offset)
            lines.append(f"\n{i}. ⏰ {t}\n   {p.text}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ── Кнопки ───────────────────────────────────────────────────────────────────

async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    chat_id = q.message.chat_id
    await q.answer()

    if q.data == "clear_yes":
        storage.clear_predictions(chat_id)
        await q.edit_message_text("🗑 Все прогнозы удалены.")

    elif q.data == "clear_no":
        await q.edit_message_text("Отмена.")

    elif q.data == "set_tz":
        PENDING_INPUT[chat_id] = "timezone"
        await q.edit_message_text(
            "🌐 Введи смещение часового пояса (UTC+N):\n"
            "`3` — Москва, `5` — Екатеринбург, `0` — UTC",
            parse_mode="Markdown",
        )
