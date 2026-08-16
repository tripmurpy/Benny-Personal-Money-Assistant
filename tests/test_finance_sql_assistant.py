import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from config import Config
from services.reporting.sql_assistant import FinanceSqlAssistant
from services.telegram.bot import TelegramService


LEDGER = [
    {"kind": "expense", "date": "2026-08-01", "time": "10:00:00", "name": "Kopi", "category": "Drink", "amount": 25_000, "notes": "meeting", "location": "Fore"},
    {"kind": "expense", "date": "2026-08-02", "time": "12:00:00", "name": "Nasi", "category": "Food", "amount": 30_000},
    {"kind": "income", "date": "2026-08-03", "time": "09:00:00", "name": "Gaji", "category": "Income", "amount": 100_000},
]


class FakeAI:
    def __init__(self, sql):
        self.sql = sql

    async def generate_finance_sql(self, _question, _today):
        return {"intent": "query", "sql": self.sql, "clarification": ""}


class FakeDB:
    def __init__(self, rows=LEDGER):
        self.rows = rows
        self.user_id = None

    def get_finance_snapshot(self, user_id):
        self.user_id = user_id
        return {"rows": self.rows, "truncated": False}


class FinanceSqlAssistantTest(unittest.IsolatedAsyncioTestCase):
    def test_sql_executes_aggregate_and_date_range_correctly(self):
        columns, rows = FinanceSqlAssistant.execute(
            LEDGER,
            "SELECT SUM(amount) AS total_pengeluaran FROM ledger "
            "WHERE kind='expense' AND date BETWEEN '2026-08-01' AND '2026-08-02'",
        )
        self.assertEqual(columns, ["total_pengeluaran"])
        self.assertEqual(rows, [(55_000,)])

    def test_sql_executes_case_insensitive_name_search(self):
        columns, rows = FinanceSqlAssistant.execute(
            [*LEDGER, {"kind": "expense", "date": "2026-08-04", "time": "10:00:00", "name": "ChatGPT Plus", "category": "Subscription", "amount": 349_000}],
            "SELECT SUM(amount) AS total_pengeluaran FROM ledger "
            "WHERE kind='expense' AND lower(name) LIKE '%chatgpt%'",
        )
        self.assertEqual(columns, ["total_pengeluaran"])
        self.assertEqual(rows, [(349_000,)])

    def test_sql_rejects_writes_other_tables_and_unbounded_details(self):
        unsafe = (
            "DELETE FROM ledger",
            "SELECT * FROM sqlite_master LIMIT 10",
            "SELECT * FROM ledger",
            "SELECT * FROM ledger LIMIT 101",
            "SELECT * FROM ledger; SELECT * FROM ledger",
        )
        for sql in unsafe:
            with self.subTest(sql=sql), self.assertRaises(ValueError):
                FinanceSqlAssistant.validate(sql)

        self.assertTrue(FinanceSqlAssistant.validate(
            "WITH totals AS (SELECT category, SUM(amount) AS amount FROM ledger GROUP BY category) "
            "SELECT * FROM totals ORDER BY amount DESC LIMIT 5"
        ).startswith("WITH totals"))

    async def test_query_is_user_scoped_and_returns_structured_rupiah(self):
        db, replies = FakeDB(), []

        async def reply(_message, text, **_kwargs):
            replies.append(text)

        service = FinanceSqlAssistant(
            FakeAI("SELECT category, SUM(amount) AS total_pengeluaran FROM ledger "
                   "WHERE kind='expense' GROUP BY category ORDER BY total_pengeluaran DESC LIMIT 5"),
            db,
            reply,
            today=lambda: date(2026, 8, 14),
        )
        update = SimpleNamespace(
            message=SimpleNamespace(text="kategori paling boros"),
            effective_user=SimpleNamespace(id=77),
        )

        self.assertTrue(await service.try_handle(update))
        self.assertEqual(db.user_id, "77")
        self.assertIn("Pengeluaran Terbesar", replies[0])
        self.assertNotIn("ANALISIS KEUANGAN", replies[0])
        self.assertIn("Total pengeluaran: <b>Rp30.000</b>", replies[0])
        self.assertIn("Kategori: Makanan", replies[0])

    async def test_simple_indonesian_history_query_returns_complete_transaction(self):
        db, replies = FakeDB(), []

        async def reply(_message, text, **_kwargs):
            replies.append(text)

        service = FinanceSqlAssistant(
            FakeAI(
                "SELECT name AS transaksi, date, time, notes AS note, amount AS harga, "
                "location AS lokasi FROM ledger WHERE kind='expense' "
                "AND amount BETWEEN 10000 AND 60000 ORDER BY date DESC LIMIT 100"
            ),
            db,
            reply,
            today=lambda: date(2026, 8, 14),
        )
        update = SimpleNamespace(
            message=SimpleNamespace(text="aku beli apa aja range 10-60 ribu"),
            effective_user=SimpleNamespace(id=77),
        )

        self.assertTrue(await service.try_handle(update))
        output = "\n".join(replies)
        self.assertIn("Daftar Transaksi", output)
        self.assertNotIn("Pertanyaan", output)
        self.assertIn("2. Kopi", output)
        self.assertIn("2026-08-01 10:00:00", output)
        self.assertIn("Catatan: meeting", output)
        self.assertIn("<b>Rp25.000</b>", output)
        self.assertEqual(output.count("<b>Rp25.000</b>"), 1)
        self.assertIn("Lokasi: Fore", output)

    def test_simple_subscription_date_question_reaches_sql_route(self):
        self.assertTrue(FinanceSqlAssistant.looks_like_query("kapan aku subscribe ChatGPT"))

    def test_frequency_aggregate_keeps_count_and_total(self):
        output = FinanceSqlAssistant.format_answers(
            ["transaksi", "jumlah_transaksi", "total_pengeluaran"],
            [("Kopi", 6, 150_000)],
            "pengeluaran apa yg paling sering?",
        )[0]
        self.assertIn("Transaksi: Kopi", output)
        self.assertIn("Jumlah transaksi: 6", output)
        self.assertIn("Total pengeluaran: <b>Rp150.000</b>", output)

    async def test_transaction_statement_stays_outside_sql_route(self):
        service = FinanceSqlAssistant(FakeAI(""), FakeDB(), None)
        update = SimpleNamespace(
            message=SimpleNamespace(text="beli kopi 25 ribu"),
            effective_user=SimpleNamespace(id=77),
        )
        self.assertFalse(await service.try_handle(update))

    async def test_finance_write_request_is_rejected_before_database_access(self):
        db, replies = FakeDB(), []

        async def reply(_message, text, **_kwargs):
            replies.append(text)

        service = FinanceSqlAssistant(FakeAI(""), db, reply)
        update = SimpleNamespace(
            message=SimpleNamespace(text="hapus semua transaksi"),
            effective_user=SimpleNamespace(id=77),
        )
        self.assertTrue(await service.try_handle(update))
        self.assertIsNone(db.user_id)
        self.assertIn("hanya dapat membaca", replies[0])

    async def test_telegram_routes_sql_before_capture(self):
        original_admin = Config.ADMIN_ID
        Config.ADMIN_ID = "77"
        try:
            service = TelegramService.__new__(TelegramService)
            service.db = Mock()
            service.reports = SimpleNamespace(try_handle=AsyncMock(return_value=False))
            service.sql_assistant = SimpleNamespace(try_handle=AsyncMock(return_value=True))
            service.capture = SimpleNamespace(handle=AsyncMock())
            update = SimpleNamespace(
                message=SimpleNamespace(text="kategori paling boros bulan ini"),
                effective_user=SimpleNamespace(id=77, username="owner", first_name="Owner"),
                effective_chat=SimpleNamespace(id=77),
            )

            await service.handle_message(update, SimpleNamespace())

            service.sql_assistant.try_handle.assert_awaited_once_with(update)
            service.capture.handle.assert_not_awaited()
        finally:
            Config.ADMIN_ID = original_admin


if __name__ == "__main__":
    unittest.main()
