"""
Configuration - Optimized & Centralized
All bot settings, API keys, and personality configs in one place.
"""

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Central configuration class."""

    # Telegram
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    ADMIN_ID = os.getenv("ADMIN_CHAT_ID")

    # AI Models
    GROQ_MODEL = "llama-3.1-8b-instant"
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-20b:free")
    AI_TIMEOUT_SECONDS = max(1.0, float(os.getenv("AI_TIMEOUT_SECONDS", "30")))
    AI_MAX_RETRIES = max(0, min(3, int(os.getenv("AI_MAX_RETRIES", "1"))))

    # Supabase
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

    GMAIL_ENABLED = os.getenv("GMAIL_ENABLED", "true").lower() == "true"
    GMAIL_CREDENTIALS_FILE = os.getenv("GMAIL_CREDENTIALS_FILE", "credintial.json")
    GMAIL_TOKEN_FILE = os.getenv("GMAIL_TOKEN_FILE", "gmail-token.json")
    GMAIL_POLL_SECONDS = max(30, int(os.getenv("GMAIL_POLL_SECONDS", "30")))
    GMAIL_FINANCE_QUERY = os.getenv(
        "GMAIL_FINANCE_QUERY",
        "newer_than:2m {"
        "from:(bca.co.id) from:(jago.com) from:(gopay.co.id) "
        "from:(receipts@gotagihan.gojek.com) "
        "from:(payments-noreply@google.com) "
        "from:(googlepayments-noreply@google.com) "
        "from:(googleplay-noreply@google.com)}",
    )

    @classmethod
    def validate(cls):
        """Validate required config values."""
        errors = []

        if not cls.TELEGRAM_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN missing in .env")
        if not cls.ADMIN_ID:
            errors.append("ADMIN_CHAT_ID missing in .env")
        elif not str(cls.ADMIN_ID).isdigit():
            errors.append("ADMIN_CHAT_ID must be numeric")
        if not cls.GROQ_API_KEY:
            errors.append("GROQ_API_KEY missing in .env")
        if not cls.SUPABASE_URL:
            errors.append("SUPABASE_URL missing in .env")
        if not cls.SUPABASE_KEY:
            errors.append("SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY missing in .env")

        if errors:
            raise ValueError("Configuration errors:\n- " + "\n- ".join(errors))

        return True
