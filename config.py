import os

# ── Telegram ─────────────────────────────────────────────────────────────────
BOT_TOKEN  = os.getenv("BOT_TOKEN", "")

# ── Discord (опционально — если не задано, авто-парсинг отключён) ────────────
DISCORD_TOKEN      = os.getenv("DISCORD_TOKEN", "")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))
# Куда пушить прогнозы из Discord (личка или группа в TG)
DISCORD_TARGET_TG_CHAT_ID = int(os.getenv("DISCORD_TARGET_TG_CHAT_ID", "0"))

# ── Хранилище ────────────────────────────────────────────────────────────────
DATA_DIR = os.getenv("DATA_DIR", "./data")

# ── Параметры напоминаний ────────────────────────────────────────────────────
NOTIFY_BEFORE_MINUTES = [30, 5]   # за сколько минут уведомлять
DELETE_AFTER_MINUTES  = 5          # удалять через N минут после старта матча

# ── Часовой пояс по умолчанию (для новых пользователей) ──────────────────────
DEFAULT_TZ_OFFSET = int(os.getenv("DEFAULT_TZ_OFFSET", "3"))
