"""Small session context and user-controlled explicit memory."""

import hashlib
import re


class MemoryService:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def _text(row):
        value = row.get("preference_value", {})
        return str(value.get("text", "")).strip() if isinstance(value, dict) else ""

    @staticmethod
    def _key(text):
        normalized = " ".join(text.casefold().split())
        return f"memory.{hashlib.sha256(normalized.encode()).hexdigest()[:16]}"

    @staticmethod
    def _query(text):
        return re.sub(r"^(bahwa|aku|saya)\s+", "", text.strip(), flags=re.I).casefold()

    def context(self, user_id, chat_id):
        messages = self.db.get_recent_chat_messages(user_id, chat_id, 6)
        memories = [self._text(row) for row in self.db.get_explicit_memories(user_id)]
        return messages, [text for text in memories if text]

    def remember_exchange(self, user_id, chat_id, user_text, assistant_text, message_id=None):
        self.db.add_chat_message(user_id, chat_id, "user", user_text, message_id)
        self.db.add_chat_message(user_id, chat_id, "assistant", assistant_text)

    def handle_command(self, user_id, text):
        stripped = text.strip()
        lowered = stripped.casefold()
        if re.fullmatch(r"(?:/memory|ingat apa|apa yang kamu ingat(?: tentang aku)?|tunjukkan ingatan(?:ku)?)\??", lowered):
            memories = [self._text(row) for row in self.db.get_explicit_memories(user_id)]
            memories = [value for value in memories if value]
            if not memories:
                return "Aku belum menyimpan ingatan eksplisit tentangmu."
            return "Yang kamu minta aku ingat:\n" + "\n".join(
                f"{index}. {value}" for index, value in enumerate(memories, 1)
            )

        match = re.fullmatch(r"(?:ingat(?:lah)?|tolong ingat|/remember)(?: bahwa|:)?\s+(.+)", stripped, re.I)
        if match:
            value = match.group(1).strip()
            if len(value) < 2:
                return "Tulis hal yang ingin kamu minta aku ingat."
            saved = self.db.upsert_explicit_memory(user_id, self._key(value), value)
            return (
                f"Sudah kuingat: {value}"
                if saved else "Ingatan belum tersimpan karena database sedang bermasalah."
            )

        match = re.fullmatch(
            r"(?:ubah|ganti) ingatan(?: tentang)?\s+(.+?)\s+(?:menjadi|jadi)\s+(.+)",
            stripped, re.I,
        )
        if match:
            return self._update(user_id, match.group(1), match.group(2))

        match = re.fullmatch(r"(?:lupakan|jangan ingat|/forget)(?: bahwa|:)?\s+(.+)", stripped, re.I)
        if match:
            return self._forget(user_id, match.group(1))
        return None

    def _matches(self, user_id, query):
        needle = self._query(query)
        return [
            row for row in self.db.get_explicit_memories(user_id)
            if needle and needle in self._query(self._text(row))
        ]

    def _update(self, user_id, query, replacement):
        matches = self._matches(user_id, query)
        if not matches:
            return "Ingatan yang ingin diubah tidak ditemukan."
        if len(matches) > 1:
            return "Ada beberapa ingatan yang cocok. Sebutkan bagian yang lebih spesifik."
        replacement = replacement.strip()
        saved = self.db.upsert_explicit_memory(
            user_id, matches[0]["preference_key"], replacement
        )
        return (
            f"Ingatan diperbarui: {replacement}"
            if saved else "Ingatan belum diperbarui karena database sedang bermasalah."
        )

    def _forget(self, user_id, query):
        matches = self._matches(user_id, query)
        if not matches:
            return "Ingatan yang ingin dilupakan tidak ditemukan."
        if len(matches) > 1:
            return "Ada beberapa ingatan yang cocok. Sebutkan bagian yang lebih spesifik."
        forgotten = self.db.forget_explicit_memory(user_id, matches[0]["preference_key"])
        return (
            f"Sudah kulupakan: {self._text(matches[0])}"
            if forgotten else "Ingatan belum dihapus karena database sedang bermasalah."
        )
