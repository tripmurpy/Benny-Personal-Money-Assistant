"""Supabase-backed fixed monthly budgets."""

from calendar import monthrange
from datetime import date

from config import Config
from services.supabase_service import SupabaseService


class BudgetService:
    """Budget CRUD and transaction-derived usage."""

    def __init__(self, db=None, user_id=None):
        self.db = db or SupabaseService()
        self.user_id = str(Config.ADMIN_ID if user_id is None else user_id)

    def set_budget(self, category: str, limit: int) -> bool:
        return self.db.set_budget(self.user_id, category.lower(), limit)

    def get_budgets(self) -> dict:
        """Get fixed limits as {category: monthly_limit}."""
        return {
            str(row["category"]).lower(): int(row["monthly_limit"])
            for row in self.db.get_budgets(self.user_id)
        }

    def get_budget_statuses(self, as_of: date | None = None) -> dict:
        """Return limits and current-month usage derived from expense rows."""
        current = as_of or date.today()
        month_start = current.replace(day=1)
        month_end = current.replace(day=monthrange(current.year, current.month)[1])
        budgets = self.get_budgets()
        if not budgets:
            return {}
        used = {category: 0 for category in budgets}

        for transaction in self.db.get_transactions_by_date(
            self.user_id, month_start.isoformat(), month_end.isoformat()
        ):
            category = str(transaction.get("category", "")).lower()
            if category not in used:
                continue
            try:
                amount = int(transaction.get("amount", 0))
            except (TypeError, ValueError):
                continue
            used[category] += max(0, amount)

        return {
            category: {
                "limit": limit,
                "used": used[category],
                "remaining": limit - used[category],
                "percentage": round(used[category] / limit * 100, 1) if limit > 0 else 0,
            }
            for category, limit in budgets.items()
        }

    def delete_budget(self, category: str) -> bool:
        return self.db.delete_budget(self.user_id, category.lower())

    def top_up_budget(self, category: str, amount: int) -> tuple[bool, int]:
        """Explicitly increase an existing fixed limit."""
        budgets = self.get_budgets()
        cat_lower = category.lower()
        if cat_lower not in budgets:
            return False, 0

        new_limit = budgets[cat_lower] + amount
        return (True, new_limit) if self.set_budget(category, new_limit) else (False, 0)

    def get_pending_alerts(self, as_of: date | None = None) -> list[dict]:
        """Return the highest newly crossed threshold for each category."""
        current = as_of or date.today()
        period = current.strftime("%Y-%m")
        context = self.db.get_context(self.user_id)
        alert_history = context.get("budget_alerts", {}) if isinstance(context, dict) else {}
        sent = alert_history.get(period, {}) if isinstance(alert_history, dict) else {}
        sent = sent if isinstance(sent, dict) else {}
        warning = 80

        alerts = []
        for category, status in self.get_budget_statuses(current).items():
            crossed = 100 if status["percentage"] >= 100 else warning if status["percentage"] >= warning else 0
            sent_threshold = sent.get(category, 0)
            sent_threshold = sent_threshold if isinstance(sent_threshold, (int, float)) else 0
            if crossed > sent_threshold:
                alerts.append({"category": category, "threshold": crossed, **status})
        return alerts

    def mark_alerts_sent(self, alerts: list[dict], as_of: date | None = None) -> bool:
        """Persist per-month/category alert high-watermarks in user_context."""
        if not alerts:
            return True

        period = (as_of or date.today()).strftime("%Y-%m")
        context = self.db.get_context(self.user_id)
        context = dict(context) if isinstance(context, dict) else {}
        stored_history = context.get("budget_alerts", {})
        alert_history = dict(stored_history) if isinstance(stored_history, dict) else {}
        stored_sent = alert_history.get(period, {})
        sent = dict(stored_sent) if isinstance(stored_sent, dict) else {}
        for alert in alerts:
            category = str(alert["category"]).lower()
            sent[category] = max(int(sent.get(category, 0)), int(alert["threshold"]))
        alert_history[period] = sent
        context["budget_alerts"] = alert_history
        return self.db.set_context(self.user_id, context)
