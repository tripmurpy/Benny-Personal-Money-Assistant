"""Telegram Service - Main Bot Interface

Handles all Telegram interactions with Benny's supportive personality.
Routes messages (text, photo, voice) to appropriate handlers.
"""

import io
import logging
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import Config
from services.ai_service import AIService
from services.sheets_service import SheetsService
from services.ai.coaching_engine import get_coaching_engine
from services.analytics_service import get_analytics_service
from services.export_service import get_export_service
from services.personality_responses import get_personality
from services.goal_handlers import handle_goals
from services.budget_handlers import handle_budgets
from services.budget_service import BudgetService
from services.chat_service import get_chat_service

logger = logging.getLogger(__name__)

class TelegramService:
    """
    Main Telegram bot service with Benny's personality.
    
    Handles all user interactions including:
    - Text, photo (OCR), and voice input
    - Menu navigation and reports
    - Personality-driven responses
    
    Attributes:
        ai_service: AI parsing for transactions
        sheets_service: Google Sheets integration
        coaching_engine: AI coaching insights
        analytics_service: Financial analytics
        export_service: PDF report generation
        personality: Benny's supportive responses
        last_activity: Timestamp for smart nudging
    """
    
    def __init__(self):
        """Initialize all services and Benny's personality."""
        self.ai_service = AIService()
        self.sheets_service = SheetsService()
        self.coaching_engine = get_coaching_engine()
        self.analytics_service = get_analytics_service()
        self.export_service = get_export_service()
        self.personality = get_personality()
        self.personality = get_personality()
        self.last_activity = datetime.now()
        self.budget_service = BudgetService()
        self.chat_service = get_chat_service()
        self.pending_expenses = {} # Store user_id -> transactions for expense source selection
        self.pending_inputs = {} # Store user_id -> text for incomplete transactions
        self.pending_income = {} # Store user_id -> transactions for income tagging
        logger.info("✅ Benny siap! (Text, OCR, Voice, AI Coaching)")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Welcome message with Benny's warm personality and intuitive keyboard.
        
        Shows persistent keyboard menu optimized for mobile use.
        Fewer rows = easier tapping on phone screens.
        """
        user_name = update.effective_user.first_name
        
        # Simple, mobile-friendly keyboard (3 rows instead of 4)
        keyboard = [
            [KeyboardButton("💵 Saldo"), KeyboardButton("📊 Laporan")],
            [KeyboardButton("🧠 Coaching"), KeyboardButton("📄 Export PDF")],
            [KeyboardButton("🎯 Goals"), KeyboardButton("💰 Budgets"), KeyboardButton("📈 Trend")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # Benny's supportive welcome message
        welcome = (
            f"Halo {user_name}! Aku Benny, sahabat keuanganmu! 💙\n\n"
            "Aku siap bantu kamu catat keuangan dengan mudah:\n"
            "✍️ Chat aja kayak ngobrol biasa\n"
            "📷 Foto struk belanjaan\n"
            "🎤 Voice note juga bisa!\n\n"
            "Ayo mulai! Kamu pasti bisa manage keuangan dengan baik! 💪✨"
        )
        
        await update.message.reply_text(
            welcome,
            reply_markup=reply_markup
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ROUTER UTAMA: Menangani TEKS, FOTO, dan SUARA."""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        if str(chat_id) != str(Config.ADMIN_ID): return
        
        self.last_activity = datetime.now()  # Update activity timestamp

        # --- FOTO (OCR) ---
        if update.message.photo:
            await self._handle_photo(update, context)
            return
        
        # --- VOICE (Speech-to-Text) ---
        if update.message.voice:
            await self._handle_voice(update, context)
            return

        # --- TEKS ---
        user_text = update.message.text
        
        # Extract reply context if user is replying to a bot message
        reply_context = ""
        if update.message.reply_to_message and update.message.reply_to_message.text:
            reply_context = update.message.reply_to_message.text
        
        if user_text:
            # Menu button handlers
            if user_text == "🧠 Coaching":
                await self.handle_coaching_report(update, context)
            elif user_text == "📊 Laporan":
                await self.handle_laporan_menu(update, context)
            elif user_text == "📄 Export PDF":
                await self.handle_export_pdf(update, context)
            elif user_text == "📈 Trend":
                await self.handle_trend_chart(update, context)
            elif user_text == "🎯 Goals":
                await handle_goals(update, context)
            elif user_text == "💰 Budgets":
                await handle_budgets(update, context)
            elif user_text == "💵 Saldo":
                await self.handle_saldo(update, context)
            else:
                # 0. Reply-to-Bot = always contextual AI chat (skip all transaction logic)
                if reply_context:
                    self.pending_inputs.pop(user_id, None)  # Clear any pending state
                    status_msg = await update.message.reply_text("💭 ...")
                    response = await self.ai_service.chat_with_user(user_text, reply_context=reply_context)
                    if response:
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=status_msg.message_id,
                            text=response
                        )
                    else:
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=status_msg.message_id,
                            text="Hmm, aku agak bingung nih 😅 Coba cerita lagi dong! 💙"
                        )
                    return

                # 1. Pengecualian awal untuk Pure Chat (gak ada angka + cocok template)
                is_pure_chat = False
                if not any(char.isdigit() for char in user_text):
                    if self.chat_service.match_template(user_text):
                        is_pure_chat = True
                        
                # Jika user mengganti topik dengan chat biasa, bersihkan state pending
                if is_pure_chat:
                    self.pending_inputs.pop(user_id, None)
                    self.pending_expenses.pop(user_id, None)
                    self.pending_income.pop(user_id, None)
                    from services.budget_handlers import pending_topup
                    pending_topup.pop(user_id, None)
                    
                    # Langsung tembak ke fungsi chat fallback
                    response = self.chat_service.match_template(user_text)
                    if response:
                        await update.message.reply_text(response)
                    return
                
                # Check for pending Top Up first
                from services.budget_handlers import pending_topup, _parse_indonesian_currency
                if user_id in pending_topup:
                    category = pending_topup.pop(user_id)
                    try:
                        amount = _parse_indonesian_currency(user_text)
                        if amount <= 0:
                            await update.message.reply_text("❌ Jumlah tidak valid.")
                            return
                        
                        success, new_limit = self.budget_service.top_up_budget(category, amount)
                        if success:
                            amt_str = "{:,.0f}".format(amount).replace(',', '.')
                            new_str = "{:,.0f}".format(new_limit).replace(',', '.')
                            await update.message.reply_text(
                                f"✅ **Budget {category.capitalize()} berhasil di-top up!**\n\n"
                                f"➕ Ditambah: Rp {amt_str}\n"
                                f"💰 Total Limit Baru: Rp {new_str}",
                                parse_mode='Markdown'
                            )
                        else:
                            await update.message.reply_text("❌ Gagal top up budget.")
                    except:
                        await update.message.reply_text("❌ Format jumlah tidak valid. Coba lagi.")
                    return

                # Check for pending input (Smart Follow-up)
                if user_id in self.pending_inputs:
                    previous_text = self.pending_inputs.pop(user_id)
                    user_text = f"{previous_text} {user_text}"
                    await update.message.reply_text(f"👌 Oke, digabung: \"{user_text}\"")
                
                # Check for natural language report requests
                text_lower = user_text.lower().strip()
                if any(kw in text_lower for kw in ['laporan', 'report']):
                    if any(kw in text_lower for kw in ['hari', 'harian', 'today', 'hari ini']):
                        await self.process_report(update, context, 'harian')
                        return
                    elif any(kw in text_lower for kw in ['minggu', 'mingguan', 'week', 'minggu ini']):
                        await self.process_report(update, context, 'mingguan')
                        return
                    elif any(kw in text_lower for kw in ['bulan', 'bulanan', 'month', 'bulan ini', 'januari', 'februari', 'maret', 'april', 'mei', 'juni', 'juli', 'agustus', 'september', 'oktober', 'november', 'desember']):
                        await self.process_report(update, context, 'bulanan')
                        return
                        
                # Check for Smart Recommendation
                recommendation_keywords = [
                    'rekomendasi', 'saran', 'beli apa', 'jajan apa', 'makan apa', 
                    'minum apa', 'enaknya beli', 'bagusnya beli'
                ]
                if any(kw in text_lower for kw in recommendation_keywords):
                    status_msg = await update.message.reply_text("Hmm bentar ya, aku cek dulu catatan belanjamu... 🔍")
                    try:
                        all_transactions = self.sheets_service.get_all_transactions()
                        current_time = datetime.now().strftime('%H:%M')
                        response = await self.ai_service.generate_smart_recommendation(
                            all_transactions, current_time, user_text
                        )
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=status_msg.message_id,
                            text=response
                        )
                    except Exception as e:
                        logger.error(f"Error handling recommendation: {e}")
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=status_msg.message_id,
                            text="❌ Maaf, otak analisaku lagi loading lama nih. Coba lagi nanti ya! 💙"
                        )
                    return
                
                # Cek apakah ini pertanyaan/chat atau transaksi
                if self._is_transaction_input(user_text):
                     # Process Transaction
                     status_msg = await update.message.reply_text("⏳ Mencatat transaksi...")
                     try:
                         transactions = await self.ai_service.parse_expense(user_text)
                         
                         # Check for Income transactions (Interception for Primer/Sekunder)
                         has_income = False
                         for t in transactions:
                             if str(t.get('category', '')).lower() in ['income', 'pemasukan', 'gaji']:
                                 has_income = True
                                 break
                         
                         if has_income:
                             # Pause saving, ask for classification
                             self.pending_income[user_id] = transactions
                             keyboard = [
                                 [InlineKeyboardButton(" PRIMER (Wajib/Utama)", callback_data='income_primer')],
                                 [InlineKeyboardButton(" SEKUNDER (Tambahan)", callback_data='income_sekunder')]
                             ]
                             reply_markup = InlineKeyboardMarkup(keyboard)
                             await context.bot.edit_message_text(
                                 chat_id=chat_id,
                                 message_id=status_msg.message_id,
                                 text="💰 **Mendapat Pemasukan!**\n\nIni termasuk jenis apa?",
                                 reply_markup=reply_markup,
                                 parse_mode='Markdown'
                             )
                         else:
                            # Proceed as normal for expenses
                             # Proceed as normal for expenses
                             self.pending_expenses[user_id] = transactions
                             
                             # Suggest matching budget if possible (Smart 10x Feature)
                             first_cat = transactions[0].get('category', '').lower()
                             budgets = self.budget_service.get_budgets()
                             
                             # Smart buttons
                             keyboard = [[InlineKeyboardButton("💳 Saldo (Umum)", callback_data='src_saldo')]]
                             
                             # If category matches a budget, offer it directly
                             if first_cat in budgets:
                                 keyboard.append([InlineKeyboardButton(f"📂 Budget: {first_cat.capitalize()}", callback_data=f'src_budget_select_{first_cat}')])
                                 keyboard.append([InlineKeyboardButton("📂 Budget Lain...", callback_data='src_budget_list')])
                             else:
                                 keyboard.append([InlineKeyboardButton("💰 Pakai Budget...", callback_data='src_budget_list')])
                                 
                             reply_markup = InlineKeyboardMarkup(keyboard)
                             
                             await context.bot.edit_message_text(
                                 chat_id=chat_id,
                                 message_id=status_msg.message_id,
                                 text="💸 **Pengeluaran via apa?**",
                                 reply_markup=reply_markup,
                                 parse_mode='Markdown'
                             )
                     except Exception as e:
                         logging.error(f"Error Text: {e}")
                         await context.bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text="❌ Error sistem.")
                     return

                # Check for Incomplete Transaction (Intent but no Amount)
                if self._is_incomplete_transaction(user_text):
                    self.pending_inputs[user_id] = user_text
                    await update.message.reply_text(
                        f"🤔 \"{user_text}\"... Nominalnya berapa?\n"
                        "Ketik angkanya aja, nanti aku gabungin! 😉"
                    )
                    return

                # Warm Chat: Pattern match first, then AI fallback
                response = self.chat_service.match_template(user_text)
                if response:
                    await update.message.reply_text(response)
                else:
                    status_msg = await update.message.reply_text("💭 ...")
                    response = await self.ai_service.chat_with_user(user_text)
                    if response:
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=status_msg.message_id,
                            text=response
                        )
                    else:
                        await context.bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=status_msg.message_id,
                            text="Halo! 💙 Aku di sini kok! Ada yang mau dicatat atau ditanyain? 😊"
                        )
                return

    async def _handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """FR-02: Handle foto struk untuk OCR"""
        chat_id = update.effective_chat.id
        status_msg = await update.message.reply_text("📷 Membaca struk...")
        
        try:
            # Gunakan resolusi menengah (agar tidak terlalu besar untuk LLM)
            photo = update.message.photo[-2] if len(update.message.photo) > 2 else update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            
            # Download foto ke memory
            bio = io.BytesIO()
            await file.download_to_memory(bio)
            image_bytes = bio.getvalue()
            
            # Kirim ke AI OCR
            transactions = await self.ai_service.parse_receipt_image(image_bytes)
            await self._save_and_reply(update, context, transactions, status_msg.message_id)
        except Exception as e:
            logging.error(f"Error Photo: {e}")
            await context.bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text="❌ Gagal membaca struk.")

    async def _handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """FR-03: Handle voice message untuk Speech-to-Text"""
        chat_id = update.effective_chat.id
        status_msg = await update.message.reply_text("🎤 Mendengarkan...")
        
        try:
            voice = update.message.voice
            file = await context.bot.get_file(voice.file_id)
            
            # Download audio ke memory
            bio = io.BytesIO()
            await file.download_to_memory(bio)
            audio_bytes = bio.getvalue()
            
            # Transcribe audio
            text = await self.ai_service.transcribe_audio(audio_bytes)
            if not text:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text="❌ Tidak terdengar.")
                return
            
            # Parse hasil transcribe
            await context.bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text=f"🎤 \"{text}\"\n⏳ Mencatat...")
            transactions = await self.ai_service.parse_expense(text)
            await self._save_and_reply(update, context, transactions, status_msg.message_id)
        except Exception as e:
            logging.error(f"Error Voice: {e}")
            await context.bot.edit_message_text(chat_id=chat_id, message_id=status_msg.message_id, text="❌ Gagal memproses suara.")
    
    def _is_transaction_input(self, text: str) -> bool:
        """
        Helper: Deteksi apakah input adalah transaksi atau pertanyaan/chat biasa.
        Returns True jika kemungkinan transaksi, False jika bukan.
        """
        text_lower = text.lower().strip()
        import string
        clean_text = text_lower.translate(str.maketrans('', '', string.punctuation)).strip()
        words = clean_text.split()
        
        # 1. Pengecualian percakapan umum yang sering disalahartikan
        chat_expressions = [
            'terima kasih', 'terimakasih', 'makasih', 'makasi', 'thanks', 'tq',
            'oke', 'ok', 'sip', 'mantap', 'iya', 'y', 'halo', 'hai', 'hello',
            'pagi', 'siang', 'sore', 'malam'
        ]
        
        # Jika pesan pendek dan mengandung kata chat, serta tidak ada angka nominal
        if len(words) <= 3 and any(cw in clean_text for cw in chat_expressions):
            if not any(char.isdigit() for char in text):
                return False
                
        # Daftar kata tanya - jika ada, kemungkinan bukan transaksi
        question_words = [
            'apa', 'kenapa', 'gimana', 'bagaimana', 'mengapa', 
            'kapan', 'siapa', 'dimana', 'berapa', 'apakah',
            'mana', 'tolong', 'help', 'bantuan', 'ini apa'
        ]
        
        # Jika input terlalu pendek (< 5 karakter) tapi bukan transaksi angka jelas
        if len(text_lower) < 5 and not any(char.isdigit() for char in text_lower):
            return False
        
        # Jika mengandung kata tanya di awal, kemungkinan bukan transaksi
        for q in question_words:
            if text_lower.startswith(q):
                return False
        
        # Kata-kata yang mengindikasikan transaksi
        transaction_keywords = [
            'beli', 'bayar', 'belanja', 'buat', 'untuk',
            'makan', 'bensin', 'isi', 'parkir', 'transport',
            'pulsa', 'token', 'internet', 'bills', 'tagihan',
            'rb', 'ribu', 'jt', 'juta', 'rp', 'rupiah',
            'k', 'gaji', 'masuk', 'income',
            'dapat', 'terima', 'uang', 'transfer', 'jual'
        ]
        
        # Cek apakah ada angka (indikasi jumlah uang)
        has_number = any(char.isdigit() for char in text)
        
        # Pencocokan keyword transaksi (sekarang pakai whole word matching jika memungkinkan)
        has_transaction_keyword = any(kw in words for kw in transaction_keywords)
        # Tambahan untuk singkatan/gabungan angka seperti "10rb", "50k", "20juta"
        if not has_transaction_keyword:
            has_transaction_keyword = any(kw in text_lower for kw in ['ribu', 'rb', 'juta', 'jt', 'rupiah', 'rp', 'k '])
            
        # 2. Keyword kuat: pastikan dicocokkan per-kata agar tidak nyangkut (misal "terima" di "terimakasih")
        strong_keywords = ['beli', 'bayar', 'belanja', 'gaji', 'income', 'dapat', 'terima']
        has_strong_keyword = any(kw in words for kw in strong_keywords)
        
        return (has_number and has_transaction_keyword) or has_strong_keyword

    def _is_incomplete_transaction(self, text: str) -> bool:
        """
        Helper: Cek apakah text terlihat seperti transaksi tapi tanpa nominal uang.
        """
        text_lower = text.lower().strip()
        import string
        clean_text = text_lower.translate(str.maketrans('', '', string.punctuation)).strip()
        words = clean_text.split()
        
        # Pengecualian tambahan jika terlewat (fallback perlindungan)
        chat_expressions = [
            'terima kasih', 'terimakasih', 'makasih', 'makasi', 'thanks', 'tq',
            'oke', 'ok', 'sip', 'mantap', 'iya', 'y', 'halo', 'hai', 'hello',
            'pagi', 'siang', 'sore', 'malam', 'maksudnya'
        ]
        if len(words) <= 3 and any(cw in clean_text for cw in chat_expressions):
            return False

        # Keywords that strongly imply transaction intent even without numbers
        keywords = [
            'beli', 'bayar', 'belanja', 'makan', 'minum', 'jajan', 
            'isi', 'topup', 'tagihan', 'gaji', 'dapat', 'terima', 
            'uang', 'income', 'transfer', 'jual'
        ]
        
        # Must have keyword (sekarang harus full word)
        has_keyword = any(kw in words for kw in keywords)
        
        # Must NOT have numbers
        has_number = any(char.isdigit() for char in text)
        
        # Ignore if it's a question or too short
        is_question = any(q in words for q in ['apa', 'dimana', 'kapan', 'tanya', 'siapa', 'gimana'])
        
        return has_keyword and not has_number and not is_question and len(text) > 3


    def _calculate_balance(self):
        """Calculate total income, expenses, and balance from all transactions"""
        all_data = self.sheets_service.get_all_transactions()
        total_income = 0
        total_expense = 0
        
        for item in all_data:
            try:
                category = str(item.get('CATEGORY', '')).lower()
                
                # Try new format first (EXPENSE/INCOME columns)
                expense_col = item.get('EXPENSE', '')
                income_col = item.get('INCOME', '')
                
                # If new columns exist and have values, use them
                if expense_col or income_col:
                    # Clean values
                    if isinstance(expense_col, str):
                        expense = int(expense_col.replace(',', '').replace('.', '')) if expense_col else 0
                    else:
                        expense = int(expense_col) if expense_col else 0
                        
                    if isinstance(income_col, str):
                        income = int(income_col.replace(',', '').replace('.', '')) if income_col else 0
                    else:
                        income = int(income_col) if income_col else 0
                else:
                    # Fallback to old format (AMOUNTH column)
                    amount = item.get('AMOUNTH(IDR)', 0)
                    if isinstance(amount, str):
                        amount = int(amount.replace(',', '').replace('.', '')) if amount else 0
                    else:
                        amount = int(amount) if amount else 0
                    
                    # Classify based on category
                    if category in ['income', 'pemasukan']:
                        income = amount
                        expense = 0
                    else:
                        expense = amount
                        income = 0
                    
                total_income += income
                total_expense += expense
            except Exception as e:
                continue
                
        balance = total_income - total_expense
        return total_income, total_expense, balance

    async def _save_and_reply(self, update, context, transactions, message_id):
        """
        Save transactions and reply with Benny's supportive personality.
        
        Uses personality engine to generate warm, contextual confirmations
        instead of generic success messages.
        """
        chat_id = update.effective_chat.id
        
        if not transactions:
            await context.bot.edit_message_text(
                chat_id=chat_id, 
                message_id=message_id, 
                text="🤖 Hmm, aku ga nemu data transaksi nih. Coba lagi ya! 💙"
            )
            return

        # Decide where to save
        is_income_batch = False
        for t in transactions:
             if str(t.get('category', '')).lower() in ['income', 'pemasukan', 'gaji']:
                 is_income_batch = True
                 break

        if is_income_batch:
            success = self.sheets_service.add_income_transactions(transactions)
        else:
            success = self.sheets_service.add_transactions_bulk(transactions)
        
        if success:
            # Report Success
            pass # Continue to build reply
        else:
             await context.bot.edit_message_text(chat_id=chat_id, message_id=message_id, text="❌ Gagal simpan ke database.")
             return
            
        # Get personality response
        first_trans = transactions[0]
        personality_msg = self.personality.get_transaction_response(
            first_trans.get('amount', 0),
            first_trans.get('category', 'Other')
        )
        
        reply_text = f"{personality_msg}\n\n"
        
        total_income_now = 0
        total_expense_now = 0
        
        for t in transactions:
            item = t.get('item', 'Item')
            amount = t.get('amount', 0)
            category = t.get('category', 'Lainnya')
            is_income = str(category).lower() in ['income', 'pemasukan', 'gaji']
            
            amt_str = "{:,.0f}".format(amount).replace(',', '.')
            
            if is_income:
                total_income_now += amount
                item_line = f"💵 {item}"
                detail_line = f"📂 {category} | 💰 +Rp{amt_str}"
            else:
                total_expense_now += amount
                item_line = f"🛒 {item}"
                detail_line = f"📂 {category} | 💸 -Rp{amt_str}"
                
            reply_text += f"{item_line}\n{detail_line}\n\n"
        
        # Calculate Realtime Saldo (Triggered every transaction)
        is_insufficient = False
        try:
            _, _, current_balance = self._calculate_balance()
            if current_balance < 0:
                is_insufficient = True
            _, _, _, start_date = self._calculate_balance_since_last_income()
            # We don't show full details here anymore based on request, just the transaction.
        except: pass

        # Short Summary
        reply_text += "━━━━━━━━━━━━━━━━━━━━\n"
        if total_income_now > 0:
            reply_text += f"➕ PEMASUKAN : Rp {total_income_now:,.0f}".replace(',', '.') + "\n"
        if total_expense_now > 0:
            reply_text += f"➖ PENGELUARAN : Rp {total_expense_now:,.0f}".replace(',', '.') + "\n"
            
            # Show remaining budget if category has budget
            first_cat = transactions[0].get('category', '').lower()
            budgets = self.budget_service.get_budgets()
            if first_cat in budgets:
                remaining = budgets[first_cat]
                reply_text += f"💰 SALDO {first_cat.upper()} : Rp {remaining:,.0f}".replace(',', '.') + "\n"
                if remaining <= 0:
                    is_insufficient = True
            
        if total_income_now > 0:
            reply_text += "\n_Nice! Pemasukan masuk, semangat terus! 🔥_"
        else:
            reply_text += "\n_Tenang, kamu pasti bisa balance lagi!_ 💪"

        await context.bot.edit_message_text(
            chat_id=chat_id, 
            message_id=message_id, 
            text=reply_text, 
            parse_mode='Markdown'
        )

    async def handle_laporan_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show friendly greeting with report period options"""
        keyboard = [
            [InlineKeyboardButton("📅 Harian", callback_data='laporan_harian')],
            [InlineKeyboardButton("📆 Mingguan", callback_data='laporan_mingguan')],
            [InlineKeyboardButton("📊 Bulanan", callback_data='laporan_bulanan')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Hi! Aku siap melaporkan laporan keuanganmu! 💙\n\n"
            "Pilih periode laporan yang kamu mau:",
            reply_markup=reply_markup
        )

    async def handle_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler Tombol Inline (Analisis AI + Report Selection)"""
        query = update.callback_query
        
        # Security Check
        if str(update.effective_user.id) != str(Config.ADMIN_ID):
            await query.answer("⛔ Akses ditolak. Bot ini privat.", show_alert=True)
            return

        await query.answer()
        action = query.data

        # Handle report period selection
        if action.startswith('laporan_'):
            period_type = action.replace('laporan_', '')
            await query.edit_message_text("⏳ Mengambil data...")
            await self._send_report_to_callback(query, context, period_type)
            return

        # Handle Income Classification
        if action.startswith('income_'):
            user_id = update.effective_user.id
            tag = "[Primer]" if action == 'income_primer' else "[Sekunder]"
            
            if user_id in self.pending_income:
                transactions = self.pending_income.pop(user_id)
                
                # Tag ONLY the income transactions
                for t in transactions:
                    if str(t.get('category', '')).lower() in ['income', 'pemasukan', 'gaji']:
                        original_item = t.get('item', 'Income')
                        t['item'] = f"{original_item} {tag}"
                
                await query.edit_message_text("💾 Menyimpan data...")
                # Use _save_and_reply which now routes internally
                await self._save_and_reply(update, context, transactions, query.message.message_id) 
            else:
                await query.edit_message_text("⚠️ Sesi kadaluarsa. Input ulang ya!")
            return

        # Handle Expense Source (Saldo vs Budget)
        if action == 'src_saldo':
             user_id = update.effective_user.id
             if user_id in self.pending_expenses:
                 transactions = self.pending_expenses.pop(user_id)
                 await query.edit_message_text("💾 Menyimpan ke Saldo Utama...")
                 await self._save_and_reply(update, context, transactions, query.message.message_id)
             else:
                 await query.edit_message_text("⚠️ Sesi kadaluarsa.")
             return

        if action == 'src_budget_list':
             budgets = self.budget_service.get_budgets()
             if not budgets:
                 await query.edit_message_text("⚠️ Belum ada budget! Gunakan /setbudget dulu.")
                 return
             
             keyboard = []
             # Create rows of 2 buttons for better UI
             row = []
             for cat in budgets:
                 row.append(InlineKeyboardButton(f"📂 {cat.capitalize()}", callback_data=f'src_budget_select_{cat}'))
                 if len(row) == 2:
                     keyboard.append(row)
                     row = []
             if row: keyboard.append(row)
             
             keyboard.append([InlineKeyboardButton("🔙 Batal (Pakai Saldo)", callback_data='src_saldo')])
             
             reply_markup = InlineKeyboardMarkup(keyboard)
             await query.edit_message_text("💰 **Pilih Budget:**", reply_markup=reply_markup, parse_mode='Markdown')
             return

        if action.startswith('src_budget_select_'):
             user_id = update.effective_user.id
             selected_budget = action.replace('src_budget_select_', '')
             
             if user_id in self.pending_expenses:
                 transactions = self.pending_expenses.pop(user_id)
                 
                 # Calculate total expense
                 total_expense = sum(t.get('amount', 0) for t in transactions)
                 
                 # Deduct from budget
                 deducted, excess = self.budget_service.deduct_budget(selected_budget, total_expense)
                 
                 # UPDATE Categories to match selected budget
                 for t in transactions:
                     t['category'] = selected_budget 
                 
                 if excess > 0:
                     deducted_str = "{:,.0f}".format(deducted).replace(',', '.')
                     excess_str = "{:,.0f}".format(excess).replace(',', '.')
                     msg = f"💾 Budget {selected_budget.capitalize()}: -Rp {deducted_str} (Habis!) + Saldo: -Rp {excess_str}"
                     await query.edit_message_text(msg)
                 else:
                    await query.edit_message_text(f"💾 Memotong budget {selected_budget.capitalize()}...")
                 
                 await self._save_and_reply(update, context, transactions, query.message.message_id)
             else:
                 await query.edit_message_text("⚠️ Sesi kadaluarsa.")
             return

        # Handle Top Up Budget Flow
        if action == 'budget_topup_list':
            budgets = self.budget_service.get_budgets()
            if not budgets:
                await query.edit_message_text("⚠️ Belum ada budget!")
                return
            
            keyboard = []
            for cat, limit in budgets.items():
                limit_str = "{:,.0f}".format(limit).replace(',', '.')
                keyboard.append([InlineKeyboardButton(f"📂 {cat.capitalize()} (Rp {limit_str})", callback_data=f'budget_topup_select_{cat}')])
            keyboard.append([InlineKeyboardButton("🔙 Batal", callback_data='budget_topup_cancel')])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("➕ **Pilih budget untuk Top Up:**", reply_markup=reply_markup, parse_mode='Markdown')
            return

        if action.startswith('budget_topup_select_'):
            user_id = update.effective_user.id
            category = action.replace('budget_topup_select_', '')
            
            # Import and store in pending_topup
            from services.budget_handlers import pending_topup
            pending_topup[user_id] = category
            
            await query.edit_message_text(
                f"💰 **Top Up Budget: {category.capitalize()}**\n\n"
                "Ketik jumlah top up (contoh: `50rb`, `100000`):",
                parse_mode='Markdown'
            )
            return

        if action == 'budget_topup_cancel':
            await query.edit_message_text("❌ Top Up dibatalkan.")
            return

        # Handle Delete Budget Flow
        if action == 'budget_delete_list':
            budgets = self.budget_service.get_budgets()
            if not budgets:
                await query.edit_message_text("⚠️ Belum ada budget!")
                return
            
            keyboard = []
            for cat, limit in budgets.items():
                limit_str = "{:,.0f}".format(limit).replace(',', '.')
                keyboard.append([InlineKeyboardButton(f"🗑️ {cat.capitalize()} (Rp {limit_str})", callback_data=f'budget_delete_select_{cat}')])
            keyboard.append([InlineKeyboardButton("🔙 Batal", callback_data='budget_delete_cancel')])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("🗑️ **Pilih budget untuk dihapus:**", reply_markup=reply_markup, parse_mode='Markdown')
            return

        if action.startswith('budget_delete_select_'):
            category = action.replace('budget_delete_select_', '')
            
            keyboard = [
                [InlineKeyboardButton("✅ Ya, Hapus", callback_data=f'budget_delete_confirm_{category}')],
                [InlineKeyboardButton("❌ Batal", callback_data='budget_delete_cancel')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"⚠️ **Yakin hapus budget {category.capitalize()}?**\n\n"
                "Aksi ini tidak bisa dibatalkan.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return

        if action.startswith('budget_delete_confirm_'):
            category = action.replace('budget_delete_confirm_', '')
            
            if self.budget_service.delete_budget(category):
                await query.edit_message_text(f"✅ Budget **{category.capitalize()}** berhasil dihapus!", parse_mode='Markdown')
            else:
                await query.edit_message_text(f"❌ Gagal menghapus budget {category}.")
            return

        if action == 'budget_delete_cancel':
            await query.edit_message_text("❌ Hapus budget dibatalkan.")
            return

        # Original AI analysis handling
        all_data = self.sheets_service.get_all_transactions()
        filtered_data = []
        today = datetime.now()
        period_label = ""
        
        COL_DATE = 'DATE' 
        COL_ITEM = 'ITEM NAME'
        COL_CAT = 'CATEGORY'
        COL_AMOUNT = 'AMOUNTH(IDR)' 

        if action == 'analisis_minggu':
            start_date = today - timedelta(days=7)
            for d in all_data:
                try:
                    d_date = datetime.strptime(str(d.get(COL_DATE)), "%Y-%m-%d")
                    if d_date >= start_date: filtered_data.append(d)
                except: pass
            period_label = "7 Hari Terakhir"

        elif action == 'analisis_bulan':
            target_month = today.strftime("%Y-%m")
            filtered_data = [d for d in all_data if str(d.get(COL_DATE)).startswith(target_month)]
            period_label = "Bulan Ini"

        await query.edit_message_text(f"⏳ Sedang menganalisis data {period_label}...")
        
        clean_data = []
        for item in filtered_data:
            clean_data.append({
                "Date": item.get(COL_DATE),
                "Item Name": item.get(COL_ITEM),
                "Category": item.get(COL_CAT),
                "Amount (IDR)": item.get(COL_AMOUNT)
            })
            
        report = self.ai_service.analyze_expenses(clean_data, period_label)
        await query.edit_message_text(text=report)

    async def _send_report_to_callback(self, query, context, type_report):
        """Send report via callback query"""
        all_data = self.sheets_service.get_all_transactions()
        filtered_data = []
        today = datetime.now()
        period_label = ""
        
        COL_DATE = 'DATE'
        COL_AMOUNT = 'AMOUNTH(IDR)'
        COL_ITEM = 'ITEM NAME'

        if type_report == 'harian':
            target = today.strftime("%Y-%m-%d")
            filtered_data = [d for d in all_data if str(d.get(COL_DATE)) == target]
            period_label = "Hari Ini"
        elif type_report == 'mingguan':
            start_date = today - timedelta(days=7)
            for d in all_data:
                try:
                    d_date = datetime.strptime(str(d.get(COL_DATE)), "%Y-%m-%d")
                    if d_date >= start_date: filtered_data.append(d)
                except: pass
            period_label = "Minggu Ini"
        elif type_report == 'bulanan':
            target_month = today.strftime("%Y-%m")
            filtered_data = [d for d in all_data if str(d.get(COL_DATE)).startswith(target_month)]
            period_label = "Bulan Ini"

        if not filtered_data:
            await query.edit_message_text(f"📂 Data {period_label} kosong.")
            return

        total = 0
        report = f"📂 **Laporan {period_label}**\n\n"
        for t in filtered_data[-15:]:
            try:
                raw_amt = str(t.get(COL_AMOUNT)).replace(',', '').replace('.', '')
                amt = int(raw_amt)
                total += amt
                amt_str = "{:,.0f}".format(amt).replace(',', '.')
                report += f"▪️ {t.get(COL_ITEM)} - Rp{amt_str}\n"
            except: pass
        
        total_str = "{:,.0f}".format(total).replace(',', '.')
        report += f"\n💰 **Total: Rp {total_str}**"
        await query.edit_message_text(report, parse_mode='Markdown')

    async def process_report(self, update, context, type_report):
        """Helper Laporan Biasa (Non-AI)"""
        await update.message.reply_text("⏳ Mengambil data...")
        all_data = self.sheets_service.get_all_transactions()
        filtered_data = []
        today = datetime.now()
        period_label = ""
        
        COL_DATE = 'DATE'
        COL_AMOUNT = 'AMOUNTH(IDR)'
        COL_ITEM = 'ITEM NAME'

        if type_report == 'harian':
            target = today.strftime("%Y-%m-%d")
            filtered_data = [d for d in all_data if str(d.get(COL_DATE)) == target]
            period_label = "Hari Ini"
        elif type_report == 'mingguan':
            start_date = today - timedelta(days=7)
            for d in all_data:
                try:
                    d_date = datetime.strptime(str(d.get(COL_DATE)), "%Y-%m-%d")
                    if d_date >= start_date: filtered_data.append(d)
                except: pass
            period_label = "Minggu Ini"
        elif type_report == 'bulanan':
            target_month = today.strftime("%Y-%m")
            filtered_data = [d for d in all_data if str(d.get(COL_DATE)).startswith(target_month)]
            period_label = "Bulan Ini"

        if not filtered_data:
            await update.message.reply_text(f"📂 Data {period_label} kosong.")
            return

        total = 0
        report = f"📂 **Laporan {period_label}**\n\n"
        for t in filtered_data[-15:]:
            try:
                raw_amt = str(t.get(COL_AMOUNT)).replace(',', '').replace('.', '')
                amt = int(raw_amt)
                total += amt
                amt_str = "{:,.0f}".format(amt).replace(',', '.')
                report += f"▪️ {t.get(COL_ITEM)} - Rp{amt_str}\n"
            except: pass
        
        total_str = "{:,.0f}".format(total).replace(',', '.')
        report += f"\n💰 **Total: Rp {total_str}**"
        await update.message.reply_text(report, parse_mode='Markdown')

    def _calculate_balance_since_last_income(self):
        """
        Calculate balance starting from the date of the LAST income transaction.
        This provides a 'Realtime Runway' view.
        
        Returns:
            total_income: Total income (calculated from Budget sheet)
            total_expense: Total expense (calculated from Main sheet)
            balance: Income - Expense
            start_date: Date of last income
        """
        # 1. Fetch Data
        expense_data = self.sheets_service.get_all_transactions()
        income_data = self.sheets_service.get_income_transactions()
        
        # 2. Find Last Income Date (from INCOME sheet)
        last_income_date = None
        
        # Parse Dates
        parsed_incomes = []
        for item in income_data:
            try:
                # Column headers for Budget sheet: Date, Source, Type, Amount
                d_str = str(item.get('Date') or item.get('date')).strip()
                d_obj = datetime.strptime(d_str, "%Y-%m-%d")
                parsed_incomes.append((d_obj, item))
            except: continue
            
        parsed_incomes.sort(key=lambda x: x[0])
        
        # Determine Start Date
        if parsed_incomes:
            start_date = parsed_incomes[-1][0] # Latest income
        else:
            today = datetime.now()
            start_date = datetime(today.year, today.month, 1)

        # 3. Calculate Income (since start_date)
        filtered_income = 0
        for d_obj, item in parsed_incomes:
            if d_obj >= start_date:
                # 'Amount' column in Budget sheet
                amt = self.sheets_service._clean_amount(item.get('Amount', 0))
                filtered_income += amt
                
        # 4. Calculate Expense (since start_date)
        filtered_expense = 0
        for item in expense_data:
            try:
                # Parse Expense Date
                d_str = str(item.get('DATE') or item.get('date')).strip()
                d_obj = datetime.strptime(d_str, "%Y-%m-%d")
                
                if d_obj >= start_date:
                    # 'AMOUNTH(IDR)' in Sheet1 is now purely Expense (conceptually)
                    # Use existing logic to be safe
                    cat = str(item.get('CATEGORY', '')).lower()
                    # Skip if somehow an income slipped into main sheet
                    if cat in ['income', 'pemasukan', 'gaji']: continue
                    
                    amt = self.sheets_service._clean_amount(item.get('AMOUNTH(IDR)', 0))
                    filtered_expense += amt
            except: continue

        balance = filtered_income - filtered_expense
        return filtered_income, filtered_expense, balance, start_date

    async def handle_saldo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle Saldo button - show balance since last income"""
        await update.message.reply_text("⏳ Menghitung sisa uang...")
        
        total_income, total_expense, balance, start_date = self._calculate_balance_since_last_income()
        
        income_str = "{:,.0f}".format(total_income).replace(',', '.')
        expense_str = "{:,.0f}".format(total_expense).replace(',', '.')
        balance_str = "{:,.0f}".format(balance).replace(',', '.')
        
        date_label = start_date.strftime("%d %b")
        today_label = datetime.now().strftime("%d %b")
        
        emoji = "✅ Aman" if balance >= 0 else "⚠️ Warning"
        
        report = f"💰 **SISA UANG** ({date_label} - {today_label}) 💰\n\n"
        report += f"➕ PEMASUKAN   : Rp {income_str}\n"
        report += f"➖ PENGELUARAN : Rp {expense_str}\n"
        report += "━━━━━━━━━━━━━━━━━━\n"
        report += f"💵 SISA SALDO  : Rp {balance_str} ({emoji})"
        
        await update.message.reply_text(report, parse_mode='Markdown')

    async def handle_coaching_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle Coaching AI button - generate weekly coaching report"""
        await update.message.reply_text("🧠 Generating AI coaching insights...")
        
        try:
            # Get transactions for current and previous week
            all_data = self.sheets_service.get_all_transactions()
            today = datetime.now()
            
            # Current week (last 7 days)
            current_week_start = today - timedelta(days=7)
            current_week = []
            previous_week = []
            
            for t in all_data:
                try:
                    date_str = str(t.get('DATE') or t.get('date') or '')
                    if date_str:
                        t_date = datetime.strptime(date_str, '%Y-%m-%d')
                        if t_date >= current_week_start:
                            current_week.append(t)
                        elif t_date >= current_week_start - timedelta(days=7):
                            previous_week.append(t)
                except ValueError:
                    continue
            
            # Generate coaching report
            report_data = self.coaching_engine.generate_weekly_report(
                current_week, 
                previous_week
            )
            
            # Format and send
            message = self.coaching_engine.format_weekly_report_message(report_data)
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logging.error(f"Error generating coaching report: {e}")
            await update.message.reply_text("❌ Gagal menghasilkan laporan coaching. Coba lagi nanti.")

    async def handle_dashboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle Dashboard button - show analytics dashboard"""
        await update.message.reply_text("📊 Loading dashboard...")
        
        try:
            all_data = self.sheets_service.get_all_transactions()
            
            # Get dashboard data for last 30 days
            dashboard = self.analytics_service.get_dashboard_data(all_data, period_days=30)
            
            # Format message
            message = self.analytics_service.format_dashboard_message(dashboard, "30 Hari Terakhir")
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logging.error(f"Error generating dashboard: {e}")
            await update.message.reply_text("❌ Gagal memuat dashboard. Coba lagi nanti.")

    async def handle_export_pdf(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle Export PDF button - generate and send PDF report"""
        if not self.export_service.is_available():
            await update.message.reply_text(
                "⚠️ PDF export belum tersedia.\n"
                "Install: `pip install reportlab matplotlib`",
                parse_mode='Markdown'
            )
            return
        
        await update.message.reply_text("📄 Generating PDF report...")
        
        try:
            all_data = self.sheets_service.get_all_transactions()
            today = datetime.now()
            
            # Filter current month
            current_month = today.strftime('%Y-%m')
            monthly_data = [
                t for t in all_data 
                if str(t.get('DATE') or t.get('date') or '').startswith(current_month)
            ]
            
            # Get analytics data
            dashboard = self.analytics_service.get_dashboard_data(monthly_data, period_days=30)
            
            # Get coaching tips
            coaching_report = self.coaching_engine.generate_weekly_report(monthly_data, [])
            
            # Generate PDF
            pdf_bytes = self.export_service.generate_monthly_report(
                transactions=monthly_data,
                category_breakdown=dashboard['category_distribution'],
                summary=dashboard['summary'],
                coaching_tips=coaching_report.get('tips', []),
                period_label=f"Bulan {today.strftime('%B %Y')}"
            )
            
            if pdf_bytes:
                # Send PDF file
                await update.message.reply_document(
                    document=io.BytesIO(pdf_bytes),
                    filename=f"Laporan_Keuangan_{today.strftime('%Y_%m')}.pdf",
                    caption="📊 Laporan Keuangan Bulanan\nGenerated by Benny AI 🤖"
                )
            else:
                await update.message.reply_text("❌ Gagal membuat PDF. Coba lagi nanti.")
                
        except Exception as e:
            logging.error(f"Error generating PDF: {e}")
            await update.message.reply_text("❌ Gagal menghasilkan PDF. Coba lagi nanti.")

    async def handle_trend_chart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle Trend button - show spending trend chart"""
        await update.message.reply_text("📈 Analyzing trends...")
        
        try:
            all_data = self.sheets_service.get_all_transactions()
            
            # Get trend data
            dashboard = self.analytics_service.get_dashboard_data(all_data, period_days=14)
            
            # Generate text-based chart
            chart_message = self.analytics_service.generate_trend_chart_text(
                dashboard['trends'],
                "TREND PENGELUARAN 14 HARI"
            )
            
            # Add summary
            summary = dashboard['summary']
            daily_avg = dashboard['daily_average']
            
            message = f"{chart_message}\n\n"
            message += "━━━━━━━━━━━━━━━━━━━━\n"
            message += f"📊 Total 14 Hari: Rp {summary['total_expense']:,}\n".replace(',', '.')
            message += f"📅 Rata-rata Harian: Rp {daily_avg:,}\n".replace(',', '.')
            
            if dashboard.get('comparison'):
                comp = dashboard['comparison']
                message += f"📈 vs Periode Lalu: {comp['trend']} ({comp['change_percent']}%)"
            
            await update.message.reply_text(message, parse_mode='Markdown')
            
        except Exception as e:
            logging.error(f"Error generating trend: {e}")
            await update.message.reply_text("❌ Gagal menghasilkan trend. Coba lagi nanti.")
