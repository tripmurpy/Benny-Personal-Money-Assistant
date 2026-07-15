"""Deterministic history across the legacy expense and income tables."""


class HistoryService:
    def __init__(self, db):
        self.db = db

    def recent(self, user_id: str, limit: int = 10) -> list[dict]:
        expenses = [
            {
                **row,
                "type": "expense",
                "table": "transactions",
                "item": row.get("item_name", row.get("item", "")),
            }
            for row in self.db.get_recent_transactions(user_id, limit)
        ]
        incomes = [
            {
                **row,
                "type": "income",
                "table": "income",
                "item": row.get("source", row.get("item", "")),
            }
            for row in self.db.get_income(user_id)
        ]
        return sorted(
            expenses + incomes,
            key=lambda row: (str(row.get("date", "")), str(row.get("time", ""))),
            reverse=True,
        )[:limit]
