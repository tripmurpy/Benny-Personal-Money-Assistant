"""Telegram bot entry point."""

import logging

from telegram.error import BadRequest
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PicklePersistence,
    filters,
)

from config import Config
from services.telegram.bot import TelegramService
from services.gmail.ingestion import GmailTransactionIngestion

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.WARNING,
)
logging.getLogger("services").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Ignore harmless Telegram retries and log every other failure."""
    error = context.error
    if isinstance(error, BadRequest) and "Message is not modified" in str(error):
        return
    logger.error("Unhandled exception: %s", error, exc_info=error)


def setup_handlers(application, telegram_service):
    """Register the private bot's commands and message routes."""
    try:
        admin_filter = filters.User(user_id=int(Config.ADMIN_ID))
    except (ValueError, TypeError) as error:
        raise ValueError("ADMIN_CHAT_ID must be a numeric Telegram user ID") from error

    application.add_error_handler(error_handler)
    application.add_handler(CallbackQueryHandler(telegram_service.handle_button))
    application.add_handler(
        CommandHandler("start", telegram_service.start, filters=admin_filter)
    )
    application.add_handler(
        CommandHandler("help", telegram_service.help, filters=admin_filter)
    )
    application.add_handler(
        CommandHandler("roast", telegram_service.roast, filters=admin_filter)
    )
    application.add_handler(
        MessageHandler(
            (
                filters.TEXT
                | filters.PHOTO
                | filters.Document.IMAGE
                | filters.VOICE
            )
            & ~filters.COMMAND
            & admin_filter,
            telegram_service.handle_message,
        )
    )


def main():
    """Validate configuration, build the bot, and start polling."""
    try:
        Config.validate()
    except ValueError as error:
        logger.error("Configuration error: %s", error)
        raise SystemExit(1) from error

    telegram_service = TelegramService()
    application = (
        ApplicationBuilder()
        .token(Config.TELEGRAM_TOKEN)
        .persistence(PicklePersistence(filepath="bot-state.pickle"))
        .build()
    )
    application.bot_data["tg_service"] = telegram_service
    if Config.GMAIL_ENABLED:
        gmail = GmailTransactionIngestion(telegram_service.capture.ai, telegram_service.db)
        application.job_queue.run_repeating(
            gmail.sync, interval=Config.GMAIL_POLL_SECONDS, first=1, name="gmail-finance-sync"
        )
    setup_handlers(application, telegram_service)

    print("Bot activated")
    application.run_polling()


if __name__ == "__main__":
    main()
