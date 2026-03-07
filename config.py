"""
Configuration - Optimized & Centralized
All bot settings, API keys, and personality configs in one place.
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


class Config:
    """Central configuration class."""
    
    # Telegram
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    ADMIN_ID = os.getenv("ADMIN_CHAT_ID")
    
    # AI Models
    GROQ_MODEL = "llama-3.1-8b-instant"
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
    
    # Supabase
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    
    # Google Sheets (legacy — kept for gradual migration)
    SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
    GOOGLE_CREDS_PATH = os.path.join(BASE_DIR, "creds.json")
    
    # Sheet Names
    SHEET_GOALS = "Goals"
    SHEET_BUDGETS = "Budgets"
    SHEET_USER_PROFILES = "UserProfiles"
    SHEET_CHAT_HISTORY = "ChatHistory"
    SHEET_USER_CONTEXT = "UserContext"
    SHEET_KNOWLEDGE_BASE = "KnowledgeBase"
    
    # Thresholds
    BUDGET_WARNING_THRESHOLD = 0.8
    INACTIVITY_HOURS = 24
    
    # Coaching Settings
    WEEKLY_REPORT_DAY = 6  # Sunday (0=Monday, 6=Sunday)
    WEEKLY_REPORT_HOUR = 18  # 6 PM
    COACHING_ENABLED = True
    
    # Export Settings
    PDF_EXPORT_ENABLED = True
    MAX_EXPORT_MONTHS = 12
    
    # Analytics Settings
    DASHBOARD_DEFAULT_DAYS = 30
    TREND_CHART_DAYS = 14
    
    # AI Personality (load from JSON if exists, else use default)
    @staticmethod
    def get_personality_config():
        """Load AI personality config."""
        config_path = BASE_DIR / "config" / "ai_personality.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "name": "Benny",
            "personality_type": "supportive_friend",
            "tone": "friendly_casual"
        }
    
    @staticmethod
    def get_memory_config():
        """Load memory config."""
        config_path = BASE_DIR / "config" / "memory_config.json"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "retention": {"conversation_history_days": 90},
            "behavior": {"auto_learn": True, "sentiment_tracking": True}
        }
    
    @classmethod
    def validate(cls):
        """Validate required config values."""
        errors = []
        
        if not cls.TELEGRAM_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN missing in .env")
        if not cls.GROQ_API_KEY:
            errors.append("GROQ_API_KEY missing in .env")
        if not cls.SUPABASE_URL:
            errors.append("SUPABASE_URL missing in .env")
        if not cls.SUPABASE_KEY:
            errors.append("SUPABASE_KEY missing in .env")
        
        if errors:
            raise ValueError("Configuration errors:\n- " + "\n- ".join(errors))
        
        return True


# Legacy support - will be deprecated
BOT_PERSONA = """
Kamu adalah asisten keuangan pribadi bernama 'Benny'.
Gunakan personality dari config/ai_personality.json.
"""

# Messages Templates
class Messages:
    """Message templates."""
    
    # Goals
    GOAL_CREATED = "✅ Target '{name}' berhasil dibuat! Target: Rp {amount:,}"
    GOAL_EXISTS = "⚠️ Target '{name}' sudah ada"
    GOAL_DELETED = "✅ Target '{name}' berhasil dihapus"
    
    # Budgets
    BUDGET_SET = "✅ Budget '{category}' di-set: Rp {amount:,}/bulan"
    BUDGET_WARNING = "⚠️ Budget '{category}' udah {percent}%! Sisa: Rp {remaining:,}"
    BUDGET_DELETED = "✅ Budget '{category}' berhasil dihapus"
    
    # Activity
    INACTIVITY_REMINDER = "👋 Halo! Sudah {hours}jam nih belum ada catatan.\nAda pengeluaran hari ini? 💰"


if __name__ == "__main__":
    try:
        Config.validate()
        print("✅ Configuration valid!")
        print(f"📱 Telegram: {Config.TELEGRAM_TOKEN[:10]}...")
        print(f"🤖 Groq Model: {Config.GROQ_MODEL}")
        print(f"🗄️ Supabase: {Config.SUPABASE_URL}")
    except Exception as e:
        print(f"❌ {e}")
        exit(1)