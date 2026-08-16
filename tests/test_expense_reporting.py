import unittest
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from services.reporting.service import ExpenseReportService


class FakeAI:
    def __init__(self, result):
        self.result = result

    async def parse_report_request(self, _text, _now):
        return self.result


class FakeDB:
    def __init__(self, rows):
        self.rows = rows
        self.range = None

    def get_expenses_between(self, user_id, start, end):
        self.range = user_id, start, end
        return self.rows


class ExpenseReportingTest(unittest.IsolatedAsyncioTestCase):
    async def test_natural_query_returns_exact_deterministic_report(self):
        request = {
            "intent": "expense_report",
            "start_at": "2026-08-10T00:00:00",
            "end_at": "2026-08-12T14:00:00",
            "needs_clarification": False,
        }
        db = FakeDB([
            {
                "date": "2026-08-11", "time": "19:30:00", "item_name": "Kopi",
                "category": "Drink", "amount": 25_000, "location": "Fore",
                "payment_method": "QRIS", "notes": "",
            },
            {
                "date": "2026-08-12", "time": "08:00:00", "item_name": "Nasi Padang",
                "category": "Food", "amount": 30_000, "location": "", "payment_method": "",
                "notes": "",
            },
        ])
        replies = []

        async def reply(_message, text):
            replies.append(text)

        service = ExpenseReportService(
            FakeAI(request), db, reply,
            now=lambda: datetime(2026, 8, 12, 15, tzinfo=ZoneInfo("Asia/Bangkok")),
        )
        update = SimpleNamespace(
            message=SimpleNamespace(text="pengeluaran 3 hari terakhir berapa?"),
            effective_user=SimpleNamespace(id=7),
        )

        self.assertTrue(await service.try_handle(update))
        self.assertEqual(db.range[0], "7")
        output = "\n".join(replies)
        self.assertIn("2 transaksi", output)
        self.assertIn("Rp55.000", output)
        self.assertIn("Kopi — Rp25.000", output)
        self.assertIn("Kategori: Minuman", output)
        self.assertIn("Lokasi: Fore", output)
        self.assertNotRegex(output, "[\U0001F300-\U0001FAFF]")

    async def test_new_transaction_bypasses_report_model(self):
        service = ExpenseReportService(FakeAI(None), FakeDB([]), None)
        update = SimpleNamespace(
            message=SimpleNamespace(text="beli kopi hari ini 25 ribu"),
            effective_user=SimpleNamespace(id=7),
        )
        self.assertFalse(await service.try_handle(update))

        update.message.text = "pengeluaran kemarin 25 ribu"
        self.assertFalse(await service.try_handle(update))

    async def test_yesterday_typo_is_resolved_without_model(self):
        db = FakeDB([])
        replies = []

        async def reply(_message, text):
            replies.append(text)

        service = ExpenseReportService(
            FakeAI(None), db, reply,
            now=lambda: datetime(2026, 8, 13, 12, 37, tzinfo=ZoneInfo("Asia/Bangkok")),
        )
        update = SimpleNamespace(
            message=SimpleNamespace(text="kemarin aku bli apa"),
            effective_user=SimpleNamespace(id=7),
        )

        self.assertTrue(await service.try_handle(update))
        self.assertEqual(db.range[1].date().isoformat(), "2026-08-12")
        self.assertIn("Rp0", replies[0])
        self.assertIn("0 transaksi", replies[0])

        update.message.text = "kemaren aku beli apa"
        self.assertTrue(await service.try_handle(update))
        self.assertEqual(db.range[1].date().isoformat(), "2026-08-12")

    def test_future_or_reversed_range_is_rejected(self):
        current = datetime(2026, 8, 12, 15, tzinfo=ZoneInfo("Asia/Bangkok"))
        with self.assertRaises(ValueError):
            ExpenseReportService._range({
                "start_at": "2026-08-12T16:00:00",
                "end_at": "2026-08-12T17:00:00",
            }, current)

    def test_relative_days_are_calculated_by_code(self):
        current = datetime(2026, 8, 12, 15, tzinfo=ZoneInfo("Asia/Bangkok"))
        start, end = ExpenseReportService._range({
            "range_type": "last_n_days", "day_count": 3,
            "start_at": None, "end_at": None,
        }, current)
        self.assertEqual(start.isoformat(), "2026-08-10T00:00:00+07:00")
        self.assertEqual(end, current)

    def test_weekday_range_uses_last_completed_window(self):
        current = datetime(2026, 8, 12, 15, tzinfo=ZoneInfo("Asia/Bangkok"))
        start, end = ExpenseReportService._range({
            "range_type": "weekday_range", "start_weekday": 1,
            "end_weekday": 5, "end_time": "20:00:00",
        }, current)
        self.assertEqual(start.isoformat(), "2026-08-03T00:00:00+07:00")
        self.assertEqual(end.isoformat(), "2026-08-07T20:00:00+07:00")


if __name__ == "__main__":
    unittest.main()
