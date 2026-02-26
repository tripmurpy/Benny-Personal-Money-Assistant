from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from services.budget_service import BudgetService
from services.sheets_service import SheetsService
import goals_config
import logging
from datetime import datetime

budget_service = BudgetService()
sheets_service = SheetsService()

# State storage for top-up flow
pending_topup = {}  # user_id -> category

def _parse_indonesian_currency(text: str) -> int:
    """Parse Indonesian currency format to integer"""
    import re
    
    # Join all args to handle "240 ribu", "1 juta", etc
    text = text.lower().strip()
    
    # Remove common separators
    text = text.replace('.', '').replace(',', '').replace('rp', '').strip()
    
    # Handle "ribu" / "rb" / "k"
    if 'ribu' in text or ' rb' in text or text.endswith('rb') or ' k' in text or text.endswith('k'):
        number_part = re.sub(r'[^\d]', '', text)
        if number_part:
            return int(number_part) * 1000
    
    # Handle "juta" / "jt" / "million"
    if 'juta' in text or 'jt' in text or 'million' in text:
        number_part = re.sub(r'[^\d]', '', text)
        if number_part:
            return int(number_part) * 1000000
    
    # Plain number
    number_part = re.sub(r'[^\d]', '', text)
    return int(number_part) if number_part else 0

async def handle_set_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /setbudget <Category> <Limit>"""
    args = list(context.args) # Create a copy to safely modify
    
    # Support for "/set budget ..." alias
    if args and args[0].lower() == 'budget':
        args.pop(0)

    if len(args) < 2:
        await update.message.reply_text(
            "ℹ️ Format: `/setbudget <Kategori> <Limit>`\n"
            "Contoh:\n"
            "• `/setbudget Food 1000000`\n"
            "• `/setbudget Transport 240 ribu`\n"
            "• `/setbudget Shopping 2 juta`",
            parse_mode='Markdown'
        )
        return

    category = args[0]
    
    # Join remaining args for Indonesian format support
    limit_text = ' '.join(args[1:])
    
    try:
        limit = _parse_indonesian_currency(limit_text)
        if limit <= 0:
            raise ValueError("Invalid amount")
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Format limit tidak valid.")
        return

    if budget_service.set_budget(category, limit):
        limit_str = "{:,.0f}".format(limit).replace(',', '.')
        await update.message.reply_text(f"✅ Budget **{category}** di-set: Rp{limit_str}/bulan", parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Gagal set budget.")

async def handle_budgets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /budgets - Show all budgets with Top Up option"""
    budgets = budget_service.get_budgets()
    if not budgets:
        await update.message.reply_text("Belum ada budget yang diatur.")
        return

    msg = "💰 **Daftar Budget Bulanan**\n\n"
    for cat, limit in budgets.items():
        limit_str = "{:,.0f}".format(limit).replace(',', '.')
        msg += f"▫️ {cat.capitalize()}: Rp {limit_str}\n"
    
    keyboard = [
        [InlineKeyboardButton("➕ Top Up Budget", callback_data='budget_topup_list')],
        [InlineKeyboardButton("🗑️ Hapus Budget", callback_data='budget_delete_list')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)

async def handle_delete_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command: /deletebudget <Category>"""
    args = context.args
    if not args:
        await update.message.reply_text("ℹ️ Format: `/deletebudget <Kategori>`")
        return
    
    category = args[0]
    if budget_service.delete_budget(category):
        await update.message.reply_text(f"✅ Budget {category} dihapus.")
    else:
        await update.message.reply_text(f"❌ Budget {category} tidak ditemukan.")

async def check_budget_warning_job(context: ContextTypes.DEFAULT_TYPE):
    """
    Scheduled Job: Cek apakah pengeluaran bulan ini melebihi threshold budget.
    """
    from config import Config
    
    budgets = budget_service.get_budgets()
    if not budgets: return

    # Ambil transaksi bulan ini
    all_data = sheets_service.get_all_transactions()
    target_month = datetime.now().strftime("%Y-%m")
    
    # Hitung total per kategori bulan ini
    current_spending = {}
    for t in all_data:
        try:
            date = str(t.get('DATE', ''))
            cat = str(t.get('CATEGORY', '')).lower()
            amt = int(str(t.get('AMOUNTH(IDR)', 0)).replace(',','').replace('.',''))
            
            if date.startswith(target_month) and cat in budgets:
                current_spending[cat] = current_spending.get(cat, 0) + amt
        except:
            continue
            
    # Cek Threshold
    warnings = []
    # Cek Threshold
    warnings = []
    for cat, remaining_limit in budgets.items():
        spent = current_spending.get(cat, 0)
        
        # Logic: Original Budget = Spent + Remaining Limit
        # Usage % = Spent / Original Budget
        original_budget = spent + remaining_limit
        
        if original_budget > 0:
            percentage = spent / original_budget
        else:
            percentage = 0
        
        if percentage >= goals_config.BUDGET_WARNING_THRESHOLD:
            # Cegah spam warning -> (Idealnya simpan state 'last_warned', tapi untuk MVP kirim saja dulu)
            # Untuk mengurangi spam, kita hanya kirim jika job ini jalan (misal tiap 6 jam)
            pct_str = int(percentage * 100)
            
            # Format: Transport: 80% (Rp 800k / Rp 1jt)
            spent_fmt = "{:,.0f}".format(spent).replace(',', '.')
            total_fmt = "{:,.0f}".format(original_budget).replace(',', '.')
            
            warnings.append(f"⚠️ **{cat.capitalize()}**: {pct_str}% (Rp {spent_fmt} / Rp {total_fmt})")

    if warnings:
        msg = f"🚨 **Budget Alert ({datetime.now().strftime('%B')})**\n\n"
        msg += "\n".join(warnings)
        msg += "\n\nHati-hati ya bos penggunaannya! 💸"
        
        try:
            await context.bot.send_message(chat_id=Config.ADMIN_ID, text=msg, parse_mode='Markdown')
        except Exception as e:
            logging.error(f"Failed to send budget warning: {e}")
