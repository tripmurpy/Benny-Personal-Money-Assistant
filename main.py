"""
Main Bot Entry Point - Clean & Optimized
"""

import logging
from datetime import datetime
from telegram.error import BadRequest
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, PicklePersistence, filters, ContextTypes
)
from config import Config
from services.telegram_service import TelegramService
from services.goal_handlers import (
    handle_set_goal, handle_goals, handle_delete_goal,
    handle_contribute_goal, handle_withdraw_goal, handle_goal_history,
)
from services.budget_handlers import (
    handle_set_budget, handle_budgets, handle_delete_budget,
    check_budget_warning_job
)
from services.reminder_handlers import handle_reminder
from services.reminder_service import ReminderService

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.WARNING  # Clean Output: Only Errors & Warnings
)
# Keep our own logs visible if needed, but default WARNING ensures silence
logging.getLogger("services").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
# Force current module to INFO just for startup messages, then we can silence it
logger.setLevel(logging.INFO)


async def check_inactivity(context):
    """Send reminder if user inactive > 24 hours."""
    tg_service = context.bot_data.get('tg_service')
    if not tg_service:
        return

    now = datetime.now()
    reminder = ReminderService(tg_service.db, Config.ADMIN_ID)
    if reminder.should_send(tg_service.last_activity, now):
        try:
            await context.bot.send_message(
                chat_id=Config.ADMIN_ID,
                text="Ada transaksi hari ini yang belum tercatat?"
            )
            reminder.mark_sent(now)
        except Exception as e:
            logger.error(f"Inactivity check failed: {e}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler - gracefully handle common Telegram API errors."""
    error = context.error

    # Silently ignore "Message is not modified" errors (caused by double-tapping buttons)
    if isinstance(error, BadRequest) and "Message is not modified" in str(error):
        return  # Harmless, just ignore

    # Log everything else
    logger.error(f"Unhandled exception: {error}", exc_info=context.error)


def setup_handlers(app, tg_service):
    """Setup all command and message handlers."""
    # Security Filter
    try:
        admin_id = int(Config.ADMIN_ID)
        admin_filter = filters.User(user_id=admin_id)
    except (ValueError, TypeError):
        raise ValueError("ADMIN_CHAT_ID must be a numeric Telegram user ID")

    # Global error handler
    app.add_error_handler(error_handler)

    # Core handlers
    app.add_handler(CallbackQueryHandler(tg_service.handle_button))
    app.add_handler(CommandHandler('start', tg_service.start, filters=admin_filter))
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.PHOTO | filters.Document.IMAGE | filters.VOICE)
        & (~filters.COMMAND)
        & admin_filter,
        tg_service.handle_message
    ))

    # Goal handlers
    for cmd, handler in [
        ('setgoal', handle_set_goal),
        ('goals', handle_goals),
        ('contributegoal', handle_contribute_goal),
        ('withdrawgoal', handle_withdraw_goal),
        ('goalhistory', handle_goal_history),
        ('deletegoal', handle_delete_goal)
    ]:
        app.add_handler(CommandHandler(cmd, handler, filters=admin_filter))

    app.add_handler(CommandHandler('reminder', handle_reminder, filters=admin_filter))

    # Budget handlers
    for cmd, handler in [
        ('setbudget', handle_set_budget),
        ('set', handle_set_budget),  # Alias for /set budget
        ('budgets', handle_budgets),
        ('deletebudget', handle_delete_budget)
    ]:
        app.add_handler(CommandHandler(cmd, handler, filters=admin_filter))


def setup_jobs(app):
    """Setup scheduled jobs."""
    from datetime import time
    job_queue = app.job_queue

    # Check the selected reminder window every 15 minutes
    job_queue.run_repeating(check_inactivity, interval=900, first=60)

    # Check budget warnings every 6 hours
    job_queue.run_repeating(check_budget_warning_job, interval=21600, first=300)

    # Weekly coaching report - every Sunday at 18:00
    job_queue.run_daily(
        send_weekly_coaching_report,
        time=time(18, 0),  # 18:00 local time
        days=(6,)  # Sunday = 6
    )


async def send_weekly_coaching_report(context):
    """Send one deterministic weekly insight and one action."""
    from services.supabase_service import SupabaseService
    from datetime import datetime, timedelta

    try:
        db = SupabaseService()
        uid = str(Config.ADMIN_ID)

        today = datetime.now()
        week_start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        prev_week_start = (today - timedelta(days=14)).strftime("%Y-%m-%d")
        today_str = today.strftime("%Y-%m-%d")

        current_week = db.get_transactions_by_date(uid, week_start, today_str)
        previous_week = db.get_transactions_by_date(uid, prev_week_start, week_start)

        if current_week:
            current_total = sum(max(0, int(row.get("amount", 0))) for row in current_week)
            previous_total = sum(max(0, int(row.get("amount", 0))) for row in previous_week)
            delta = current_total - previous_total
            categories = {}
            for row in current_week:
                category = str(row.get("category", "Other"))
                categories[category] = categories.get(category, 0) + max(
                    0, int(row.get("amount", 0))
                )
            top_category = max(categories, key=categories.get)
            direction = "naik" if delta > 0 else "turun" if delta < 0 else "tetap"
            message = (
                "Ringkasan 7 Hari\n\n"
                f"Pengeluaran Rp{current_total:,.0f}, {direction} "
                f"Rp{abs(delta):,.0f} dari minggu lalu.\n"
                f"Terbesar: {top_category} · Rp{categories[top_category]:,.0f}\n\n"
                f"Tindakan: periksa transaksi {top_category} di Riwayat."
            ).replace(",", ".")

            await context.bot.send_message(
                chat_id=Config.ADMIN_ID,
                text=message,
            )
            logger.info("✅ Weekly digest sent")

    except Exception as e:
        logger.error(f"Failed to send weekly digest: {e}")


# ... imports ...

def main():
    """Main bot entry point."""

    # Validate config
    try:
        Config.validate()
    except Exception as e:
        logger.error(f"❌ Configuration error: {e}")
        exit(1)

    # Initialize services
    tg_service = TelegramService()
    application = (
        ApplicationBuilder()
        .token(Config.TELEGRAM_TOKEN)
        .persistence(PicklePersistence(filepath="bot-state.pickle"))
        .build()
    )
    application.bot_data['tg_service'] = tg_service

    # Setup handlers and jobs
    setup_handlers(application, tg_service)
    setup_jobs(application)

    # Start bot
    print("Bot activated")
    application.run_polling()


if __name__ == '__main__':
    main()
