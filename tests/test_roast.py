import unittest
from datetime import date
from types import SimpleNamespace

from config import Config
from main import setup_handlers
from services.ai.service import AIService
from services.reporting.roast import RoastService


LEDGER = [
    {"kind": "expense", "date": "2026-08-01", "time": "08:00:00", "name": "Kopi", "category": "Drink", "amount": 25_000, "notes": "private", "location": "Cafe"},
    {"kind": "expense", "date": "2026-08-02", "time": "08:00:00", "name": "Kopi", "category": "Drink", "amount": 25_000},
    {"kind": "expense", "date": "2026-08-03", "time": "08:00:00", "name": "Kopi", "category": "Drink", "amount": 25_000},
    {"kind": "expense", "date": "2026-08-04", "time": "12:00:00", "name": "Nasi", "category": "Food", "amount": 30_000},
    {"kind": "income", "date": "2026-08-05", "time": "09:00:00", "name": "Gaji", "category": "Income", "amount": 500_000},
    {"kind": "expense", "date": "2026-07-16", "time": "12:00:00", "name": "Lama", "category": "Other", "amount": 100_000},
    {"kind": "expense", "date": "invalid", "time": "12:00:00", "name": "Rusak", "category": "Other", "amount": 999_000},
]


class FakeDB:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.user_id = None

    def get_finance_snapshot(self, user_id):
        self.user_id = user_id
        return self.snapshot

    def add_transactions_bulk(self, *_args, **_kwargs):
        raise AssertionError("roast must not write expenses")

    def add_income(self, *_args, **_kwargs):
        raise AssertionError("roast must not write income")


class FakeAI:
    def __init__(self, response="Dompetmu dijadikan mesin espresso: Kopi tiga kali, Rp75.000. Batasi satu kali minggu depan.", error=None):
        self.response = response
        self.error = error
        self.snapshots = []

    async def generate_roast(self, snapshot):
        self.snapshots.append(snapshot)
        if self.error:
            raise self.error
        return self.response


def make_update(text="roast", user_id=77):
    return SimpleNamespace(
        message=SimpleNamespace(text=text),
        effective_user=SimpleNamespace(id=user_id),
    )


