import os

# ── Telegram ─────────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# ── Авторизация ──────────────────────────────────────────────────────────────
ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD", "")         # пароль для доступа
ADMIN_CHAT_ID   = int(os.getenv("ADMIN_CHAT_ID", "0"))     # твой TG chat_id

# ── Discord (опционально) ────────────────────────────────────────────────────
DISCORD_TOKEN             = os.getenv("DISCORD_TOKEN", "")
DISCORD_CHANNEL_ID        = int(os.getenv("DISCORD_CHANNEL_ID", "0"))
DISCORD_TARGET_TG_CHAT_ID = int(os.getenv("DISCORD_TARGET_TG_CHAT_ID", "0"))

# ── Хранилище ────────────────────────────────────────────────────────────────
DATA_DIR = os.getenv("DATA_DIR", "./data")

# ── Параметры напоминаний ────────────────────────────────────────────────────
NOTIFY_BEFORE_MINUTES = [30, 5]
DELETE_AFTER_MINUTES  = 5

# ── Часовой пояс по умолчанию ────────────────────────────────────────────────
DEFAULT_TZ_OFFSET = int(os.getenv("DEFAULT_TZ_OFFSET", "3"))
