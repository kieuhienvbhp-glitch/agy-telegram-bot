import asyncio
import logging
import sys
from telegram import BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

from config import Config
from agy_client import agy_client
from scheduled_tasks import scheduled_task_manager
from handlers.start import start_command, help_command
from handlers.commands import (
    new_command,
    model_command,
    project_command,
    add_project_command,
    history_command,
    stop_command,
    status_command,
    schedule_command,
    tasks_command,
    deltask_command
)
from handlers.chat import handle_text_message, handle_media_message
from handlers.callbacks import handle_callback_query

# Logging setup
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Config.STORAGE_DIR / "bot.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

async def post_init(application):
    """
    Configure bot commands and restore scheduled background tasks.
    """
    commands = [
        BotCommand("start", "Bảng điều khiển Antigravity"),
        BotCommand("new", "Bắt đầu cuộc trò chuyện mới"),
        BotCommand("history", "Lịch sử cuộc trò chuyện"),
        BotCommand("model", "Chọn mô hình AI (Gemini, Claude...)"),
        BotCommand("project", "Quản lý thư mục dự án"),
        BotCommand("stop", "Dừng tác vụ agy đang chạy"),
        BotCommand("status", "Xem trạng thái hiện tại"),
        BotCommand("tasks", "Xem tác vụ định kỳ"),
        BotCommand("help", "Xem hướng dẫn chi tiết"),
    ]
    try:
        await application.bot.set_my_commands(commands)
        logger.info("Bot commands successfully registered with Telegram.")
    except Exception as e:
        logger.warning(f"Failed to register bot commands: {e}")

    # Load scheduled background jobs
    scheduled_task_manager.load_and_schedule_all(application)
    logger.info("Scheduled tasks initialized.")

def main():
    token = Config.TELEGRAM_BOT_TOKEN
    if not token or token == "your_telegram_bot_token_here":
        logger.error(
            "CRITICAL: TELEGRAM_BOT_TOKEN is not configured! "
            "Please edit .env and specify your bot token obtained from @BotFather."
        )
        sys.exit(1)

    # Check agy binary
    if not agy_client.is_agy_installed():
        logger.warning(
            f"WARNING: The agy binary '{Config.AGY_BIN_PATH}' was not found in PATH. "
            "Please ensure Google Antigravity CLI is installed on this Ubuntu system."
        )
    else:
        logger.info(f"agy CLI verified at '{Config.AGY_BIN_PATH}'.")

    # Build Application
    app = ApplicationBuilder().token(token).post_init(post_init).build()

    # Register Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("new", new_command))
    app.add_handler(CommandHandler("model", model_command))
    app.add_handler(CommandHandler("project", project_command))
    app.add_handler(CommandHandler("add_project", add_project_command))
    app.add_handler(CommandHandler("history", history_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("schedule", schedule_command))
    app.add_handler(CommandHandler("tasks", tasks_command))
    app.add_handler(CommandHandler("deltask", deltask_command))

    # Register Callback Queries (inline buttons)
    app.add_handler(CallbackQueryHandler(handle_callback_query))

    # Register Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_media_message))

    logger.info("Google Antigravity Telegram Bot is starting...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
