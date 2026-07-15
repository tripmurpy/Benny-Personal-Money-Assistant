"""
Goal Handlers — Telegram command handlers for financial goals.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from services.goals_service import GoalsService
from services.event_logger import log_event
from config import Config

goals_service = GoalsService()


def _parse_amount(value: str):
    try:
        amount = int(value.replace('.', '').replace(',', ''))
        return amount if amount > 0 else None
    except ValueError:
        return None


async def handle_set_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /setgoal <nama> <target>"""
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "ℹ️ Format: `/setgoal <Nama> <Nominal>`\n"
            "Contoh: `/setgoal PS5 7000000`",
            parse_mode='Markdown',
        )
        return

    name = args[0]
    try:
        target = _parse_amount(args[1])
        if target is None:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Nominal harus angka.")
        return

    success = goals_service.set_goal(name, target)
    if success:
        await update.message.reply_text(
            f"✅ Target **{name}** sebesar Rp {target:,} berhasil dibuat!",
            parse_mode='Markdown',
        )
    else:
        await update.message.reply_text(
            f"⚠️ Gagal membuat goal. Mungkin nama '{name}' sudah ada."
        )


async def handle_goals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /goals"""
    msg = goals_service.get_formatted_goals_progress()
    keyboard = []
    for goal in goals_service.get_goals():
        goal_id = goal["id"]
        keyboard.append([
            InlineKeyboardButton(
                f"Tambah · {goal['name']}", callback_data=f"goal_add:{goal_id}"
            ),
            InlineKeyboardButton("Ambil", callback_data=f"goal_withdraw:{goal_id}"),
            InlineKeyboardButton("Riwayat", callback_data=f"goal_history:{goal_id}"),
        ])
    await update.message.reply_text(
        msg,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
    )


async def handle_contribute_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /contributegoal <nama> <nominal>"""
    if len(context.args) < 2:
        await update.message.reply_text("Format: `/contributegoal <Nama> <Nominal>`")
        return
    goal = goals_service.contribute(context.args[0], _parse_amount(context.args[1]) or 0)
    if not goal:
        await update.message.reply_text("Goal tidak ditemukan atau nominal tidak valid.")
        return
    await update.message.reply_text(
        f"Tabungan **{goal['name']}** sekarang Rp {int(goal['current_amount']):,}.",
        parse_mode='Markdown',
    )
    log_event("goal_contribution_added", Config.ADMIN_ID, goal_id=goal["id"])


async def handle_withdraw_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /withdrawgoal <nama> <nominal>"""
    if len(context.args) < 2:
        await update.message.reply_text("Format: `/withdrawgoal <Nama> <Nominal>`")
        return
    goal = goals_service.withdraw(context.args[0], _parse_amount(context.args[1]) or 0)
    if not goal:
        await update.message.reply_text(
            "Goal tidak ditemukan, nominal tidak valid, atau saldo tidak cukup."
        )
        return
    await update.message.reply_text(
        f"Saldo **{goal['name']}** sekarang Rp {int(goal['current_amount']):,}.",
        parse_mode='Markdown',
    )


async def handle_goal_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /goalhistory <nama>"""
    if not context.args:
        await update.message.reply_text("Format: `/goalhistory <Nama>`")
        return
    await update.message.reply_text(
        goals_service.get_formatted_history(context.args[0]), parse_mode='Markdown'
    )


async def handle_delete_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /deletegoal <nama>"""
    args = context.args
    if not args:
        await update.message.reply_text("ℹ️ Format: `/deletegoal <Nama>`")
        return

    name = args[0]
    if goals_service.delete_goal(name):
        await update.message.reply_text(f"✅ Goal '{name}' dihapus.")
    else:
        await update.message.reply_text(f"❌ Goal '{name}' tidak ditemukan.")
