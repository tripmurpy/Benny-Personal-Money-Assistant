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

    def __init__(self, db=None, user_id: str = None):
        self.db = db or SupabaseService()
        self.user_id = user_id or str(Config.ADMIN_ID)  # Single-user bot

    def set_goal(self, name: str, target_amount: int, note: str = "-") -> bool:
        """Create a new goal. Returns False if name already exists."""
        name = name.strip()
        if not name or target_amount <= 0:
            return False
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
        goal = self._find_goal(name)
        return bool(goal and self.db.delete_goal(self.user_id, goal["id"]))

    def _find_goal(self, name: str):
        return next(
            (g for g in self.get_goals() if g.get("name", "").lower() == name.lower()),
            None,
        )

    def contribute(self, name: str, amount: int):
        """Add money to a goal and return its updated row."""
        goal = self._find_goal(name)
        if not goal or amount <= 0:
            return None
        return self.db.contribute_goal(self.user_id, goal["id"], amount)

    def withdraw(self, name: str, amount: int):
        """Withdraw money without allowing a negative balance."""
        goal = self._find_goal(name)
        if not goal or amount <= 0:
            return None
        return self.db.withdraw_goal(self.user_id, goal["id"], amount)

    def get_history(self, name: str) -> list[dict]:
        goal = self._find_goal(name)
        return self.db.get_goal_history(self.user_id, goal["id"]) if goal else []

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

    def get_formatted_history(self, name: str) -> str:
        goal = self._find_goal(name)
        if not goal:
            return f"❌ Goal '{name}' tidak ditemukan."

        history = self.db.get_goal_history(self.user_id, goal["id"])
        if not history:
            return f"Belum ada riwayat untuk goal **{goal['name']}**."

        labels = {
            "created": "Dibuat",
            "contribute": "Tambah",
            "withdraw": "Ambil",
            "cancelled": "Dibatalkan",
        }
        lines = [f"📜 **Riwayat {goal['name']}**", ""]
        for entry in history:
            action = entry.get("action", "")
            delta = int(entry.get("amount_delta") or 0)
            amount = f" {delta:+,}" if delta else ""
            lines.append(
                f"{labels.get(action, action.title())}{amount} · Saldo Rp {int(entry.get('balance_after') or 0):,}"
            )
        return "\n".join(lines)
