from copy import deepcopy
from datetime import date

from services.budget_service import BudgetService


class FakeDatabase:
    def __init__(self):
        self.budgets = [{"category": "Food", "monthly_limit": 100_000}]
        self.transactions = []
        self.context = {"existing_key": "preserved"}
        self.set_budget_calls = []

    def get_budgets(self, user_id):
        return deepcopy(self.budgets)

    def set_budget(self, user_id, category, limit):
        self.set_budget_calls.append((user_id, category, limit))
        return True

    def delete_budget(self, user_id, category):
        return True

    def get_transactions_by_date(self, user_id, start, end):
        assert (start, end) == ("2026-07-01", "2026-07-31")
        return deepcopy(self.transactions)

    def get_context(self, user_id):
        return deepcopy(self.context)

    def set_context(self, user_id, context):
        self.context = deepcopy(context)
        return True


def verify_budget_logic():
    db = FakeDatabase()
    service = BudgetService(db=db, user_id="qa-user")
    as_of = date(2026, 7, 15)

    db.transactions = [
        {"category": "Food", "amount": 50_000},
        {"category": "food", "amount": 30_000},
        {"category": "Transport", "amount": 99_000},
    ]
    status = service.get_budget_statuses(as_of)["food"]
    assert status == {"limit": 100_000, "used": 80_000, "remaining": 20_000, "percentage": 80.0}

    assert db.set_budget_calls == [], "capturing an expense must not mutate monthly_limit"

    alerts = service.get_pending_alerts(as_of)
    assert [(alert["category"], alert["threshold"]) for alert in alerts] == [("food", 80)]
    assert service.mark_alerts_sent(alerts, as_of)
    assert service.get_pending_alerts(as_of) == []
    assert db.context["existing_key"] == "preserved"

    db.transactions[0]["amount"] = 70_000  # edit: usage is recomputed, now 100%
    assert service.get_budget_statuses(as_of)["food"]["used"] == 100_000
    alerts = service.get_pending_alerts(as_of)
    assert alerts[0]["threshold"] == 100
    assert service.mark_alerts_sent(alerts, as_of)
    assert service.get_pending_alerts(as_of) == []

    db.transactions.pop()  # delete unrelated category
    db.transactions.pop(0)  # delete edited Food transaction
    status = service.get_budget_statuses(as_of)["food"]
    assert status["used"] == 30_000 and status["remaining"] == 70_000


if __name__ == "__main__":
    verify_budget_logic()
    print("Budget verification passed")
