"""
Goals Service — Supabase-backed financial goals management.

Thin wrapper over SupabaseService for goals-specific logic.
"""

from services.supabase_service import SupabaseService
from config import Config
import logging

logger = logging.getLogger(__name__)


class GoalsService:
    """Financial goals CRUD backed by Supabase."""

    def __init__(self):
        self.db = SupabaseService()
        self.user_id = str(Config.ADMIN_ID)  # Single-user bot

    def set_goal(self, name: str, target_amount: int, note: str = "-") -> bool:
        """Create a new goal. Returns False if name already exists."""
        goals = self.get_goals()
        for g in goals:
            if g.get("name", "").lower() == name.lower():
                return False  # Duplicate

        return self.db.create_goal(
            self.user_id, name, target_amount, deadline=None
        )

    def get_goals(self) -> list[dict]:
        """Get all active goals."""
        return self.db.get_goals(self.user_id)

    def delete_goal(self, name: str) -> bool:
        """Soft-delete a goal by name."""
        goals = self.get_goals()
        for g in goals:
            if g.get("name", "").lower() == name.lower():
                return self.db.delete_goal(g["id"])
        return False

    def get_formatted_goals_progress(self, current_savings: int = 0) -> str:
        """Format goals as a Telegram-friendly progress display."""
        goals = self.get_goals()
        if not goals:
            return "Belum ada Goal yang diset. Pakai /setgoal <nama> <target>"

        msg = "🎯 **Financial Goals**\n\n"
        for g in goals:
            name = g.get("name", "?")
            target = int(g.get("target_amount") or 0)
            saved = int(g.get("current_amount") or 0)

            progress = min(1.0, saved / target) if target > 0 else 0
            bar_len = 10
            filled = int(progress * bar_len)
            bar = "▓" * filled + "░" * (bar_len - filled)
            pct = int(progress * 100)

            msg += f"📌 **{name}**\n"
            msg += f"{bar} {pct}%\n"
            msg += f"Rp {saved:,} / Rp {target:,}\n\n"

        return msg
