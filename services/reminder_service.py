"""Persistent reminder preferences for the private user."""

from datetime import datetime, timedelta

from config import Config
from services.supabase_service import SupabaseService


class ReminderService:
    def __init__(self, db=None, user_id=None):
        self.db = db or SupabaseService()
        self.user_id = str(Config.ADMIN_ID if user_id is None else user_id)

    def get_preferences(self) -> dict:
        context = self.db.get_context(self.user_id)
        stored = context.get("reminder", {}) if isinstance(context, dict) else {}
        return {
            "enabled": stored.get("enabled", True),
            "time": stored.get("time", "18:00"),
            "snoozed_until": stored.get("snoozed_until"),
            "last_sent": stored.get("last_sent"),
        }

    def update(self, **changes) -> bool:
        context = self.db.get_context(self.user_id)
        context = dict(context) if isinstance(context, dict) else {}
        preferences = self.get_preferences()
        preferences.update(changes)
        context["reminder"] = preferences
        return self.db.set_context(self.user_id, context)

    def snooze(self, hours: int = 2, now: datetime | None = None) -> bool:
        if hours <= 0 or hours > 168:
            return False
        until = (now or datetime.now()) + timedelta(hours=hours)
        return self.update(snoozed_until=until.isoformat(timespec="minutes"))

    def should_send(self, last_activity: datetime, now: datetime | None = None) -> bool:
        current = now or datetime.now()
        preferences = self.get_preferences()
        if not preferences["enabled"] or (current - last_activity) < timedelta(hours=24):
            return False
        if preferences["last_sent"] == current.date().isoformat():
            return False
        if preferences["snoozed_until"]:
            try:
                if current < datetime.fromisoformat(preferences["snoozed_until"]):
                    return False
            except ValueError:
                pass
        try:
            hour, minute = map(int, preferences["time"].split(":"))
        except (AttributeError, TypeError, ValueError):
            return False
        return current.hour == hour and minute <= current.minute < minute + 15

    def mark_sent(self, now: datetime | None = None) -> bool:
        return self.update(
            last_sent=(now or datetime.now()).date().isoformat(),
            snoozed_until=None,
        )
