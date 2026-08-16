"""Thin Telegram adapter for AI income and expense capture."""

import asyncio
import logging
import unicodedata

from telegram.ext import ContextTypes

from services.ai.service import AIService
from services.infrastructure.database import SupabaseService
from services.memory.service import MemoryService
from services.reporting.roast import RoastService
from services.reporting.service import ExpenseReportService
from services.reporting.sql_assistant import FinanceSqlAssistant
from services.telegram import auth as auth_svc
from services.transactions.capture import TransactionCaptureController

logger = logging.getLogger(__name__)

HELP_TEXT = """Aku bisa bantu:

- Catat transaksi: makan 25 ribu atau gaji 5 juta.
- Baca foto struk dan voice note, lalu minta konfirmasi sebelum menyimpan.
- Cek laporan atau analitik: pengeluaran 7 hari terakhir atau kategori paling boros.
- Kelola ingatan: ingat jawab singkat, ingat apa, ubah ingatan, atau lupakan.
- Roast pengeluaran 30 hari terakhir: roast atau /roast."""


def _calm_text(text: str) -> str:
    """Repair common mojibake and remove decorative emoji at the Telegram boundary."""
    if any(marker in text for marker in ("Ã", "Â", "â", "ð")):
        try:
            text = text.encode("cp1252").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return "".join(
        char for char in text
        if char not in {"\ufe0f", "\u200d", "\u20e3"}
        and unicodedata.category(char) not in {"So", "Sk"}
    ).strip()


def _calm_call(args, kwargs):
    kwargs = kwargs.copy()
    if args:
        return (_calm_text(args[0]), *args[1:]), kwargs
    kwargs["text"] = _calm_text(kwargs["text"])
    return args, kwargs


async def _reply_text(message, *args, **kwargs):
    args, kwargs = _calm_call(args, kwargs)
    return await message.reply_text(*args, **kwargs)


async def _edit_message_text(target, *args, **kwargs):
    args, kwargs = _calm_call(args, kwargs)
    return await target.edit_message_text(*args, **kwargs)


class TelegramService:
    """Authenticate Telegram updates and delegate transaction capture."""

    def __init__(self):
        self.db = SupabaseService()
        ai = AIService()
        self.memory = MemoryService(self.db)
        self.capture = TransactionCaptureController(
            ai, self.db, _reply_text, _edit_message_text, self.memory
        )
        self.reports = ExpenseReportService(ai, self.db, _reply_text)
        self.sql_assistant = FinanceSqlAssistant(ai, self.db, _reply_text)
        self.roasts = RoastService(ai, self.db, _reply_text)

    async def start(self, update, context: ContextTypes.DEFAULT_TYPE):
        if not auth_svc.is_allowed(update.effective_user.id):
            return
        await _reply_text(
            update.message,
            "Halo, aku Benny. Aku bisa bantu mencatat pemasukan dan pengeluaran "
            "lewat teks, foto struk, atau voice note. Semua transaksi akan aku minta cek dulu.",
        )

    async def handle_message(self, update, context: ContextTypes.DEFAULT_TYPE):
        if not auth_svc.is_allowed(update.effective_user.id):
            return
        await asyncio.to_thread(
            self.db.upsert_user,
            str(update.effective_user.id),
            {
                "username": update.effective_user.username or "",
                "first_name": update.effective_user.first_name or "",
            },
        )
        memory = getattr(self, "memory", None)
        if memory and update.message.text:
            memory_reply = await asyncio.to_thread(
                memory.handle_command, str(update.effective_user.id), update.message.text
            )
            if memory_reply:
                await _reply_text(update.message, memory_reply)
                return
        roasts = getattr(self, "roasts", None)
        if update.message.text and roasts and await roasts.try_handle(update):
            return
        if update.message.text and await self.reports.try_handle(update):
            return
        sql_assistant = getattr(self, "sql_assistant", None)
        if update.message.text and sql_assistant and await sql_assistant.try_handle(update):
            return
        await self.capture.handle(update, context)

    async def help(self, update, context: ContextTypes.DEFAULT_TYPE):
        if not auth_svc.is_allowed(update.effective_user.id):
            return
        await _reply_text(update.message, HELP_TEXT)

    async def roast(self, update, context: ContextTypes.DEFAULT_TYPE):
        if not auth_svc.is_allowed(update.effective_user.id):
            return
        await self.roasts.try_handle(update)

    async def handle_button(self, update, context: ContextTypes.DEFAULT_TYPE):
        if not auth_svc.is_allowed(update.effective_user.id):
            await update.callback_query.answer(
                "Akses ditolak. Bot ini privat.", show_alert=True
            )
            return
        await self.capture.handle_callback(update, context)
