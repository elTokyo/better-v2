import logging
import threading
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
)

import config
import handlers
from scheduler import setup_scheduler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def start_discord_in_background():
    """Discord-бот работает в отдельном потоке параллельно с TG."""
    if not config.DISCORD_TOKEN:
        logger.info("Discord listener отключён (нет DISCORD_TOKEN)")
        return

    from discord_listener import run_discord_listener

    def runner():
        try:
            run_discord_listener()
        except Exception as e:
            logger.exception(f"Discord listener crashed: {e}")

    t = threading.Thread(target=runner, daemon=True, name="discord-listener")
    t.start()
    logger.info("Discord listener запущен в фоне")


def main():
    if not config.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан в переменных окружения")

    app = Application.builder().token(config.BOT_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start",    handlers.cmd_start))
    app.add_handler(CommandHandler("add",      handlers.cmd_add))
    app.add_handler(CommandHandler("list",     handlers.cmd_list))
    app.add_handler(CommandHandler("delete",   handlers.cmd_delete))
    app.add_handler(CommandHandler("clear",    handlers.cmd_clear))
    app.add_handler(CommandHandler("settings", handlers.cmd_settings))

    # Кнопки + текст
    app.add_handler(CallbackQueryHandler(handlers.on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.on_text))

    # Планировщик уведомлений и автоудаления
    setup_scheduler(app)

    # Discord-слушатель (в отдельном потоке)
    start_discord_in_background()

    logger.info("TG бот запущен")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
