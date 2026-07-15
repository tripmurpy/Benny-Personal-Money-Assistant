"""Telegram command for reminder preferences."""

from telegram import Update
from telegram.ext import ContextTypes

from services.reminder_service import ReminderService
from services.event_logger import log_event

reminders = ReminderService()


async def handle_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = [arg.lower() for arg in context.args]
    if not args:
        prefs = reminders.get_preferences()
        status = "aktif" if prefs["enabled"] else "nonaktif"
        await update.message.reply_text(f"Reminder {status} · {prefs['time']}")
        return

    action = args[0]
    if action in {"on", "off"}:
        success = reminders.update(enabled=action == "on")
    elif action == "snooze":
        try:
            hours = int(args[1]) if len(args) > 1 else 2
        except ValueError:
            hours = 0
        success = reminders.snooze(hours)
    else:
        try:
            hour, minute = map(int, action.split(":"))
            valid = 0 <= hour <= 23 and 0 <= minute <= 59
        except ValueError:
            valid = False
        success = valid and reminders.update(time=f"{hour:02d}:{minute:02d}")

    await update.message.reply_text(
        "Preferensi reminder tersimpan."
        if success else "Format: /reminder on|off|HH:MM|snooze [jam]"
    )
    if success and action == "snooze":
        log_event("reminder_snoozed", update.effective_user.id)
    elif success and action == "off":
        log_event("reminder_disabled", update.effective_user.id)
