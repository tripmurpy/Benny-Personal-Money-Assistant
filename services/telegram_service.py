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
import services.auth_service as auth_svc
from services.supabase_service import SupabaseService
from services.ai.coaching_engine import get_coaching_engine
from services.analytics_service import get_analytics_service
from services.export_service import get_export_service
from services.personality_responses import get_personality
from services.goal_handlers import handle_goals
from services.budget_handlers import handle_budgets
from services.budget_service import BudgetService
from services.chat_service import get_chat_service
from services.expense_query_service import get_expense_query_service
from services.history_service import HistoryService
from services.event_logger import log_event

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
        db: Supabase database service
        coaching_engine: AI coaching insights
        analytics_service: Financial analytics
        export_service: PDF report generation
        personality: Benny's supportive responses
        last_activity: Timestamp for smart nudging
    """

    def __init__(self):
        """Initialize all services and Benny's personality."""
        self.ai_service = AIService()
        self.db = SupabaseService()
        self.coaching_engine = get_coaching_engine()
        self.analytics_service = get_analytics_service()
        self.export_service = get_export_service()
        self.personality = get_personality()
        self.last_activity = datetime.now()
        self.budget_service = BudgetService()
        self.chat_service = get_chat_service()
        self.expense_query = get_expense_query_service()
        self.history_service = HistoryService(self.db)
        self.pending_query_data = {}  # user_id -> (transactions, label) for detail button
        logger.info("✅ Benny siap! (Text, OCR, Voice, AI Coaching)")

    def _user_id(self, update: Update) -> str:
        """Extract user_id as string for Supabase queries."""
        return str(update.effective_user.id)

    def _main_keyboard(self):
        """Return the private mode main keyboard."""
        keyboard = [
            [KeyboardButton("Ringkasan"), KeyboardButton("Riwayat")],
            [KeyboardButton("Budget"), KeyboardButton("Goals")],
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Welcome the configured private user without a second login."""
        if not auth_svc.is_allowed(update.effective_user.id):
            return
        await update.message.reply_text(
            "Selamat datang di Benny. Catat transaksi dengan pesan seperti: makan siang 25 ribu.",
            reply_markup=self._main_keyboard(),
        )
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ROUTER UTAMA: Menangani TEKS, FOTO, dan SUARA."""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        uid = str(user_id)
        if not auth_svc.is_allowed(user_id):
            return

        self.last_activity = datetime.now()

        # Ensure user profile exists before processing any transactions
        self.db.upsert_user(uid, {
            "username": update.effective_user.username or "",
            "first_name": update.effective_user.first_name or "",
        })

        # --- FOTO (OCR) OR DOCUMENT (GAMBAR) ---
        if update.message.photo or (update.message.document and update.message.document.mime_type and update.message.document.mime_type.startswith('image/')):
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
            if user_text == "Ringkasan":
                await self.handle_summary(update, context)
            elif user_text == "Riwayat":
                await self.handle_history(update, context)
            elif user_text == "Goals":
                await handle_goals(update, context)
            elif user_text == "Budget":
                await handle_budgets(update, context)
            else:
                pending_goal = context.user_data.pop("goal_action", None)
                if pending_goal:
                    from services.budget_handlers import _parse_indonesian_currency

                    amount = _parse_indonesian_currency(user_text)
                    if amount <= 0:
                        await update.message.reply_text("Nominal belum valid.")
                        return
                    goal = (
                        self.db.contribute_goal(uid, pending_goal["goal_id"], amount)
                        if pending_goal["action"] == "contribute"
                        else self.db.withdraw_goal(uid, pending_goal["goal_id"], amount)
                    )
                    if not goal:
                        await update.message.reply_text(
                            "Perubahan goal gagal. Periksa nominal dan saldo goal."
                        )
                        return
                    saved = f"{int(goal.get('current_amount', 0)):,.0f}".replace(",", ".")
                    target = f"{int(goal.get('target_amount', 0)):,.0f}".replace(",", ".")
                    await update.message.reply_text(
                        f"Goal {goal.get('name', '')}\nRp{saved} / Rp{target}"
                    )
                    return

                if update.message.reply_to_message:
                    markup = update.message.reply_to_message.reply_markup
                    if markup:
                        callbacks = [
                            button.callback_data
                            for row in markup.inline_keyboard
                            for button in row
                            if button.callback_data and button.callback_data.startswith("edit_capture:")
                        ]
                        if callbacks:
                            _, table_code, record_id = callbacks[0].split(":", 2)
                            table = "income" if table_code == "i" else "transactions"
                            original = self.db.get_record(uid, table, record_id)
                            if original:
                                context.user_data["edit_capture"] = {
                                    "table": table,
                                    "record_id": record_id,
                                    "original": original,
                                }

                pending_edit = context.user_data.pop("edit_capture", None)
                if pending_edit:
                    from services.budget_handlers import _parse_indonesian_currency

                    original = pending_edit["original"]
                    if self._is_transaction_input(user_text):
                        transactions = await self.ai_service.parse_expense(user_text)
                        if len(transactions) != 1:
                            await update.message.reply_text(
                                "Kirim satu transaksi lengkap, contoh: makan siang 20 ribu."
                            )
                            return
                        transaction = transactions[0]
                        amount = int(transaction.get("amount", 0))
                        item = transaction.get("item", "")
                        category = transaction.get("category")
                    else:
                        transaction = {}
                        amount = _parse_indonesian_currency(user_text)
                        item = original.get("source", original.get("item_name", ""))
                        category = original.get("category")

                    if amount <= 0 or not item:
                        await update.message.reply_text("Item atau nominal belum valid.")
                        return

                    if pending_edit["table"] == "income":
                        new_data = {
                            "source": item,
                            "category": category or "Income",
                            "amount": amount,
                            "date": transaction.get("date") or original.get("date"),
                            "time": transaction.get("time") or original.get("time"),
                        }
                    else:
                        new_data = {
                            "item_name": item,
                            "category": category or "Other",
                            "amount": amount,
                            "date": transaction.get("date") or original.get("date"),
                            "time": transaction.get("time") or original.get("time"),
                            "location": transaction.get("location", original.get("location", "")),
                        }

                    context.user_data["pending_modification"] = {
                        "target_id": pending_edit["record_id"],
                        "action": "update",
                        "new_data": new_data,
                        "table": pending_edit["table"],
                        "original": original,
                    }
                    old_amount = int(pending_edit["original"].get("amount", 0))
                    await update.message.reply_text(
                        f"Konfirmasi perubahan\n\nRp{old_amount:,.0f} → Rp{amount:,.0f}".replace(",", "."),
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("Konfirmasi", callback_data="confirm_mod_yes"),
                            InlineKeyboardButton("Batal", callback_data="confirm_mod_no"),
                        ]]),
                    )
                    return

                # 0. Reply-to-Bot = always contextual AI chat
                if reply_context:
                    context.user_data.pop("pending_input", None)
                    status_msg = await update.message.reply_text("💭 ...")
                    response = await self.ai_service.chat_with_user(
                        user_text=user_text,
                        user_id=uid,
                        reply_context=reply_context
                    )
                    if response:
                        await context.bot.edit_message_text(
                            chat_id=chat_id, message_id=status_msg.message_id, text=response
                        )
                    else:
                        await context.bot.edit_message_text(
                            chat_id=chat_id, message_id=status_msg.message_id,
                            text="Hmm, aku agak bingung nih 😅 Coba cerita lagi dong! 💙"
                        )
                    return

                # 1. Pure Chat detection
                is_pure_chat = False
                if not any(char.isdigit() for char in user_text):
                    if self.chat_service.match_template(user_text):
                        is_pure_chat = True

                if is_pure_chat:
                    context.user_data.pop("pending_input", None)
                    from services.budget_handlers import pending_topup
                    pending_topup.pop(user_id, None)

                    response = self.chat_service.match_template(user_text)
                    if response:
                        await update.message.reply_text(response)
                    return

                # Check for pending Top Up
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
                previous_text = context.user_data.pop("pending_input", None)
                if previous_text:
                    user_text = f"{previous_text} {user_text}"
                    await update.message.reply_text(f'👌 Oke, digabung: "{user_text}"')

                # Smart Expense Query Detection (natural language + keyword)
                query_result = self.expense_query.detect(user_text)
                if query_result:
                    await self._handle_expense_query(
                        update, context, user_text, query_result
                    )
                    return

                # Smart Recommendation
                text_lower = user_text.lower().strip()
                recommendation_keywords = [
                    'rekomendasi', 'saran', 'beli apa', 'jajan apa', 'makan apa',
                    'minum apa', 'enaknya beli', 'bagusnya beli'
                ]
                if any(kw in text_lower for kw in recommendation_keywords):
                    status_msg = await update.message.reply_text("Hmm bentar ya, aku cek dulu catatan belanjamu... 🔍")
                    try:
                        all_transactions = self.db.get_all_transactions(uid)
                        current_time = datetime.now().strftime('%H:%M')
                        response = await self.ai_service.generate_smart_recommendation(
                            all_transactions, current_time, user_text
                        )
                        await context.bot.edit_message_text(
                            chat_id=chat_id, message_id=status_msg.message_id, text=response
                        )
                    except Exception as e:
                        logger.error(f"Error handling recommendation: {e}")
                        await context.bot.edit_message_text(
                            chat_id=chat_id, message_id=status_msg.message_id,
                            text="❌ Maaf, otak analisaku lagi loading lama nih. Coba lagi nanti ya! 💙"
                        )
                    return

                # Transaction modification detection
                if self._is_transaction_modification(user_text):
                    status_msg = await update.message.reply_text("🔍 Mencari transaksi yang dimaksud...")
                    try:
                        recent_txs = self.db.get_recent_transactions(uid, limit=50)
                        if not recent_txs:
                            await context.bot.edit_message_text(
                                chat_id=chat_id, message_id=status_msg.message_id,
                                text="📂 Belum ada rekam jejak transaksi nih untuk diubah/hapus. 💙"
                            )
                            return

                        # Ask AI to parse the modification intention
                        mod_result = await self.ai_service.parse_modification(user_text, recent_txs)
                        
                        action = mod_result.get("action")
                        target_id = mod_result.get("target_id")
                        
                        if action == "not_found" or not target_id:
                            await context.bot.edit_message_text(
                                chat_id=chat_id, message_id=status_msg.message_id,
                                text="🤔 Aku tidak menemukan transaksi tersebut di riwayat baru-baru ini. Boleh lebih spesifik (tanggal/harganya)?"
                            )
                            return

                        # Find original transaction from list
                        orig_tx = next((t for t in recent_txs if str(t.get("id")) == str(target_id)), None)
                        if not orig_tx:
                            await context.bot.edit_message_text(
                                chat_id=chat_id, message_id=status_msg.message_id,
                                text="🤔 Transaksi tersebut tidak ditemukan di sistem. Coba lagi!"
                            )
                            return
                            
                        # Store in pending state
                        mod_data = {
                            "action": action,
                            "target_id": orig_tx.get("id"),
                            "original": orig_tx,
                            "new_data": mod_result.get("new_data", {})
                        }
                        context.user_data["pending_modification"] = mod_data
                        
                        # Render confirmation
                        date_str = orig_tx.get('date', '')
                        item = orig_tx.get('item_name', 'Item')
                        amount = int(orig_tx.get('amount', 0))
                        amt_str = "{:,.0f}".format(amount).replace(',', '.')
                        
                        if action == "delete":
                            msg_text = f"🗑️ **Yakin mau MENGHAPUS transaksi ini?**\n\n📌 {date_str} — {item} — Rp {amt_str}"
                        elif action == "update":
                            new_data = mod_data["new_data"]
                            new_item = new_data.get("item", item)
                            new_amount = new_data.get("amount", amount)
                            new_amt_str = "{:,.0f}".format(new_amount).replace(',', '.')
                            
                            msg_text = (
                                f"✏️ **Yakin mau MENGUBAH transaksi ini?**\n\n"
                                f"**Lama:** {date_str} — {item} — Rp {amt_str}\n"
                                f"**Baru:** {new_item} — Rp {new_amt_str}"
                            )
                            
                        keyboard = [
                            [InlineKeyboardButton("[Ya]", callback_data='confirm_mod_yes'),
                             InlineKeyboardButton("[Tidak]", callback_data='confirm_mod_no')]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        await context.bot.edit_message_text(
                            chat_id=chat_id, message_id=status_msg.message_id,
                            text=msg_text, reply_markup=reply_markup, parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"Error handling transaction modification: {e}")
                        await context.bot.edit_message_text(
                            chat_id=chat_id, message_id=status_msg.message_id,
                            text="❌ Maaf, otak analisaku lagi loading lama nih. Coba lagi nanti ya! 💙"
                        )
                    return

                # Transaction detection
                if self._is_transaction_input(user_text):
                    log_event("capture_received", uid, source="text")
                    status_msg = await update.message.reply_text("⏳ Mencatat transaksi...")
                    try:
                        transactions = await self.ai_service.parse_expense(user_text)

                        if not transactions:
                            await context.bot.edit_message_text(
                                chat_id=chat_id, message_id=status_msg.message_id,
                                text="🤖 Hmm, aku ga nemu data transaksi nih atau sistem AInya lagi error. Coba lagi ya! 💙"
                            )
                            return

                        operation_id = f"{uid}:{update.message.message_id}"
                        if len(transactions) > 1:
                            await self._ask_confirmation(
                                update, context, transactions, status_msg.message_id, "Teks"
                            )
                        else:
                            await self._save_and_reply(
                                update,
                                context,
                                transactions,
                                status_msg.message_id,
                                operation_id,
                            )
                    except Exception as e:
                        logging.error(f"Error Text: {e}")
                        await context.bot.edit_message_text(
                            chat_id=chat_id, message_id=status_msg.message_id, text="❌ Error sistem."
                        )
                    return

                # Incomplete Transaction detection
                if self._is_incomplete_transaction(user_text):
                    log_event("capture_needs_clarification", uid, field="amount")
                    context.user_data["pending_input"] = user_text
                    await update.message.reply_text(
                        f'🤔 "{user_text}"... Nominalnya berapa?\n'
                        "Ketik angkanya aja, nanti aku gabungin! 😉"
                    )
                    return

                # Warm Chat
                response = self.chat_service.match_template(user_text)
                if response:
                    await update.message.reply_text(response)
                else:
                    status_msg = await update.message.reply_text("💭 ...")
                    response = await self.ai_service.chat_with_user(
                        user_text=user_text,
                        user_id=uid
                    )
                    if response:
                        await context.bot.edit_message_text(
                            chat_id=chat_id, message_id=status_msg.message_id, text=response
                        )
                    else:
                        await context.bot.edit_message_text(
                            chat_id=chat_id, message_id=status_msg.message_id,
                            text="Halo! 💙 Aku di sini kok! Ada yang mau dicatat atau ditanyain? 😊"
                        )
                return

    async def _handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """FR-02: Handle foto struk untuk OCR"""
        chat_id = update.effective_chat.id
        status_msg = await update.message.reply_text("📷 Membaca struk...")

        try:
            if update.message.photo:
                file_id = update.message.photo[-1].file_id
            else:
                file_id = update.message.document.file_id
                
            file = await context.bot.get_file(file_id)

            bio = io.BytesIO()
            await file.download_to_memory(bio)
            image_bytes = bio.getvalue()

            transactions = await self.ai_service.parse_receipt_image(image_bytes)
            await self._ask_confirmation(update, context, transactions, status_msg.message_id, "Struk OCR")
        except Exception as e:
            logging.error(f"Error Photo: {e}")
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=status_msg.message_id, text="❌ Gagal membaca struk."
            )

    async def _handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """FR-03: Handle voice message untuk Speech-to-Text"""
        chat_id = update.effective_chat.id
        status_msg = await update.message.reply_text("🎤 Mendengarkan...")

        try:
            voice = update.message.voice
            file = await context.bot.get_file(voice.file_id)

            bio = io.BytesIO()
            await file.download_to_memory(bio)
            audio_bytes = bio.getvalue()

            text = await self.ai_service.transcribe_audio(audio_bytes)
            if not text:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=status_msg.message_id, text="❌ Tidak terdengar."
                )
                return

            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=status_msg.message_id,
                text=f'🎤 "{text}"\n⏳ Memproses Data...'
            )
            transactions = await self.ai_service.parse_expense(text)
            await self._ask_confirmation(update, context, transactions, status_msg.message_id, "Voice Note")
        except Exception as e:
            logging.error(f"Error Voice: {e}")
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=status_msg.message_id, text="❌ Gagal memproses suara."
            )

    async def _ask_confirmation(self, update, context, transactions, message_id, source):
        chat_id = update.effective_chat.id
        uid = update.effective_user.id
        
        if not transactions:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=message_id,
                text="🤖 Hmm, aku ga nemu data transaksi nih. Coba lagi ya! 💙"
            )
            return

        context.user_data["pending_confirmation"] = {
            "source": source,
            "transactions": transactions,
            "operation_id": f"{uid}:{update.effective_message.message_id}",
        }

        msg_text = f"📝 **Review Hasil {source}:**\n\n"
        for i, t in enumerate(transactions):
            date_val = t.get('date', '-')
            item = t.get('item', t.get('item_name', '?'))
            amt = int(t.get('amount', 0))
            amt_str = "{:,.0f}".format(amt).replace(',', '.')
            loc = t.get('location', '-')
            
            if loc == "":
                loc = "-"
            if date_val == "":
                date_val = "-"
                
            msg_text += (
                f"📅 **DATE**       : {date_val}\n"
                f"🛒 **ITEMS**      : {item}\n"
                f"💸 **AMOUNT**     : Rp {amt_str}\n"
                f"📍 **LOCATION**   : {loc}\n"
            )
            if i < len(transactions) - 1:
                msg_text += "\n────────────────────────\n\n"

        keyboard = [
            [InlineKeyboardButton("✅ Simpan", callback_data='confirm_save_yes')],
            [InlineKeyboardButton("✏️ Edit Teks", callback_data='confirm_save_edit'),
             InlineKeyboardButton("❌ Batal", callback_data='confirm_save_no')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=message_id,
            text=msg_text, reply_markup=reply_markup, parse_mode='Markdown'
        )

    async def _handle_expense_query(self, update, context, user_text, query_result):
        """Handle a detected expense query — fetch data, AI summarize, show detail button."""
        chat_id = update.effective_chat.id
        uid = self._user_id(update)
        user_id = update.effective_user.id

        start = query_result['start']
        end = query_result['end']
        label = query_result['label']
        wants_detail = query_result.get('wants_detail', False)

        status_msg = await update.message.reply_text(f"🔍 Mengecek pengeluaran {label}...")

        try:
            transactions = self.db.get_transactions_by_date(uid, start, end)

            if not transactions:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=status_msg.message_id,
                    text=f"📂 Belum ada data pengeluaran di {label} nih! 💙"
                )
                return

            # If user explicitly asked for detail, show full list directly
            if wants_detail:
                total = 0
                report = f"📋 **Detail Pengeluaran {label}**\n\n"
                for t in transactions:
                    try:
                        amt = int(t.get('amount', 0))
                        cat = t.get('category', 'Other')
                        if str(cat).lower() in ['income', 'pemasukan', 'gaji']:
                            continue
                        total += amt
                        item = t.get('item_name', t.get('item', '?'))
                        date = t.get('date', '')
                        amt_str = "{:,.0f}".format(amt).replace(',', '.')
                        report += f"▪️ {date} — {item} — Rp{amt_str} [{cat}]\n"
                    except:
                        continue
                total_str = "{:,.0f}".format(total).replace(',', '.')
                report += f"\n💰 **Total: Rp {total_str}**"
                if len(report) > 4000:
                    report = report[:3950] + "\n\n... (terpotong, terlalu banyak data)"
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=status_msg.message_id,
                    text=report, parse_mode='Markdown'
                )
                return

            # AI Smart Summary
            summary = await self.ai_service.summarize_expenses(
                transactions, label, user_text
            )

            # Cache data for detail button
            self.pending_query_data[user_id] = (transactions, label)

            keyboard = [[InlineKeyboardButton("📋 Detail Lengkap", callback_data='expense_detail')]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=status_msg.message_id,
                text=summary, reply_markup=reply_markup
            )

        except Exception as e:
            logger.error(f"Error handling expense query: {e}")
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=status_msg.message_id,
                text="❌ Maaf, gagal mengambil data. Coba lagi nanti ya! 💙"
            )

    def _is_transaction_modification(self, text: str) -> bool:
        """Helper: Detect if input is a modification/deletion request."""
        text_lower = text.lower().strip()
        import string
        clean_text = text_lower.translate(str.maketrans('', '', string.punctuation)).strip()
        words = clean_text.split()
        
        modification_keywords = ['hapus', 'ubah', 'ganti', 'salah', 'ralat', 'bukan']
        has_mod_keyword = any(kw in words for kw in modification_keywords)
        
        # Must have at least a mod keyword and another context word, avoiding pure chat or questions
        is_question = any(q in words for q in ['apa', 'kenapa', 'bagaimana', 'gimana', 'mengapa'])
        return len(words) >= 2 and has_mod_keyword and not is_question

    def _is_transaction_input(self, text: str) -> bool:
        """Helper: Deteksi apakah input adalah transaksi atau pertanyaan/chat biasa."""
        text_lower = text.lower().strip()
        import string
        clean_text = text_lower.translate(str.maketrans('', '', string.punctuation)).strip()
        words = clean_text.split()

        chat_expressions = [
            'terima kasih', 'terimakasih', 'makasih', 'makasi', 'thanks', 'tq',
            'oke', 'ok', 'sip', 'mantap', 'iya', 'y', 'halo', 'hai', 'hello',
            'pagi', 'siang', 'sore', 'malam'
        ]

        if len(words) <= 3 and any(cw in clean_text for cw in chat_expressions):
            if not any(char.isdigit() for char in text):
                return False

        question_words = [
            'apa', 'kenapa', 'gimana', 'bagaimana', 'mengapa',
            'kapan', 'siapa', 'dimana', 'berapa', 'apakah',
            'mana', 'tolong', 'help', 'bantuan', 'ini apa'
        ]

        if len(text_lower) < 5 and not any(char.isdigit() for char in text_lower):
            return False

        for q in question_words:
            if text_lower.startswith(q):
                return False

        transaction_keywords = [
            'beli', 'bayar', 'belanja', 'buat', 'untuk',
            'makan', 'bensin', 'isi', 'parkir', 'transport',
            'pulsa', 'token', 'internet', 'bills', 'tagihan',
            'rb', 'ribu', 'jt', 'juta', 'rp', 'rupiah',
            'k', 'gaji', 'masuk', 'income',
            'dapat', 'terima', 'uang', 'transfer', 'jual'
        ]

        has_number = any(char.isdigit() for char in text)
        has_transaction_keyword = any(kw in words for kw in transaction_keywords)
        if not has_transaction_keyword:
            has_transaction_keyword = any(kw in text_lower for kw in ['ribu', 'rb', 'juta', 'jt', 'rupiah', 'rp', 'k '])

        strong_keywords = ['beli', 'bayar', 'belanja', 'gaji', 'income', 'dapat', 'terima']
        has_strong_keyword = any(kw in words for kw in strong_keywords)

        return (has_number and has_transaction_keyword) or has_strong_keyword

    def _is_incomplete_transaction(self, text: str) -> bool:
        """Helper: Cek apakah text terlihat seperti transaksi tapi tanpa nominal uang."""
        text_lower = text.lower().strip()
        import string
        clean_text = text_lower.translate(str.maketrans('', '', string.punctuation)).strip()
        words = clean_text.split()

        chat_expressions = [
            'terima kasih', 'terimakasih', 'makasih', 'makasi', 'thanks', 'tq',
            'oke', 'ok', 'sip', 'mantap', 'iya', 'y', 'halo', 'hai', 'hello',
            'pagi', 'siang', 'sore', 'malam', 'maksudnya'
        ]
        if len(words) <= 3 and any(cw in clean_text for cw in chat_expressions):
            return False

        keywords = [
            'beli', 'bayar', 'belanja', 'makan', 'minum', 'jajan',
            'isi', 'topup', 'tagihan', 'gaji', 'dapat', 'terima',
            'uang', 'income', 'transfer', 'jual'
        ]

        has_keyword = any(kw in words for kw in keywords)
        has_number = any(char.isdigit() for char in text)
        is_question = any(q in words for q in ['apa', 'dimana', 'kapan', 'tanya', 'siapa', 'gimana'])

        return has_keyword and not has_number and not is_question and len(text) > 3

    # ─── DATA HELPERS ───────────────────────────────────────

    def _calculate_balance(self, uid: str):
        """Calculate total income, expenses, and balance from Supabase."""
        transactions = self.db.get_all_transactions(uid)
        income_rows = self.db.get_income(uid)

        total_income = sum(int(r.get("amount", 0)) for r in income_rows)
        total_expense = sum(int(t.get("amount", 0)) for t in transactions)

        return total_income, total_expense, total_income - total_expense

    def _calculate_balance_since_last_income(self, uid: str):
        """
        Calculate balance starting from the date of the LAST income transaction.
        Returns: (total_income, total_expense, balance, start_date)
        """
        income_rows = self.db.get_income(uid)  # newest first

        # Find last income date
        if income_rows:
            start_date_str = income_rows[0].get("date", "")
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            except ValueError:
                start_date = datetime(datetime.now().year, datetime.now().month, 1)
        else:
            today = datetime.now()
            start_date = datetime(today.year, today.month, 1)

        start_str = start_date.strftime("%Y-%m-%d")
        end_str = datetime.now().strftime("%Y-%m-%d")

        # Income since start
        filtered_income = sum(
            int(r.get("amount", 0)) for r in income_rows
            if r.get("date", "") >= start_str
        )

        # Expenses since start
        expense_rows = self.db.get_transactions_by_date(uid, start_str, end_str)
        filtered_expense = sum(int(t.get("amount", 0)) for t in expense_rows)

        return filtered_income, filtered_expense, filtered_income - filtered_expense, start_date

    # ─── SAVE & REPLY ───────────────────────────────────────

    async def _save_and_reply(
        self, update, context, transactions, message_id, operation_id=None
    ):
        """Save one transaction type and render a database-confirmed receipt."""
        chat_id = update.effective_chat.id
        uid = self._user_id(update)
        operation_id = operation_id or f"{uid}:{update.effective_message.message_id}"

        if not transactions:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=message_id,
                text="🤖 Hmm, aku ga nemu data transaksi nih. Coba lagi ya! 💙"
            )
            return

        income_flags = [
            str(t.get('category', '')).lower() in ['income', 'pemasukan', 'gaji']
            for t in transactions
        ]
        if any(income_flags) and not all(income_flags):
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Belum tersimpan\n\nPisahkan pemasukan dan pengeluaran ke pesan berbeda.",
            )
            return

        is_income_batch = all(income_flags)

        if is_income_batch:
            result = self.db.add_income(uid, [
                {
                    "source": t.get("item", ""),
                    "category": t.get("category", "Income"),
                    "amount": t.get("amount", 0),
                    "date": t.get("date", ""),
                    "time": t.get("time", ""),
                    "notes": t.get("notes", ""),
                } for t in transactions
            ], operation_id)
            table_code = "i"
        else:
            result = self.db.add_transactions_bulk(uid, transactions, operation_id)
            table_code = "e"

        if not result["ok"]:
            log_event("capture_failed", uid, reason=result["error"])
            context.user_data["retry_capture"] = {
                "transactions": transactions,
                "operation_id": operation_id,
            }
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="Belum tersimpan\n\nKoneksi sedang bermasalah. Datamu belum masuk.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Coba Lagi", callback_data="retry_capture")
                ]]),
            )
            return

        context.user_data.pop("retry_capture", None)
        log_event("capture_saved", uid, count=len(result["records"]))
        reply_text = "Tersimpan\n\n"

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
                item_line = item
                detail_line = f"{category} · +Rp{amt_str}"
            else:
                total_expense_now += amount
                item_line = item
                detail_line = f"{category} · Rp{amt_str}"

            reply_text += f"{item_line}\n{detail_line}\n\n"

        reply_text += "────────────\n"
        if total_income_now > 0:
            reply_text += f"Pemasukan Rp{total_income_now:,.0f}".replace(',', '.') + "\n"
        if total_expense_now > 0:
            reply_text += f"Pengeluaran Rp{total_expense_now:,.0f}".replace(',', '.') + "\n"

        first_record = result["records"][0]
        edit_callback = f"edit_capture:{table_code}:{first_record.get('id', '')}"
        keyboard = [
            [InlineKeyboardButton(
                "Batalkan", callback_data=f"undo_capture:{table_code}:{operation_id}"
            )],
            [InlineKeyboardButton("Edit", callback_data=edit_callback)],
        ]

        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=message_id,
            text=reply_text, reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ─── MENUS & REPORTS ────────────────────────────────────

    async def handle_summary(self, update, context):
        """Show deterministic current-month income, expense, and cash flow."""
        uid = self._user_id(update)
        today = datetime.now()
        start = today.strftime("%Y-%m-01")
        end = today.strftime("%Y-%m-%d")
        month_names = (
            "Januari", "Februari", "Maret", "April", "Mei", "Juni",
            "Juli", "Agustus", "September", "Oktober", "November", "Desember",
        )
        label = f"{month_names[today.month - 1]} {today.year}"
        summary = self.analytics_service.get_unified_summary(
            self.db.get_transactions_by_date(uid, start, end),
            self.db.get_income(uid),
            start,
            end,
            label,
        )
        log_event("summary_viewed", uid, period=start[:7])
        await update.message.reply_text(
            self.analytics_service.format_unified_summary_message(summary),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Detail", callback_data="laporan_bulanan"),
                InlineKeyboardButton("Trend", callback_data="summary_trend"),
                InlineKeyboardButton("PDF", callback_data="summary_pdf"),
            ]]),
        )

    async def handle_history(self, update, context):
        """Show recent income and expenses without an AI call."""
        rows = self.history_service.recent(self._user_id(update), limit=10)
        if not rows:
            await update.message.reply_text("Belum ada transaksi.")
            return

        keyboard = []
        for row in rows:
            sign = "+" if row["type"] == "income" else "-"
            amount = f"{int(row.get('amount', 0)):,.0f}".replace(",", ".")
            table_code = "i" if row["table"] == "income" else "e"
            keyboard.append([InlineKeyboardButton(
                f"{row['item']} · {sign}Rp{amount}",
                callback_data=f"history:{table_code}:{row['id']}",
            )])

        await update.message.reply_text(
            "Riwayat Terakhir", reply_markup=InlineKeyboardMarkup(keyboard)
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
        uid = str(update.effective_user.id)

        if not auth_svc.is_allowed(update.effective_user.id):
            await query.answer("⛔ Akses ditolak. Bot ini privat.", show_alert=True)
            return

        await query.answer()
        action = query.data

        # Handle report period selection
        if action.startswith('laporan_'):
            period_type = action.replace('laporan_', '')
            await query.edit_message_text("⏳ Mengambil data...")
            await self._send_report_to_callback(query, context, period_type, uid)
            return

        if action == "summary_trend":
            await self.handle_trend_chart(update, context)
            return

        if action == "summary_pdf":
            await self.handle_export_pdf(update, context)
            return

        if action.startswith("goal_add:") or action.startswith("goal_withdraw:"):
            operation, goal_id = action.split(":", 1)
            context.user_data["goal_action"] = {
                "action": "contribute" if operation == "goal_add" else "withdraw",
                "goal_id": int(goal_id),
            }
            await query.edit_message_text("Nominalnya berapa?")
            return

        if action.startswith("goal_history:"):
            goal_id = int(action.split(":", 1)[1])
            history = self.db.get_goal_history(uid, goal_id)
            if not history:
                await query.edit_message_text("Belum ada riwayat goal.")
                return
            lines = ["Riwayat Goal", ""]
            labels = {"created": "Dibuat", "contribute": "Tambah", "withdraw": "Ambil", "cancelled": "Dibatalkan"}
            for entry in history:
                delta = int(entry.get("amount_delta", 0))
                balance = int(entry.get("balance_after", 0))
                lines.append(
                    f"{labels.get(entry.get('action'), entry.get('action', ''))} "
                    f"{delta:+,} · Rp{balance:,}".replace(",", ".")
                )
            await query.edit_message_text("\n".join(lines))
            return

        # Handle transaction modification confirmation
        if action.startswith('confirm_mod_'):
            user_id = update.effective_user.id
            if "pending_modification" not in context.user_data:
                await query.edit_message_text("⚠️ Sesi kadaluarsa. Silakan ulangi perintah ubah/hapus.")
                return

            mod_data = context.user_data.pop("pending_modification")
            
            if action == 'confirm_mod_no':
                await query.edit_message_text("❌ Aksi dibatalkan.")
                return
                
            if action == 'confirm_mod_yes':
                await query.edit_message_text("⏳ Memproses permintaan...")
                try:
                    target_id = mod_data["target_id"]
                    mod_action = mod_data["action"]
                    
                    if mod_action == "delete":
                        success = self.db.delete_transaction(uid, target_id)
                        if success:
                            await query.edit_message_text("✅ Transaksi berhasil **dihapus**!", parse_mode='Markdown')
                        else:
                            await query.edit_message_text("❌ Gagal menghapus transaksi.")
                            
                    elif mod_action == "update":
                        new_data = mod_data["new_data"]
                        if mod_data.get("table") == "income":
                            success = self.db.update_income(uid, target_id, new_data)
                        else:
                            success = self.db.update_transaction(uid, target_id, new_data)
                        if success:
                            log_event(
                                "transaction_edited",
                                uid,
                                table=mod_data.get("table", "transactions"),
                            )
                            await query.edit_message_text("✅ Transaksi berhasil **diubah**!", parse_mode='Markdown')
                        else:
                            await query.edit_message_text("❌ Gagal mengubah transaksi.")
                except Exception as e:
                    logger.error(f"Error executing transaction modification: {e}")
                    await query.edit_message_text("❌ Terjadi kesalahan saat memproses data.")
            return

        # Handle Save Confirmation (OCR & Voice)
        if action.startswith('confirm_save_'):
            user_id = update.effective_user.id
            if "pending_confirmation" not in context.user_data:
                await query.edit_message_text("⚠️ Sesi kadaluarsa. Silakan ulangi input.")
                return

            if action == 'confirm_save_no':
                context.user_data.pop("pending_confirmation")
                await query.edit_message_text("❌ Aksi dibatalkan.")
                return
                
            data = context.user_data.pop("pending_confirmation")
            transactions = data['transactions']
            
            if action == 'confirm_save_edit':
                items = [t.get("item", t.get("item_name", "")) for t in transactions]
                context.user_data["pending_input"] = f"Dari hasil scan ({', '.join(items)}): "
                await query.edit_message_text("✏️ Oke, ketik ulang transaksinya beserta nominal yang benar ya!")
                return
                
            if action == 'confirm_save_yes':
                await query.edit_message_text("⏳ Menyimpan transaksi...")
                await self._save_and_reply(
                    update,
                    context,
                    transactions,
                    query.message.message_id,
                    data["operation_id"],
                )
                return

        if action == "retry_capture":
            pending = context.user_data.get("retry_capture")
            if not pending:
                await query.edit_message_text("Sesi coba lagi sudah berakhir. Kirim transaksi kembali.")
                return
            await query.edit_message_text("Memproses ulang...")
            await self._save_and_reply(
                update,
                context,
                pending["transactions"],
                query.message.message_id,
                pending["operation_id"],
            )
            return

        if action.startswith("undo_capture:"):
            _, table_code, operation_id = action.split(":", 2)
            table = "income" if table_code == "i" else "transactions"
            if self.db.delete_operation(uid, table, operation_id):
                log_event("capture_undone", uid, table=table)
                await query.edit_message_text("Dibatalkan")
            else:
                await query.edit_message_text("Transaksi sudah dibatalkan atau tidak ditemukan.")
            return

        if action.startswith("edit_capture:"):
            _, table_code, record_id = action.split(":", 2)
            table = "income" if table_code == "i" else "transactions"
            original = self.db.get_record(uid, table, record_id)
            if not original:
                await query.edit_message_text("Transaksi tidak ditemukan.")
                return
            context.user_data["edit_capture"] = {
                "table": table,
                "record_id": record_id,
                "original": original,
            }
            await query.edit_message_text(
                "Kirim ulang transaksi lengkap dengan nilai yang benar."
            )
            return

        if action.startswith("history:"):
            _, table_code, record_id = action.split(":", 2)
            table = "income" if table_code == "i" else "transactions"
            record = self.db.get_record(uid, table, record_id)
            if not record:
                await query.edit_message_text("Transaksi tidak ditemukan.")
                return
            item = record.get("source", record.get("item_name", ""))
            amount = f"{int(record.get('amount', 0)):,.0f}".replace(",", ".")
            await query.edit_message_text(
                f"{item} · Rp{amount}\n{record.get('category', 'Other')} · {record.get('date', '')}",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("Edit", callback_data=f"edit_capture:{table_code}:{record_id}"),
                        InlineKeyboardButton("Hapus", callback_data=f"history_delete:{table_code}:{record_id}"),
                    ],
                    [InlineKeyboardButton("Catat Lagi", callback_data=f"history_repeat:{table_code}:{record_id}")],
                ]),
            )
            return

        if action.startswith("history_delete:"):
            _, table_code, record_id = action.split(":", 2)
            context.user_data["history_delete"] = (table_code, record_id)
            await query.edit_message_text(
                "Hapus transaksi ini?",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Hapus", callback_data="history_delete_confirm"),
                    InlineKeyboardButton("Batal", callback_data="history_delete_cancel"),
                ]]),
            )
            return

        if action == "history_delete_cancel":
            context.user_data.pop("history_delete", None)
            await query.edit_message_text("Penghapusan dibatalkan.")
            return

        if action == "history_delete_confirm":
            pending = context.user_data.pop("history_delete", None)
            if not pending:
                await query.edit_message_text("Sesi hapus sudah berakhir.")
                return
            table_code, record_id = pending
            success = (
                self.db.delete_income(uid, record_id)
                if table_code == "i"
                else self.db.delete_transaction(uid, record_id)
            )
            await query.edit_message_text("Dihapus" if success else "Transaksi tidak ditemukan.")
            return

        if action.startswith("history_repeat:"):
            _, table_code, record_id = action.split(":", 2)
            table = "income" if table_code == "i" else "transactions"
            record = self.db.get_record(uid, table, record_id)
            if not record:
                await query.edit_message_text("Transaksi tidak ditemukan.")
                return
            transaction = {
                "item": record.get("source", record.get("item_name", "")),
                "category": record.get("category", "Income" if table_code == "i" else "Other"),
                "amount": int(record.get("amount", 0)),
                "date": datetime.now().date().isoformat(),
                "time": datetime.now().strftime("%H:%M"),
                "location": record.get("location", ""),
            }
            await query.edit_message_text("Mencatat ulang...")
            await self._save_and_reply(
                update,
                context,
                [transaction],
                query.message.message_id,
                f"{uid}:repeat:{query.message.message_id}:{record_id}",
            )
            return

        # Handle Expense Detail button
        if action == 'expense_detail':
            user_id = update.effective_user.id
            cached = self.pending_query_data.pop(user_id, None)
            if cached:
                transactions, label = cached
                total = 0
                report = f"📋 **Detail Pengeluaran {label}**\n\n"
                for t in transactions:
                    try:
                        amt = int(t.get('amount', 0))
                        cat = t.get('category', 'Other')
                        if str(cat).lower() in ['income', 'pemasukan', 'gaji']:
                            continue
                        total += amt
                        item = t.get('item_name', t.get('item', '?'))
                        date = t.get('date', '')
                        amt_str = "{:,.0f}".format(amt).replace(',', '.')
                        report += f"▪️ {date} — {item} — Rp{amt_str} [{cat}]\n"
                    except:
                        continue
                total_str = "{:,.0f}".format(total).replace(',', '.')
                report += f"\n💰 **Total: Rp {total_str}**"

                # Telegram has 4096 char limit
                if len(report) > 4000:
                    report = report[:3950] + "\n\n... (terpotong, terlalu banyak data)"

                await query.edit_message_text(report, parse_mode='Markdown')
            else:
                await query.edit_message_text("⚠️ Data sudah kadaluarsa. Tanya lagi ya! 💙")
            return

        if action.startswith(('income_', 'src_')):
            await query.edit_message_text("Flow lama sudah berakhir. Kirim transaksinya kembali.")
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
                keyboard.append([InlineKeyboardButton(
                    f"📂 {cat.capitalize()} (Rp {limit_str})",
                    callback_data=f'budget_topup_select_{cat}'
                )])
            keyboard.append([InlineKeyboardButton("🔙 Batal", callback_data='budget_topup_cancel')])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("➕ **Pilih budget untuk Top Up:**", reply_markup=reply_markup, parse_mode='Markdown')
            return

        if action.startswith('budget_topup_select_'):
            user_id = update.effective_user.id
            category = action.replace('budget_topup_select_', '')

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
                keyboard.append([InlineKeyboardButton(
                    f"🗑️ {cat.capitalize()} (Rp {limit_str})",
                    callback_data=f'budget_delete_select_{cat}'
                )])
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
                reply_markup=reply_markup, parse_mode='Markdown'
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

        # AI analysis handling
        self.db.get_all_transactions(uid)
        filtered_data = []
        today = datetime.now()
        period_label = ""

        if action == 'analisis_minggu':
            start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
            end = today.strftime("%Y-%m-%d")
            filtered_data = self.db.get_transactions_by_date(uid, start, end)
            period_label = "7 Hari Terakhir"

        elif action == 'analisis_bulan':
            start = today.strftime("%Y-%m-01")
            end = today.strftime("%Y-%m-%d")
            filtered_data = self.db.get_transactions_by_date(uid, start, end)
            period_label = "Bulan Ini"

        await query.edit_message_text(f"⏳ Sedang menganalisis data {period_label}...")

        clean_data = [
            {
                "Date": item.get("date"),
                "Item Name": item.get("item_name"),
                "Category": item.get("category"),
                "Amount (IDR)": item.get("amount"),
            }
            for item in filtered_data
        ]

        report = self.ai_service.analyze_expenses(clean_data, period_label)
        await query.edit_message_text(text=report)

    async def _send_report_to_callback(self, query, context, type_report, uid: str):
        """Send report via callback query — data from Supabase."""
        today = datetime.now()

        if type_report == 'harian':
            start = end = today.strftime("%Y-%m-%d")
            period_label = "Hari Ini"
        elif type_report == 'mingguan':
            start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
            end = today.strftime("%Y-%m-%d")
            period_label = "Minggu Ini"
        elif type_report == 'bulanan':
            start = today.strftime("%Y-%m-01")
            end = today.strftime("%Y-%m-%d")
            period_label = "Bulan Ini"
        else:
            return

        filtered_data = self.db.get_transactions_by_date(uid, start, end)

        if not filtered_data:
            await query.edit_message_text(f"📂 Data {period_label} kosong.")
            return

        total = 0
        report = f"📂 **Laporan {period_label}**\n\n"
        for t in filtered_data[-15:]:
            try:
                amt = int(t.get("amount", 0))
                total += amt
                amt_str = "{:,.0f}".format(amt).replace(',', '.')
                report += f"▪️ {t.get('item_name', '?')} - Rp{amt_str}\n"
            except:
                pass

        total_str = "{:,.0f}".format(total).replace(',', '.')
        report += f"\n💰 **Total: Rp {total_str}**"
        await query.edit_message_text(report, parse_mode='Markdown')

    async def process_report(self, update, context, type_report):
        """Helper Laporan Biasa (Non-AI) — data from Supabase."""
        uid = self._user_id(update)
        await update.message.reply_text("⏳ Mengambil data...")
        today = datetime.now()

        if type_report == 'harian':
            start = end = today.strftime("%Y-%m-%d")
            period_label = "Hari Ini"
        elif type_report == 'mingguan':
            start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
            end = today.strftime("%Y-%m-%d")
            period_label = "Minggu Ini"
        elif type_report == 'bulanan':
            start = today.strftime("%Y-%m-01")
            end = today.strftime("%Y-%m-%d")
            period_label = "Bulan Ini"
        else:
            return

        filtered_data = self.db.get_transactions_by_date(uid, start, end)

        if not filtered_data:
            await update.message.reply_text(f"📂 Data {period_label} kosong.")
            return

        total = 0
        report = f"📂 **Laporan {period_label}**\n\n"
        for t in filtered_data[-15:]:
            try:
                amt = int(t.get("amount", 0))
                total += amt
                amt_str = "{:,.0f}".format(amt).replace(',', '.')
                report += f"▪️ {t.get('item_name', '?')} - Rp{amt_str}\n"
            except:
                pass

        total_str = "{:,.0f}".format(total).replace(',', '.')
        report += f"\n💰 **Total: Rp {total_str}**"
        await update.message.reply_text(report, parse_mode='Markdown')

    async def handle_saldo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle Saldo button — show balance since last income."""
        uid = self._user_id(update)
        await update.message.reply_text("⏳ Menghitung sisa uang...")

        total_income, total_expense, balance, start_date = self._calculate_balance_since_last_income(uid)

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
        """Handle Coaching AI button — generate weekly coaching report."""
        uid = self._user_id(update)
        await update.message.reply_text("🧠 Generating AI coaching insights...")

        try:
            today = datetime.now()
            week_start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
            prev_week_start = (today - timedelta(days=14)).strftime("%Y-%m-%d")
            today_str = today.strftime("%Y-%m-%d")

            current_week = self.db.get_transactions_by_date(uid, week_start, today_str)
            previous_week = self.db.get_transactions_by_date(uid, prev_week_start, week_start)

            report_data = self.coaching_engine.generate_weekly_report(current_week, previous_week)
            message = self.coaching_engine.format_weekly_report_message(report_data)
            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logging.error(f"Error generating coaching report: {e}")
            await update.message.reply_text("❌ Gagal menghasilkan laporan coaching. Coba lagi nanti.")

    async def handle_dashboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle Dashboard button — show analytics dashboard."""
        uid = self._user_id(update)
        await update.message.reply_text("📊 Loading dashboard...")

        try:
            all_data = self.db.get_all_transactions(uid)

            dashboard = self.analytics_service.get_dashboard_data(all_data, period_days=30)
            message = self.analytics_service.format_dashboard_message(dashboard, "30 Hari Terakhir")
            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logging.error(f"Error generating dashboard: {e}")
            await update.message.reply_text("❌ Gagal memuat dashboard. Coba lagi nanti.")

    async def handle_export_pdf(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle Export PDF button — generate and send PDF report."""
        uid = self._user_id(update)
        message = update.effective_message

        if not self.export_service.is_available():
            await message.reply_text(
                "⚠️ PDF export belum tersedia.\n"
                "Install: `pip install reportlab matplotlib`",
                parse_mode='Markdown'
            )
            return

        await message.reply_text("📄 Generating PDF report...")

        try:
            today = datetime.now()
            month_start = today.strftime("%Y-%m-01")
            month_end = today.strftime("%Y-%m-%d")

            monthly_data = self.db.get_transactions_by_date(uid, month_start, month_end)

            dashboard = self.analytics_service.get_dashboard_data(monthly_data, period_days=30)
            coaching_report = self.coaching_engine.generate_weekly_report(monthly_data, [])

            pdf_bytes = self.export_service.generate_monthly_report(
                transactions=monthly_data,
                category_breakdown=dashboard['category_distribution'],
                summary=dashboard['summary'],
                coaching_tips=coaching_report.get('tips', []),
                period_label=f"Bulan {today.strftime('%B %Y')}"
            )

            if pdf_bytes:
                await message.reply_document(
                    document=io.BytesIO(pdf_bytes),
                    filename=f"Laporan_Keuangan_{today.strftime('%Y_%m')}.pdf",
                    caption="📊 Laporan Keuangan Bulanan\nGenerated by Benny AI 🤖"
                )
            else:
                await message.reply_text("❌ Gagal membuat PDF. Coba lagi nanti.")

        except Exception as e:
            logging.error(f"Error generating PDF: {e}")
            await message.reply_text("❌ Gagal menghasilkan PDF. Coba lagi nanti.")

    async def handle_trend_chart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle Trend button — show spending trend chart."""
        uid = self._user_id(update)
        response_message = update.effective_message
        await response_message.reply_text("📈 Analyzing trends...")

        try:
            all_data = self.db.get_all_transactions(uid)

            dashboard = self.analytics_service.get_dashboard_data(all_data, period_days=14)

            chart_message = self.analytics_service.generate_trend_chart_text(
                dashboard['trends'], "TREND PENGELUARAN 14 HARI"
            )

            summary = dashboard['summary']
            daily_avg = dashboard['daily_average']

            message = f"{chart_message}\n\n"
            message += "━━━━━━━━━━━━━━━━━━━━\n"
            message += f"📊 Total 14 Hari: Rp {summary['total_expense']:,}\n".replace(',', '.')
            message += f"📅 Rata-rata Harian: Rp {daily_avg:,}\n".replace(',', '.')

            if dashboard.get('comparison'):
                comp = dashboard['comparison']
                message += f"📈 vs Periode Lalu: {comp['trend']} ({comp['change_percent']}%)"

            await response_message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logging.error(f"Error generating trend: {e}")
            await response_message.reply_text("❌ Gagal menghasilkan trend. Coba lagi nanti.")