class RoastServiceTest(unittest.IsolatedAsyncioTestCase):
    def test_setup_registers_start_help_and_roast_commands(self):
        class Application:
            def __init__(self):
                self.handlers = []

            def add_error_handler(self, _handler):
                pass

            def add_handler(self, handler):
                self.handlers.append(handler)

        async def callback(*_args, **_kwargs):
            pass

        application = Application()
        service = SimpleNamespace(
            start=callback,
            help=callback,
            roast=callback,
            handle_button=callback,
            handle_message=callback,
        )
        old_admin_id = Config.ADMIN_ID
        Config.ADMIN_ID = "77"
        try:
            setup_handlers(application, service)
        finally:
            Config.ADMIN_ID = old_admin_id

        commands = {
            command
            for handler in application.handlers
            for command in getattr(handler, "commands", set())
        }
        self.assertEqual({"start", "help", "roast"}, commands)

    def test_trigger_only_matches_a_leading_roast_keyword(self):
        self.assertTrue(RoastService.looks_like_roast("roast"))
        self.assertTrue(RoastService.looks_like_roast("/roast"))
        self.assertTrue(RoastService.looks_like_roast("Roast pengeluaran aku"))
        self.assertFalse(RoastService.looks_like_roast("fitur roast itu apa"))

    def test_summary_uses_only_the_last_thirty_days_and_deterministic_facts(self):
        summary = RoastService.summarize(LEDGER, date(2026, 8, 15))

        self.assertEqual(summary["period_start"], "2026-07-17")
        self.assertEqual(summary["period_end"], "2026-08-15")
        self.assertEqual(summary["total_expense"], 105_000)
        self.assertEqual(summary["total_income"], 500_000)
        self.assertEqual(summary["net_cashflow"], 395_000)
        self.assertEqual(summary["transaction_count"], 5)
        self.assertEqual(summary["expense_count"], 4)
        self.assertEqual(summary["top_category"], {"name": "Drink", "count": 3, "amount": 75_000})
        self.assertEqual(summary["top_item"], {"name": "Kopi", "count": 3, "amount": 75_000})
        self.assertEqual(len(summary["largest_expenses"]), 4)
        self.assertEqual(summary["largest_expenses"][0]["name"], "Nasi")
        self.assertNotIn("notes", str(summary))
        self.assertNotIn("location", str(summary))

    async def test_roast_reads_only_the_authenticated_users_snapshot(self):
        db = FakeDB({"rows": LEDGER, "truncated": False})
        ai = FakeAI()
        replies = []

        async def reply(_message, text, **_kwargs):
            replies.append(text)

        service = RoastService(ai, db, reply, today=lambda: date(2026, 8, 15))

        self.assertTrue(await service.try_handle(make_update()))
        self.assertEqual(db.user_id, "77")
        self.assertEqual(len(ai.snapshots), 1)
        self.assertEqual(replies, [ai.response])
        self.assertEqual(ai.snapshots[0]["top_item"]["name"], "Kopi")

    async def test_empty_or_income_only_snapshot_skips_the_model(self):
        for rows in ([], [LEDGER[4]]):
            with self.subTest(rows=rows):
                ai = FakeAI(error=AssertionError("AI must not run"))
                replies = []

                async def reply(_message, text, **_kwargs):
                    replies.append(text)

                service = RoastService(
                    ai,
                    FakeDB({"rows": rows, "truncated": False}),
                    reply,
                    today=lambda: date(2026, 8, 15),
                )
                self.assertTrue(await service.try_handle(make_update()))
                self.assertEqual(ai.snapshots, [])
                self.assertIn("Belum ada transaksi", replies[0])

    async def test_database_failure_has_a_specific_message(self):
        replies = []

        async def reply(_message, text, **_kwargs):
            replies.append(text)

        service = RoastService(FakeAI(), FakeDB(None), reply)

        self.assertTrue(await service.try_handle(make_update()))
        self.assertEqual(replies, ["Data keuangan belum dapat dibaca. Coba roast lagi nanti."])

    async def test_provider_failure_uses_a_deterministic_actionable_fallback(self):
        replies = []

        async def reply(_message, text, **_kwargs):
            replies.append(text)

        service = RoastService(
            FakeAI(error=RuntimeError("provider down")),
            FakeDB({"rows": LEDGER, "truncated": False}),
            reply,
            today=lambda: date(2026, 8, 15),
        )

        self.assertTrue(await service.try_handle(make_update()))
        self.assertIn("Rp105.000", replies[0])
        self.assertIn("Kopi", replies[0])
        self.assertIn("Batasi", replies[0])

    async def test_unsupported_provider_claim_uses_the_factual_fallback(self):
        replies = []

        async def reply(_message, text, **_kwargs):
            replies.append(text)

        service = RoastService(
            FakeAI(response="Kamu tidak punya tujuan hidup dan cuma menghamburkan uang."),
            FakeDB({"rows": LEDGER, "truncated": False}),
            reply,
            today=lambda: date(2026, 8, 15),
        )

        self.assertTrue(await service.try_handle(make_update()))
        self.assertIn("AI roast sedang tidak tersedia", replies[0])
        self.assertIn("Rp105.000", replies[0])
        self.assertNotIn("tujuan hidup", replies[0])

    async def test_ai_receives_only_bounded_facts_and_limits_output(self):
        class Completions:
            def __init__(self):
                self.calls = []

            async def create(self, **kwargs):
                self.calls.append(kwargs)
                return SimpleNamespace(choices=[SimpleNamespace(
                    message=SimpleNamespace(content="x" * 1_000)
                )])

        completions = Completions()
        ai = object.__new__(AIService)
        ai.client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        summary = RoastService.summarize(LEDGER, date(2026, 8, 15))

        result = await ai.generate_roast(summary)
        prompt = completions.calls[0]["messages"][0]["content"]

        self.assertEqual(len(result), 900)
        self.assertIn("Attack spending decisions, never the person's worth", prompt)
        self.assertIn("Never invent facts", prompt)
        self.assertIn("Do not infer goals, motives, addiction, wealth, or discipline", prompt)
        self.assertIn("Format every money amount as Rp", prompt)
        self.assertIn('"top_item": {"name": "Kopi"', prompt)
        self.assertNotIn("private", prompt)
        self.assertNotIn("Cafe", prompt)


if __name__ == "__main__":
    unittest.main()
