import unittest

from services.history_service import HistoryService


class FakeDatabase:
    def get_recent_transactions(self, _user_id, _limit):
        return [{"id": 1, "date": "2026-07-15", "time": "10:00", "item_name": "Kopi", "amount": 20_000}]

    def get_income(self, _user_id):
        return [{"id": 2, "date": "2026-07-15", "time": "11:00", "source": "Gaji", "amount": 1_000_000}]


class HistoryServiceTest(unittest.TestCase):
    def test_recent_normalizes_and_sorts_both_sources(self):
        rows = HistoryService(FakeDatabase()).recent("7")
        self.assertEqual([(row["type"], row["item"]) for row in rows], [("income", "Gaji"), ("expense", "Kopi")])
        self.assertEqual(rows[0]["table"], "income")


if __name__ == "__main__":
    unittest.main()
