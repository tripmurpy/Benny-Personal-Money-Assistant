import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from config import Config
from services.telegram import auth as auth_service
from services.telegram.bot import TelegramService


class DummyMessage:
    def __init__(self, text=None):
        self.text = text
        self.photo = None
        self.document = None
        self.voice = None
        self.reply_to_message = None
        self.replies = []

    async def reply_text(self, text, **kwargs):
        self.replies.append((text, kwargs))


def make_update(user_id, text=None):
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id, username="owner", first_name="Owner"),
        effective_chat=SimpleNamespace(id=user_id),
        message=DummyMessage(text),
    )


class PrivateOnboardingTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.original_admin_id = Config.ADMIN_ID
        Config.ADMIN_ID = "12345"

    def tearDown(self):
        Config.ADMIN_ID = self.original_admin_id

    async def test_start_whitelist_and_capture_only_welcome(self):
        service = TelegramService.__new__(TelegramService)
        allowed = make_update(12345)
        denied = make_update(99999)

        await service.start(allowed, SimpleNamespace())
        await service.start(denied, SimpleNamespace())

        self.assertTrue(auth_service.is_allowed(12345))
        self.assertFalse(auth_service.is_allowed(99999))
        self.assertEqual(len(allowed.message.replies), 1)
        self.assertEqual(denied.message.replies, [])
        self.assertNotIn("reply_markup", allowed.message.replies[0][1])
        self.assertIn("pemasukan", allowed.message.replies[0][0].lower())
        self.assertIn("pengeluaran", allowed.message.replies[0][0].lower())

    async def test_allowed_message_routes_only_to_capture_controller(self):
        service = TelegramService.__new__(TelegramService)
        service.db = Mock()
        service.capture = SimpleNamespace(handle=AsyncMock())
        service.reports = SimpleNamespace(try_handle=AsyncMock(return_value=False))
        update = make_update(12345, "makan 25 ribu")
        context = SimpleNamespace()

        await service.handle_message(update, context)

        service.db.upsert_user.assert_called_once()
        service.reports.try_handle.assert_awaited_once_with(update)
        service.capture.handle.assert_awaited_once_with(update, context)

    async def test_memory_command_routes_before_report_and_capture(self):
        service = TelegramService.__new__(TelegramService)
        service.db = Mock()
        service.memory = SimpleNamespace(handle_command=Mock(return_value="Sudah kuingat"))
        service.capture = SimpleNamespace(handle=AsyncMock())
        service.reports = SimpleNamespace(try_handle=AsyncMock(return_value=False))
        update = make_update(12345, "ingat aku suka teh")

        await service.handle_message(update, SimpleNamespace())

        self.assertEqual(update.message.replies[0][0], "Sudah kuingat")
        service.reports.try_handle.assert_not_awaited()
        service.capture.handle.assert_not_awaited()

    async def test_plain_roast_routes_before_report_sql_and_capture(self):
        service = TelegramService.__new__(TelegramService)
        service.db = Mock()
        service.memory = SimpleNamespace(handle_command=Mock(return_value=None))
        service.roasts = SimpleNamespace(try_handle=AsyncMock(return_value=True))
        service.reports = SimpleNamespace(try_handle=AsyncMock(return_value=False))
        service.sql_assistant = SimpleNamespace(try_handle=AsyncMock(return_value=False))
        service.capture = SimpleNamespace(handle=AsyncMock())
        update = make_update(12345, "roast pengeluaran aku")

        await service.handle_message(update, SimpleNamespace())

        service.roasts.try_handle.assert_awaited_once_with(update)
        service.reports.try_handle.assert_not_awaited()
        service.sql_assistant.try_handle.assert_not_awaited()
        service.capture.handle.assert_not_awaited()

    async def test_help_lists_only_active_features(self):
        service = TelegramService.__new__(TelegramService)
        allowed = make_update(12345)
        denied = make_update(99999)

        await service.help(allowed, SimpleNamespace())
        await service.help(denied, SimpleNamespace())

        text = allowed.message.replies[0][0].lower()
        self.assertIn("/roast", text)
        self.assertIn("foto struk", text)
        self.assertIn("ingat", text)
        self.assertNotIn("budget", text)
        self.assertNotIn("reminder", text)
        self.assertEqual(denied.message.replies, [])

    def test_tracked_config_has_no_chat_credentials_or_secret_fallback(self):
        source = (Path(__file__).parents[1] / "config" / "__init__.py").read_text(encoding="utf-8")

        self.assertNotIn("BOT_USERNAME", source)
        self.assertNotIn("BOT_PASSWORD_HASH", source)
        self.assertIsNone(re.search(r'OPENROUTER_API_KEY\s*=\s*os\.getenv\([^\n]+,', source))

    def test_invalid_admin_id_fails_closed(self):
        Config.ADMIN_ID = "not-a-telegram-id"
        with self.assertRaises(ValueError):
            Config.validate()


if __name__ == "__main__":
    unittest.main()
