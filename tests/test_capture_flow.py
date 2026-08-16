import unittest
from types import SimpleNamespace

from services.ai.service import (
    AIService,
    ReceiptProcessingError,
    TextProcessingError,
    VoiceProcessingError,
)
from services.transactions.capture import TransactionCaptureController


class FakeBot:
    def __init__(self):
        self.edits = []

    async def edit_message_text(self, **kwargs):
        self.edits.append(kwargs)

    async def get_file(self, _file_id):
        return SimpleNamespace(
            download_to_memory=self._download_to_memory
        )

    async def _download_to_memory(self, target):
        target.write(b"receipt-image")


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


async def edit_message_text(target, *args, **kwargs):
    return await target.edit_message_text(*args, **kwargs)


class CaptureFlowTest(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def service(result):
        return TransactionCaptureController(
            None, FakeDatabase(result), None, edit_message_text
        )

    async def test_receipt_requires_confirmed_record_and_uses_idempotency_key(self):
        service = self.service({"ok": True, "records": [{"id": 4}], "error": None})
        context = SimpleNamespace(bot=FakeBot(), user_data={})

        await service.save_and_reply(
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
        service = self.service(
            {"ok": False, "records": [], "error": "write_not_confirmed"}
        )
        context = SimpleNamespace(bot=FakeBot(), user_data={})

        await service.save_and_reply(
            make_update(),
            context,
            [{"item": "Kopi", "amount": 25_000, "category": "Food"}],
            99,
            "7:10",
        )

        self.assertTrue(context.bot.edits[-1]["text"].startswith("Belum tersimpan"))
        self.assertEqual(context.user_data["retry_capture"]["operation_id"], "7:10")

    async def test_mixed_income_expense_batch_is_rejected_before_write(self):
        service = self.service({"ok": True, "records": [{"id": 4}], "error": None})
        context = SimpleNamespace(bot=FakeBot(), user_data={})

        await service.save_and_reply(
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

    async def test_ocr_provider_failure_is_not_reported_as_missing_data(self):
        class FailingAI:
            async def parse_receipt_image(self, _data):
                raise ReceiptProcessingError("provider unavailable")

        async def reply_text(_message, _text):
            return SimpleNamespace(message_id=99)

        service = TransactionCaptureController(
            FailingAI(), FakeDatabase({}), reply_text, edit_message_text
        )
        update = make_update()
        update.message.photo = [SimpleNamespace(file_id="photo")]
        update.message.document = None
        context = SimpleNamespace(bot=FakeBot(), user_data={})

        await service.handle_photo(update, context)

        self.assertIn("OCR sedang tidak tersedia", context.bot.edits[-1]["text"])
        self.assertNotIn("tidak ditemukan", context.bot.edits[-1]["text"])

    def test_receipt_output_rejects_invalid_money_and_category(self):
        rows = AIService._valid_receipt_items({"items": [
            {"item": "Kopi", "amount": "32000", "category": "Drink"},
            {"item": "Invalid", "amount": 0, "category": "Food/Drink"},
        ]})

        self.assertEqual(rows, [{"item": "Kopi", "amount": 32000, "category": "Drink"}])

    async def test_pending_confirmation_cannot_be_overwritten_by_new_input(self):
        replies = []

        async def reply_text(_message, text, **_kwargs):
            replies.append(text)

        service = TransactionCaptureController(
            None, FakeDatabase({}), reply_text, edit_message_text
        )
        pending = {
            "transactions": [{"item": "Kopi", "amount": 25_000}],
            "operation_id": "7:9",
        }
        context = SimpleNamespace(bot=FakeBot(), user_data={"pending_confirmation": pending})

        await service.handle(make_update(), context)

        self.assertIs(context.user_data["pending_confirmation"], pending)
        self.assertIn("menunggu konfirmasi", replies[0])

    async def test_stale_confirmation_button_cannot_save_current_state(self):
        class Query:
            data = "confirm_save_yes:7:old"
            message = SimpleNamespace(message_id=99)

            def __init__(self):
                self.edits = []

            async def answer(self):
                pass

            async def edit_message_text(self, text, **_kwargs):
                self.edits.append(text)

        service = self.service({"ok": True, "records": [{"id": 4}], "error": None})
        query = Query()
        update = SimpleNamespace(
            callback_query=query,
            effective_user=SimpleNamespace(id=7),
        )
        pending = {
            "transactions": [{"item": "Kopi", "amount": 25_000}],
            "operation_id": "7:new",
        }
        context = SimpleNamespace(user_data={"pending_confirmation": pending})

        await service.handle_callback(update, context)

        self.assertEqual(service.db.calls, [])
        self.assertIs(context.user_data["pending_confirmation"], pending)
        self.assertIn("kedaluwarsa", query.edits[-1])

    async def test_text_has_separate_conversation_clarification_and_provider_fallbacks(self):
        class FakeAI:
            def __init__(self, result=None, error=None):
                self.result, self.error = result, error

            async def interpret_message(self, _text):
                if self.error:
                    raise self.error
                return self.result

        async def reply_text(_message, _text):
            return SimpleNamespace(message_id=99)

        update = make_update()
        update.message.text = "halo"
        update.message.photo = None
        update.message.document = None
        update.message.voice = None

        cases = [
            ({"intent": "conversation", "reply": "Halo, aku siap bantu.", "items": []}, "siap bantu"),
            ({"intent": "clarification", "clarification": "Nominalnya berapa?", "items": []}, "Nominalnya"),
            (None, "sedang tidak tersedia"),
        ]
        for result, expected in cases:
            error = TextProcessingError("provider_failed") if result is None else None
            service = TransactionCaptureController(
                FakeAI(result, error), FakeDatabase({}), reply_text, edit_message_text
            )
            context = SimpleNamespace(bot=FakeBot(), user_data={})
            await service.handle_text(update, context)
            self.assertIn(expected, context.bot.edits[-1]["text"])

    async def test_ocr_and_voice_artifacts_are_shown_before_save(self):
        class FakeAI:
            async def parse_receipt_image(self, _data):
                return {
                    "status": "low_confidence",
                    "raw_text": "TOKO TEST\nTOTAL 25000",
                    "items": [{"item": "Kopi", "amount": 25_000, "category": "Drink"}],
                }

            async def transcribe_audio(self, _data):
                return {"status": "low_confidence", "text": "beli kopi dua puluh lima ribu"}

            async def interpret_message(self, _text):
                return {
                    "intent": "transaction",
                    "items": [{"item": "Kopi", "amount": 25_000, "category": "Drink"}],
                }

        async def reply_text(_message, _text):
            return SimpleNamespace(message_id=99)

        service = TransactionCaptureController(
            FakeAI(), FakeDatabase({}), reply_text, edit_message_text
        )
        update = make_update()
        update.message.photo = [SimpleNamespace(file_id="photo")]
        update.message.document = None
        update.message.voice = None
        context = SimpleNamespace(bot=FakeBot(), user_data={})

        await service.handle_photo(update, context)
        self.assertIn("Teks terbaca", context.bot.edits[-1]["text"])
        self.assertIn("Perlu dicek", context.bot.edits[-1]["text"])

        context.user_data.clear()
        update.message.photo = None
        update.message.voice = SimpleNamespace(file_id="voice")
        await service.handle_voice(update, context)
        self.assertIn("Transkrip", context.bot.edits[-1]["text"])
        self.assertIn("beli kopi", context.bot.edits[-1]["text"])

    async def test_empty_and_provider_failed_voice_are_distinct(self):
        class FakeAI:
            def __init__(self, error=False):
                self.error = error

            async def transcribe_audio(self, _data):
                if self.error:
                    raise VoiceProcessingError("provider_failed")
                return {"status": "transcribed", "text": ""}

        async def reply_text(_message, _text):
            return SimpleNamespace(message_id=99)

        update = make_update()
        update.message.voice = SimpleNamespace(file_id="voice")
        context = SimpleNamespace(bot=FakeBot(), user_data={})
        service = TransactionCaptureController(
            FakeAI(), FakeDatabase({}), reply_text, edit_message_text
        )
        await service.handle_voice(update, context)
        self.assertIn("tidak dapat dikenali", context.bot.edits[-1]["text"])

        service.ai = FakeAI(error=True)
        await service.handle_voice(update, context)
        self.assertIn("sedang tidak tersedia", context.bot.edits[-1]["text"])

    async def test_voice_without_provider_confidence_requires_review(self):
        class Transcriptions:
            async def create(self, **_kwargs):
                return SimpleNamespace(text="beli kopi dua puluh lima ribu", segments=[])

        ai = object.__new__(AIService)
        ai.client = SimpleNamespace(audio=SimpleNamespace(transcriptions=Transcriptions()))

        result = await ai.transcribe_audio(b"RIFF-test-audio")

        self.assertEqual(result["status"], "low_confidence")
        self.assertIsNone(result["confidence"])


if __name__ == "__main__":
    unittest.main()
