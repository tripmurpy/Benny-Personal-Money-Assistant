"""Telegram handlers for fixed monthly budgets."""

import logging
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import Config
from services.budget_service import BudgetService
from services.event_logger import log_event

logger = logging.getLogger(__name__)
budget_service = BudgetService()
pending_topup = {}


def _parse_indonesian_currency(text: str) -> int:
    """Parse common Indonesian currency text to integer rupiah."""
    text = text.lower().strip().replace(".", "").replace(",", "").replace("rp", "").strip()
    number_part = re.sub(r"[^\d]", "", text)
    if not number_part:
        return 0
    if "ribu" in text or " rb" in text or text.endswith("rb") or " k" in text or text.endswith("k"):
        return int(number_part) * 1_000
    if "juta" in text or "jt" in text or "million" in text:
        return int(number_part) * 1_000_000
    return int(number_part)


async def handle_set_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /setbudget <Category> <Limit>."""
    args = list(context.args)
    if args and args[0].lower() == "budget":
        args.pop(0)

    if len(args) < 2:
        await update.message.reply_text(
            "ℹ️ Format: `/setbudget <Kategori> <Limit>`\n"
            "Contoh:\n"
            "• `/setbudget Food 1000000`\n"
            "• `/setbudget Transport 240 ribu`\n"
            "• `/setbudget Shopping 2 juta`",
            parse_mode="Markdown",
        )
        return

    category = args[0]
    limit = _parse_indonesian_currency(" ".join(args[1:]))
    if limit <= 0:
        await update.message.reply_text("❌ Format limit tidak valid.")
        return

    if budget_service.set_budget(category, limit):
        limit_str = f"{limit:,.0f}".replace(",", ".")
        await update.message.reply_text(
            f"✅ Budget **{category}** di-set: Rp{limit_str}/bulan",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text("❌ Gagal set budget.")


async def handle_budgets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /budgets - show fixed limits and current usage."""
    statuses = budget_service.get_budget_statuses()
    if not statuses:
        await update.message.reply_text("Belum ada budget yang diatur.")
        return

    msg = "💰 **Budget Bulan Ini**\n\n"
    for category, status in statuses.items():
        used = f"{status['used']:,.0f}".replace(",", ".")
        limit = f"{status['limit']:,.0f}".replace(",", ".")
        remaining = f"{status['remaining']:,.0f}".replace(",", ".")
        msg += (
            f"▫️ **{category.capitalize()}**\n"
            f"Rp {used} / Rp {limit} · {status['percentage']:g}%\n"
            f"Sisa Rp {remaining}\n\n"
        )

    keyboard = [
        [InlineKeyboardButton("➕ Top Up Budget", callback_data="budget_topup_list")],
        [InlineKeyboardButton("🗑️ Hapus Budget", callback_data="budget_delete_list")],
    ]
    await update.message.reply_text(
        msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_delete_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /deletebudget <Category>."""
    if not context.args:
        await update.message.reply_text("ℹ️ Format: `/deletebudget <Kategori>`")
        return

    category = context.args[0]
    if budget_service.delete_budget(category):
        await update.message.reply_text(f"✅ Budget {category} dihapus.")
    else:
        await update.message.reply_text(f"❌ Budget {category} tidak ditemukan.")


async def check_budget_warning_job(context: ContextTypes.DEFAULT_TYPE):
    """Send each crossed 80/100% threshold at most once per category/month."""
    alerts = budget_service.get_pending_alerts()
    if not alerts:
        return

    warnings = []
    for alert in alerts:
        used = f"{alert['used']:,.0f}".replace(",", ".")
        limit = f"{alert['limit']:,.0f}".replace(",", ".")
        warnings.append(
            f"⚠️ **{alert['category'].capitalize()}**: {alert['percentage']:g}% "
            f"(Rp {used} / Rp {limit})"
        )

    try:
        await context.bot.send_message(
            chat_id=Config.ADMIN_ID,
            text="🚨 **Budget Alert**\n\n" + "\n".join(warnings),
            parse_mode="Markdown",
        )
    except Exception as error:
        logger.error("Failed to send budget warning: %s", error)
        return

    if not budget_service.mark_alerts_sent(alerts):
        logger.error("Failed to persist budget alert state")
        return
    for alert in alerts:
        log_event(
            "budget_threshold_reached",
            Config.ADMIN_ID,
            category=alert["category"],
            threshold=alert["threshold"],
        )
