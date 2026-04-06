"""
Auth Service — Login & Onboarding State Machine for Benny Bot.

Flow:
    /start
      → Welcome → WAITING_USERNAME
      → WAITING_PASSWORD (verify bcrypt)
        ├─ Fail (max 3x) → Locked
        └─ Pass
            ├─ New User  → ONBOARDING_NAME → ONBOARDING_NICKNAME → ONBOARDING_BIRTHDAY → DONE
            └─ Has Profile → PROFILE_REVIEW → (Ya: ONBOARDING_NAME) | (Tidak: DONE)
"""

import bcrypt
import logging
from config import Config

logger = logging.getLogger(__name__)

# ─── States ────────────────────────────────────────────────────────────────────
STATE_WAITING_USERNAME   = "WAITING_USERNAME"
STATE_WAITING_PASSWORD   = "WAITING_PASSWORD"
STATE_AUTHENTICATED      = "AUTHENTICATED"
STATE_ONBOARDING_NAME    = "ONBOARDING_NAME"
STATE_ONBOARDING_NICKNAME = "ONBOARDING_NICKNAME"
STATE_ONBOARDING_BIRTHDAY = "ONBOARDING_BIRTHDAY"
STATE_PROFILE_REVIEW     = "PROFILE_REVIEW"

MAX_ATTEMPTS = 3


# ─── Credential Verification ──────────────────────────────────────────────────

def verify_credentials(username: str, password: str) -> bool:
    """Verify username + password against .env stored bcrypt hash."""
    stored_username = Config.BOT_USERNAME
    stored_hash = Config.BOT_PASSWORD_HASH

    if not stored_username or not stored_hash:
        logger.error("❌ BOT_USERNAME or BOT_PASSWORD_HASH not set in .env")
        return False

    if username.strip().lower() != stored_username.strip().lower():
        return False

    try:
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    except Exception as e:
        logger.error(f"❌ bcrypt verification failed: {e}")
        return False


# ─── State Helpers ────────────────────────────────────────────────────────────

def init_auth(user_data: dict):
    """Reset auth state for a fresh /start session."""
    user_data["auth_state"] = STATE_WAITING_USERNAME
    user_data["auth_attempts"] = 0
    user_data["auth_temp"] = {}   # temp storage during onboarding


def get_state(user_data: dict) -> str:
    return user_data.get("auth_state", STATE_WAITING_USERNAME)


def is_authenticated(user_data: dict) -> bool:
    return get_state(user_data) == STATE_AUTHENTICATED


def set_authenticated(user_data: dict):
    user_data["auth_state"] = STATE_AUTHENTICATED


# ─── Message Templates ────────────────────────────────────────────────────────

WELCOME_MSG = (
    "🔐 *Selamat Datang di Benny Bot!*\n\n"
    "Asisten keuangan pribadimu yang aman & terpercaya. 💙\n\n"
    "Untuk melindungi datamu, silakan login terlebih dahulu.\n\n"
    "👤 Masukkan *username* kamu:"
)

ASK_PASSWORD_MSG = "🔑 Masukkan *password* kamu:"

WRONG_CREDS_MSG = (
    "❌ Username atau password salah. *({attempt}/{max})*\n\n"
    "Coba lagi — masukkan username kamu:"
)

LOCKED_MSG = (
    "🚫 *Akses ditolak.*\n\n"
    "Terlalu banyak percobaan yang gagal.\n"
    "Ketik /start untuk mencoba kembali."
)

LOGIN_SUCCESS_NEW_MSG = (
    "✅ *Login berhasil!* Selamat datang!\n\n"
    "Sepertinya ini pertama kali kita ketemu! 😊\n"
    "Boleh kenalan dulu dong?\n\n"
    "📝 Siapa *nama lengkap* kamu?"
)

LOGIN_SUCCESS_RETURNING_MSG = (
    "✅ *Login berhasil!* Selamat datang kembali!\n\n"
    "📋 *Profil kamu saat ini:*\n"
    "👤 Nama: {full_name}\n"
    "😊 Panggilan: {nickname}\n"
    "🎂 Ulang tahun: {birthday}\n\n"
    "Mau update profil? Ketik *ya* atau *tidak*"
)

ASK_NICKNAME_MSG   = "😊 Hei *{name}*! Mau dipanggil siapa nih?"
ASK_BIRTHDAY_MSG   = "🎂 Okee *{nickname}*! Kapan kamu ulang tahun? (contoh: 14 Maret 2000)"
PROFILE_SAVED_MSG  = (
    "🎉 *Profil tersimpan!*\n\n"
    "👤 Nama: {full_name}\n"
    "😊 Panggilan: {nickname}\n"
    "🎂 Ulang tahun: {birthday}\n\n"
    "Selamat datang, *{nickname}*! Aku siap bantu keuanganmu! 💙💪"
)
