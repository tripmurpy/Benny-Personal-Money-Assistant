"""
Chat Service - Warm Conversational Handler

Hybrid approach: Pattern-based templates (instant) + AI fallback (Groq).
Makes Benny feel like a real friend, not a cold robot.
"""

import json
import random
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent


class ChatService:
    """
    Hybrid chat handler with 2 layers:
    - Layer 1: Pattern matching against chat_templates.json (instant)
    - Layer 2: AI fallback via Groq for open-ended chat
    """

    def __init__(self):
        """Load chat templates from JSON file."""
        self.templates = {}
        self._load_templates()

    def _load_templates(self):
        """Load and parse chat_templates.json."""
        templates_path = BASE_DIR / "config" / "chat_templates.json"
        try:
            with open(templates_path, 'r', encoding='utf-8') as f:
                self.templates = json.load(f)
            logger.info(f"✅ Chat templates loaded: {len(self.templates)} categories")
        except FileNotFoundError:
            logger.warning("⚠️ chat_templates.json not found, pattern matching disabled")
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid chat_templates.json: {e}")

    def match_template(self, text: str) -> Optional[str]:
        """
        Layer 1: Match user input against keyword patterns.

        Args:
            text: User's message text

        Returns:
            Random response from matching category, or None if no match
        """
        text_lower = text.lower().strip()

        # Try each category
        for category, data in self.templates.items():
            patterns = data.get("patterns", [])
            responses = data.get("responses", [])

            if not patterns or not responses:
                continue

            for pattern in patterns:
                pattern_lower = pattern.lower()

                # Match strategies:
                # 1. Exact match (for short patterns like "hi", "p")
                # 2. Pattern appears as whole word in text
                # 3. Text starts with pattern
                if (text_lower == pattern_lower or
                    pattern_lower in text_lower.split() or
                    text_lower.startswith(pattern_lower)):
                    return random.choice(responses)

        return None

    async def handle_chat(self, text: str, ai_service) -> str:
        """
        Main handler: Try pattern match first, then AI fallback.

        Args:
            text: User's message text
            ai_service: AIService instance for Groq fallback

        Returns:
            Warm, friendly response
        """
        # Layer 1: Pattern match (instant, no API call)
        template_response = self.match_template(text)
        if template_response:
            return template_response

        # Layer 2: AI fallback (Groq chat)
        try:
            ai_response = await ai_service.chat_with_user(text)
            if ai_response:
                return ai_response
        except Exception as e:
            logger.error(f"AI chat fallback failed: {e}")

        # Ultimate fallback (should rarely happen)
        return (
            "Halo! 💙 Maaf, aku lagi sedikit bingung nih.\n\n"
            "Kalau mau catat transaksi, coba format kayak gini:\n"
            "📝 \"Beli makan 50rb di Warteg\"\n\n"
            "Atau tap menu di bawah ya! 👇"
        )


# Singleton
_chat_service = None


def get_chat_service() -> ChatService:
    """Get singleton ChatService instance."""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
