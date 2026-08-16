import base64
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from services.gmail.ingestion import GmailTransactionIngestion


class GmailIngestionTest(unittest.TestCase):
    def test_body_reads_plain_text_without_html_or_attachments(self):
        source = b"Subject: BCA transaksi\r\nFrom: bank@example.com\r\nContent-Type: text/plain\r\n\r\nRp 25.000"
        raw = base64.urlsafe_b64encode(source).decode().rstrip("=")
        body = GmailTransactionIngestion._body({"raw": raw})
        self.assertEqual(body["subject"], "BCA transaksi")
        self.assertEqual(body["body"], "Rp 25.000")

    def test_body_extracts_text_from_html_only_provider_email(self):
        source = (
            b"Subject: Transaksi\r\nFrom: bca@bca.co.id\r\n"
            b"Content-Type: text/html; charset=utf-8\r\n\r\n"
            b"<html><body><p>Pembayaran Rp <b>25.000</b></p></body></html>"
        )
        raw = base64.urlsafe_b64encode(source).decode().rstrip("=")
        body = GmailTransactionIngestion._body({"raw": raw})
        self.assertEqual(body["body"], "Pembayaran Rp 25.000")

    def test_query_is_bounded_to_trusted_finance_senders(self):
        query = GmailTransactionIngestion.finance_query()
        self.assertIn("bca.co.id", query)
        self.assertIn("jago.com", query)
        self.assertIn("receipts@gotagihan.gojek.com", query)
        self.assertNotIn("marketing.go-jek.com", query)

    def test_fetch_limits_each_poll_to_two_emails(self):
        ingestion = GmailTransactionIngestion(SimpleNamespace(), SimpleNamespace())
        service = MagicMock()
        service.users.return_value.messages.return_value.list.return_value.execute.return_value = {
            "messages": []
        }
        ingestion._service = lambda: service

        self.assertEqual(ingestion._fetch(), [])
        service.users.return_value.messages.return_value.list.assert_called_once_with(
            userId="me", q=ingestion.finance_query(), maxResults=2
        )

    def test_legacy_saved_transaction_is_retried_once_for_notification(self):
        self.assertTrue(GmailTransactionIngestion._needs_processing("expense"))
        self.assertTrue(GmailTransactionIngestion._needs_processing("income"))
        self.assertFalse(GmailTransactionIngestion._needs_processing("expense:notified"))
        self.assertFalse(GmailTransactionIngestion._needs_processing("neither"))


class GmailClassificationFlowTest(unittest.IsolatedAsyncioTestCase):
    async def test_neither_is_skipped_and_not_reprocessed(self):
        class AI:
            async def parse_finance_email(self, _email):
                return {"transaction_type": "neither", "reason": "promo"}

        class DB:
            def add_income(self, *_args):
                self.called = True

            add_transactions_bulk = add_income

        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / "state.json"
            ingestion = GmailTransactionIngestion(AI(), DB(), state)
            ingestion._fetch = lambda: [("mail-1", {"subject": "Promo"})]
            await ingestion.sync(SimpleNamespace())
            self.assertEqual(json.loads(state.read_text()), {"mail-1": "neither"})

    async def test_classified_income_uses_existing_income_writer(self):
        class AI:
            async def parse_finance_email(self, _email):
                return {
                    "transaction_type": "income", "source": "Client",
                    "amount": 100_000, "date": "2026-08-12",
                }

        class DB:
            def upsert_user(self, _uid, _profile):
                self.profiled = True
                return True

            def add_income(self, _uid, rows, operation_id):
                assert self.profiled
                self.saved = (rows, operation_id)
                return {"ok": True, "records": [{}]}

            def add_transactions_bulk(self, *_args):
                raise AssertionError("income routed to expense writer")

        with tempfile.TemporaryDirectory() as folder:
            db = DB()
            ingestion = GmailTransactionIngestion(AI(), db, Path(folder) / "state.json")
            ingestion._fetch = lambda: [("mail-2", {"subject": "Dana masuk"})]
            await ingestion.sync(SimpleNamespace())
            self.assertEqual(db.saved[1], "gmail:mail-2")

    async def test_saved_old_transaction_sends_telegram_notification(self):
        class AI:
            async def parse_finance_email(self, _email):
                return {
                    "transaction_type": "expense", "item": "ChatGPT",
                    "amount": 349_000, "date": "2026-08-01", "time": "10:30",
                    "location": "OpenAI", "notes": "Langganan",
                }

        class DB:
            def upsert_user(self, *_args):
                return True

            def add_transactions_bulk(self, *_args):
                return {"ok": True, "records": [{}]}

        with tempfile.TemporaryDirectory() as folder:
            ingestion = GmailTransactionIngestion(AI(), DB(), Path(folder) / "state.json")
            ingestion._fetch = lambda: [("old-mail", {"subject": "Receipt"})]
            bot = SimpleNamespace(send_message=AsyncMock())
            await ingestion.sync(SimpleNamespace(bot=bot))

            bot.send_message.assert_awaited_once()
            text = bot.send_message.await_args.kwargs["text"]
            self.assertIn("Transaksi: ChatGPT", text)
            self.assertIn("Harga: Rp349.000", text)
            self.assertIn("Lokasi: OpenAI", text)
            self.assertEqual(ingestion.processed["old-mail"], "expense:notified")


if __name__ == "__main__":
    unittest.main()
