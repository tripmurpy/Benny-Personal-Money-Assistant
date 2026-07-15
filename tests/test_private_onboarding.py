import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from config import Config
from services import auth_service
from services.telegram_service import TelegramService


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

    async def test_start_whitelist_and_exact_main_menu(self):
        service = TelegramService.__new__(TelegramService)
        allowed = make_update(12345)
        denied = make_update(99999)

        await service.start(allowed, SimpleNamespace())
        await service.start(denied, SimpleNamespace())

        self.assertTrue(auth_service.is_allowed(12345))
        self.assertFalse(auth_service.is_allowed(99999))
        self.assertEqual(len(allowed.message.replies), 1)
        self.assertEqual(denied.message.replies, [])
        keyboard = allowed.message.replies[0][1]["reply_markup"].keyboard
        self.assertEqual(
            [button.text for row in keyboard for button in row],
            ["Ringkasan", "Riwayat", "Budget", "Goals"],
        )

    async def test_allowed_message_needs_no_chat_login(self):
        service = TelegramService.__new__(TelegramService)
        service.db = Mock()
        service.handle_summary = AsyncMock()
        update = make_update(12345, "Ringkasan")

        await service.handle_message(update, SimpleNamespace())

        service.db.upsert_user.assert_called_once()
        service.handle_summary.assert_awaited_once()

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
