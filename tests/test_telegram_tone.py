import unittest

from services.telegram.bot import _calm_text, _edit_message_text, _reply_text


class FakeTelegramTarget:
    def __init__(self):
        self.call = None

    async def reply_text(self, *args, **kwargs):
        self.call = (args, kwargs)
        return "reply-result"

    async def edit_message_text(self, *args, **kwargs):
        self.call = (args, kwargs)
        return "edit-result"


class TelegramToneTest(unittest.IsolatedAsyncioTestCase):
    def test_calm_text_removes_decorative_emoji_and_repairs_mojibake(self):
        self.assertEqual(_calm_text("✅ **Tersimpan** 💙"), "**Tersimpan**")
        self.assertEqual(_calm_text("Selesai âœ…"), "Selesai")

    async def test_boundary_preserves_telegram_options(self):
        target = FakeTelegramTarget()
        markup = object()

        result = await _reply_text(
            target,
            "📊 Ringkasan siap",
            parse_mode="Markdown",
            reply_markup=markup,
        )

        self.assertEqual(result, "reply-result")
        self.assertEqual(target.call[0], ("Ringkasan siap",))
        self.assertEqual(
            target.call[1],
            {"parse_mode": "Markdown", "reply_markup": markup},
        )

        result = await _edit_message_text(
            target,
            chat_id=7,
            message_id=9,
            text="⏳ Memproses...",
        )

        self.assertEqual(result, "edit-result")
        self.assertEqual(
            target.call,
            ((), {"chat_id": 7, "message_id": 9, "text": "Memproses..."}),
        )


if __name__ == "__main__":
    unittest.main()
