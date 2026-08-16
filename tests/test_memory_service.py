import unittest

from services.memory.service import MemoryService


class FakeDatabase:
    def __init__(self):
        self.memories = {}
        self.messages = []

    def get_explicit_memories(self, _user_id):
        return [
            {"preference_key": key, "preference_value": {"text": value}}
            for key, value in self.memories.items() if value is not None
        ]

    def upsert_explicit_memory(self, _user_id, key, text):
        self.memories[key] = text
        return True

    def forget_explicit_memory(self, _user_id, key):
        self.memories[key] = None
        return True

    def add_chat_message(self, user_id, chat_id, role, content, message_id=None):
        self.messages.append({
            "user_id": user_id, "chat_id": chat_id, "role": role,
            "content": content, "message_id": message_id,
        })
        return True

    def get_recent_chat_messages(self, _user_id, _chat_id, limit):
        return self.messages[-limit:]


class MemoryServiceTest(unittest.TestCase):
    def setUp(self):
        self.db = FakeDatabase()
        self.memory = MemoryService(self.db)

    def test_remember_show_update_forget_lifecycle(self):
        self.assertEqual(
            self.memory.handle_command("7", "ingat bahwa aku suka kopi tanpa gula"),
            "Sudah kuingat: aku suka kopi tanpa gula",
        )
        shown = self.memory.handle_command("7", "apa yang kamu ingat tentang aku?")
        self.assertIn("aku suka kopi tanpa gula", shown)

        updated = self.memory.handle_command(
            "7", "ubah ingatan kopi tanpa gula menjadi aku suka teh tawar"
        )
        self.assertEqual(updated, "Ingatan diperbarui: aku suka teh tawar")
        self.assertIn("aku suka teh tawar", self.memory.handle_command("7", "/memory"))

        forgotten = self.memory.handle_command("7", "lupakan teh tawar")
        self.assertEqual(forgotten, "Sudah kulupakan: aku suka teh tawar")
        self.assertIn("belum menyimpan", self.memory.handle_command("7", "ingat apa"))

    def test_update_and_forget_refuse_ambiguous_match(self):
        self.memory.handle_command("7", "ingat aku suka kopi susu")
        self.memory.handle_command("7", "ingat aku suka kopi hitam")

        self.assertIn("beberapa", self.memory.handle_command("7", "lupakan kopi"))
        self.assertIn(
            "beberapa",
            self.memory.handle_command("7", "ubah ingatan kopi menjadi teh"),
        )
        self.assertEqual(len([value for value in self.db.memories.values() if value]), 2)

    def test_session_context_is_bounded_and_separate_from_explicit_memory(self):
        for index in range(4):
            self.memory.remember_exchange("7", "7", f"user {index}", f"bot {index}", index)
        self.memory.handle_command("7", "ingat namaku Benny")

        messages, explicit = self.memory.context("7", "7")

        self.assertEqual(len(messages), 6)
        self.assertEqual(messages[0]["content"], "user 1")
        self.assertEqual(explicit, ["namaku Benny"])


if __name__ == "__main__":
    unittest.main()
