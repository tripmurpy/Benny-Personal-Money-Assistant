"""Private single-user access for Benny Bot."""

from config import Config


def is_allowed(user_id) -> bool:
    """Allow only the configured Telegram administrator."""
    return bool(Config.ADMIN_ID) and str(user_id) == str(Config.ADMIN_ID)
