"""
Budget Service — Supabase-backed budget management.

Thin wrapper over SupabaseService for budget-specific logic
(top-up, deduction, threshold checks).
"""

from services.supabase_service import SupabaseService
from config import Config
import logging

logger = logging.getLogger(__name__)


class BudgetService:
    """Budget CRUD + business logic backed by Supabase."""

    def __init__(self):
        self.db = SupabaseService()
        self.user_id = str(Config.ADMIN_ID)  # Single-user bot

    def set_budget(self, category: str, limit: int) -> bool:
        return self.db.set_budget(self.user_id, category.lower(), limit)

    def get_budgets(self) -> dict:
        """Get all budgets as {category: monthly_limit} dict."""
        rows = self.db.get_budgets(self.user_id)
        return {r["category"]: r["monthly_limit"] for r in rows}

    def delete_budget(self, category: str) -> bool:
        return self.db.delete_budget(self.user_id, category.lower())

    def top_up_budget(self, category: str, amount: int) -> tuple[bool, int]:
        """Add amount to existing budget limit. Returns (success, new_limit)."""
        budgets = self.get_budgets()
        cat_lower = category.lower()

        if cat_lower not in budgets:
            return False, 0

        new_limit = budgets[cat_lower] + amount
        if self.set_budget(category, new_limit):
            return True, new_limit
        return False, 0

    def deduct_budget(self, category: str, amount: int) -> tuple[int, int]:
        """
        Deduct amount from budget.
        Returns (amount_deducted, excess_to_general).
        If budget=100k and spend=120k → (100k, 20k).
        """
        budgets = self.get_budgets()
        cat_lower = category.lower()

        if cat_lower not in budgets:
            return 0, amount  # No budget, all excess

        current_limit = budgets[cat_lower]

        if current_limit >= amount:
            self.set_budget(category, current_limit - amount)
            return amount, 0
        else:
            excess = amount - current_limit
            self.set_budget(category, 0)
            return current_limit, excess
