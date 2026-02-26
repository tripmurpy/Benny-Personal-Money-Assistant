"""
Main Bot Entry Point - Clean & Optimized
"""

import logging
from datetime import datetime
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters, ContextTypes
)
from config import Config, Messages
from services.telegram_service import TelegramService
from services.goal_handlers import handle_set_goal, handle_goals, handle_delete_goal
from services.budget_handlers import (
    handle_set_budget, handle_budgets, handle_delete_budget, 
    check_budget_warning_job
)

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
    
    hours = (datetime.now() - tg_service.last_activity).total_seconds() / 3600
    
    if hours >= Config.INACTIVITY_HOURS:
        try:
            await context.bot.send_message(
                chat_id=Config.ADMIN_ID,
                text=Messages.INACTIVITY_REMINDER.format(hours=int(hours))
            )
            tg_service.last_activity = datetime.now()
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
        logger.warning("⚠️ ADMIN_ID not set or invalid. Security filter disabled (NOT SAFE).")
        admin_filter = filters.ALL

    # Global error handler
    app.add_error_handler(error_handler)

    # Core handlers
    app.add_handler(CallbackQueryHandler(tg_service.handle_button))
    app.add_handler(CommandHandler('start', tg_service.start, filters=admin_filter))
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.PHOTO | filters.VOICE) & (~filters.COMMAND) & admin_filter,
        tg_service.handle_message
    ))
    
    # Goal handlers
    for cmd, handler in [
        ('setgoal', handle_set_goal),
        ('goals', handle_goals),
        ('deletegoal', handle_delete_goal)
    ]:
        app.add_handler(CommandHandler(cmd, handler, filters=admin_filter))
    
    # Budget handlers
    for cmd, handler in [
        ('setbudget', handle_set_budget),
        ('set', handle_set_budget), # Alias for /set budget
        ('budgets', handle_budgets),
        ('deletebudget', handle_delete_budget)
    ]:
        app.add_handler(CommandHandler(cmd, handler, filters=admin_filter))


def setup_jobs(app):
    """Setup scheduled jobs."""
    from datetime import time
    job_queue = app.job_queue
    
    # Check inactivity every 6 hours
    job_queue.run_repeating(check_inactivity, interval=21600, first=60)
    
    # Check budget warnings every 6 hours
    job_queue.run_repeating(check_budget_warning_job, interval=21600, first=300)
    
    # Weekly coaching report - every Sunday at 18:00
    job_queue.run_daily(
        send_weekly_coaching_report, 
        time=time(18, 0),  # 18:00 local time
        days=(6,)  # Sunday = 6
    )


async def send_weekly_coaching_report(context):
    """Send weekly AI coaching report to user."""
    from services.ai.coaching_engine import get_coaching_engine
    from services.sheets_service import SheetsService
    from datetime import datetime, timedelta
    
    try:
        sheets_service = SheetsService()
        coaching_engine = get_coaching_engine()
        
        # Get transactions for current and previous week
        all_data = sheets_service.get_all_transactions()
        today = datetime.now()
        current_week_start = today - timedelta(days=7)
        
        current_week = []
        previous_week = []
        
        for t in all_data:
            try:
                date_str = str(t.get('DATE') or t.get('date') or '')
                if date_str:
                    t_date = datetime.strptime(date_str, '%Y-%m-%d')
                    if t_date >= current_week_start:
                        current_week.append(t)
                    elif t_date >= current_week_start - timedelta(days=7):
                        previous_week.append(t)
            except ValueError:
                continue
        
        # Generate and send report
        if current_week:  # Only send if there are transactions
            report_data = coaching_engine.generate_weekly_report(current_week, previous_week)
            message = coaching_engine.format_weekly_report_message(report_data)
            
            await context.bot.send_message(
                chat_id=Config.ADMIN_ID,
                text="📅 *LAPORAN MINGGUAN OTOMATIS*\n\n" + message,
                parse_mode='Markdown'
            )
            logger.info("✅ Weekly coaching report sent")
            
    except Exception as e:
        logger.error(f"Failed to send weekly coaching report: {e}")


import asyncio
import sys

# ... imports ...

def main():
    """Main bot entry point."""
    # Fix AsyncIO Windows Loop Policy
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Validate config
    try:
        Config.validate()
        logger.info("✅ Configuration validated")
    except Exception as e:
        logger.error(f"❌ Configuration error: {e}")
        exit(1)
    
    # Initialize services
    tg_service = TelegramService()
    application = ApplicationBuilder().token(Config.TELEGRAM_TOKEN).build()
    application.bot_data['tg_service'] = tg_service
    
    # Setup handlers and jobs
    setup_handlers(application, tg_service)
    setup_jobs(application)
    
    # Start bot
    logger.info("🚀 Bot starting...")
    logger.info("✅ Features: Text, OCR, Voice, Smart Nudging, Goals, Budgets")
    application.run_polling()


if __name__ == '__main__':
    main()
