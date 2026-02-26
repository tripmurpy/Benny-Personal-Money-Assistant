from telegram import Update
from telegram.ext import ContextTypes
from services.goals_service import GoalsService
import logging

goals_service = GoalsService()

async def handle_set_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /setgoal <nama> <target>"""
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("ℹ️ Format: `/setgoal <Nama> <Nominal>`\nContoh: `/setgoal PS5 7000000`", parse_mode='Markdown')
        return

    name = args[0]
    try:
        target = int(args[1].replace('.', '').replace(',', ''))
    except ValueError:
        await update.message.reply_text("❌ Nominal harus angka.")
        return

    success = goals_service.set_goal(name, target)
    if success:
        await update.message.reply_text(f"✅ Target **{name}** sebesar Rp {target:,} berhasil dibuat!", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"⚠️ Gagal membuat goal. Mungkin nama '{name}' sudah ada.")

async def handle_goals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /goals"""
    # Di masa depan, kita bisa hitung 'Saved Amount' real dari transaksi 'Income' - 'Expense'
    # Untuk sekarang, kita ambil data apa adanya dari sheet Goals.
    msg = goals_service.get_formatted_goals_progress()
    await update.message.reply_text(msg, parse_mode='Markdown')

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
