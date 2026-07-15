import unittest
from types import SimpleNamespace

from services.telegram_service import TelegramService


class FakeBot:
    def __init__(self):
        self.edits = []

    async def edit_message_text(self, **kwargs):
        self.edits.append(kwargs)


class FakeDatabase:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def add_transactions_bulk(self, user_id, transactions, operation_id):
        self.calls.append(("expense", user_id, transactions, operation_id))
        return self.result

    def add_income(self, user_id, transactions, operation_id):
        self.calls.append(("income", user_id, transactions, operation_id))
        return self.result


def make_update():
    message = SimpleNamespace(message_id=10)
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=7),
        effective_chat=SimpleNamespace(id=7),
        effective_message=message,
        message=message,
    )


class CaptureFlowTest(unittest.IsolatedAsyncioTestCase):
    async def test_receipt_requires_confirmed_record_and_uses_idempotency_key(self):
        service = TelegramService.__new__(TelegramService)
        service.db = FakeDatabase({"ok": True, "records": [{"id": 4}], "error": None})
        context = SimpleNamespace(bot=FakeBot(), user_data={})

        await service._save_and_reply(
            make_update(),
            context,
            [{"item": "Kopi", "amount": 25_000, "category": "Food"}],
            99,
            "7:10",
        )

        self.assertEqual(service.db.calls[0][3], "7:10")
        self.assertTrue(context.bot.edits[-1]["text"].startswith("Tersimpan"))
        callbacks = [
            button.callback_data
            for row in context.bot.edits[-1]["reply_markup"].inline_keyboard
            for button in row
        ]
        self.assertEqual(callbacks, ["undo_capture:e:7:10", "edit_capture:e:4"])

    async def test_unconfirmed_write_is_never_reported_as_success(self):
        service = TelegramService.__new__(TelegramService)
        service.db = FakeDatabase(
            {"ok": False, "records": [], "error": "write_not_confirmed"}
        )
        context = SimpleNamespace(bot=FakeBot(), user_data={})

        await service._save_and_reply(
            make_update(),
            context,
            [{"item": "Kopi", "amount": 25_000, "category": "Food"}],
            99,
            "7:10",
        )

        self.assertTrue(context.bot.edits[-1]["text"].startswith("Belum tersimpan"))
        self.assertEqual(context.user_data["retry_capture"]["operation_id"], "7:10")

    async def test_mixed_income_expense_batch_is_rejected_before_write(self):
        service = TelegramService.__new__(TelegramService)
        service.db = FakeDatabase({"ok": True, "records": [{"id": 4}], "error": None})
        context = SimpleNamespace(bot=FakeBot(), user_data={})

        await service._save_and_reply(
            make_update(),
            context,
            [
                {"item": "Gaji", "amount": 1_000_000, "category": "Income"},
                {"item": "Kopi", "amount": 25_000, "category": "Food"},
            ],
            99,
            "7:10",
        )

        self.assertEqual(service.db.calls, [])
        self.assertTrue(context.bot.edits[-1]["text"].startswith("Belum tersimpan"))


if __name__ == "__main__":
    unittest.main()
