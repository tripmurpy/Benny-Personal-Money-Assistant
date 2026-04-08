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
        self.pending_expenses = {}  # user_id -> transactions
        self.pending_inputs = {}    # user_id -> text for incomplete transactions
        self.pending_income = {}    # user_id -> transactions for income tagging
        self.pending_query_data = {}  # user_id -> (transactions, label) for detail button
        logger.info("✅ Benny siap! (Text, OCR, Voice, AI Coaching)")

    def _user_id(self, update: Update) -> str:
        """Extract user_id as string for Supabase queries."""
        return str(update.effective_user.id)

    def _main_keyboard(self):
        """Return the main bot keyboard after successful login."""
        keyboard = [
            [KeyboardButton("💵 Saldo"), KeyboardButton("📊 Laporan")],
            [KeyboardButton("🧠 Coaching"), KeyboardButton("📄 Export PDF")],
            [KeyboardButton("🎯 Goals"), KeyboardButton("💰 Budgets"), KeyboardButton("📈 Trend")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Entry point: reset auth state and show secure login prompt.
        """
        # Reset auth for every /start
        auth_svc.init_auth(context.user_data)

        await update.message.reply_text(
            auth_svc.WELCOME_MSG,
            parse_mode="Markdown"
        )

    async def _handle_auth_flow(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Auth + Onboarding state machine.
        Called by handle_message() when user is not yet AUTHENTICATED.
        """
        uid       = self._user_id(update)
        ud        = context.user_data
        state     = auth_svc.get_state(ud)
        text      = (update.message.text or "").strip()
        chat_id   = update.effective_chat.id

        # Guard: only accept text messages during auth/onboarding
        if not text:
            await update.message.reply_text(
                "🔐 Sedang dalam proses login. Tolong ketik teks ya!"
            )
            return

        # ── STEP 1: Receive Username ─────────────────────────────────────────
        if state == auth_svc.STATE_WAITING_USERNAME:
            ud["auth_temp"]["username"] = text
            ud["auth_state"] = auth_svc.STATE_WAITING_PASSWORD
            await update.message.reply_text(auth_svc.ASK_PASSWORD_MSG, parse_mode="Markdown")
            return

        # ── STEP 2: Receive Password & Verify ────────────────────────────────
        if state == auth_svc.STATE_WAITING_PASSWORD:
            username = ud["auth_temp"].get("username", "")
            ok = auth_svc.verify_credentials(username, text)

            if not ok:
                ud["auth_attempts"] = ud.get("auth_attempts", 0) + 1
                attempt = ud["auth_attempts"]

                if attempt >= auth_svc.MAX_ATTEMPTS:
                    ud["auth_state"] = "LOCKED"
                    await update.message.reply_text(auth_svc.LOCKED_MSG, parse_mode="Markdown")
                else:
                    # Reset to username step
                    ud["auth_state"] = auth_svc.STATE_WAITING_USERNAME
                    ud["auth_temp"] = {}
                    await update.message.reply_text(
                        auth_svc.WRONG_CREDS_MSG.format(
                            attempt=attempt,
                            max=auth_svc.MAX_ATTEMPTS
                        ),
                        parse_mode="Markdown"
                    )
                return

            # ✅ Credentials OK — check if profile exists
            profile = self.db.get_user(uid)
            has_profile = bool(
                profile
                and profile.get("full_name")
                and profile.get("nickname")
            )

            # Register basic user info
            self.db.upsert_user(uid, {
                "username": update.effective_user.username or "",
                "first_name": update.effective_user.first_name or "",
            })

            if has_profile:
                # Returning user — show profile summary
                ud["auth_state"] = auth_svc.STATE_PROFILE_REVIEW
                msg = auth_svc.LOGIN_SUCCESS_RETURNING_MSG.format(
                    full_name=profile.get("full_name", "-"),
                    nickname=profile.get("nickname", "-"),
                    birthday=profile.get("birthday", "-"),
                )
                await update.message.reply_text(msg, parse_mode="Markdown")
            else:
                # New user — start onboarding
                ud["auth_state"] = auth_svc.STATE_ONBOARDING_NAME
                await update.message.reply_text(
                    auth_svc.LOGIN_SUCCESS_NEW_MSG, parse_mode="Markdown"
                )
            return

        # ── STEP 3: Profile Review (returning user) ──────────────────────────
        if state == auth_svc.STATE_PROFILE_REVIEW:
            if text.lower() in ["ya", "y", "iya", "yes", "update"]:
                ud["auth_state"] = auth_svc.STATE_ONBOARDING_NAME
                await update.message.reply_text(
                    "📝 Oke! Siapa *nama lengkap* kamu?", parse_mode="Markdown"
                )
            else:
                # User doesn't want to update — go straight to bot
                auth_svc.set_authenticated(ud)
                profile = self.db.get_user(uid)
                nickname = profile.get("nickname", update.effective_user.first_name) if profile else update.effective_user.first_name
                await update.message.reply_text(
                    f"Sip! Selamat datang kembali, *{nickname}*! 💙\nAda yang mau dicatat hari ini? 💰",
                    reply_markup=self._main_keyboard(),
                    parse_mode="Markdown"
                )
            return

        # ── STEP 4: Onboarding — Full Name ───────────────────────────────────
        if state == auth_svc.STATE_ONBOARDING_NAME:
            ud["auth_temp"]["full_name"] = text
            ud["auth_state"] = auth_svc.STATE_ONBOARDING_NICKNAME
            await update.message.reply_text(
                auth_svc.ASK_NICKNAME_MSG.format(name=text),
                parse_mode="Markdown"
            )
            return

        # ── STEP 5: Onboarding — Nickname ────────────────────────────────────
        if state == auth_svc.STATE_ONBOARDING_NICKNAME:
            ud["auth_temp"]["nickname"] = text
            ud["auth_state"] = auth_svc.STATE_ONBOARDING_BIRTHDAY
            await update.message.reply_text(
                auth_svc.ASK_BIRTHDAY_MSG.format(nickname=text),
                parse_mode="Markdown"
            )
            return

        # ── STEP 6: Onboarding — Birthday → Save & Done ──────────────────────
        if state == auth_svc.STATE_ONBOARDING_BIRTHDAY:
            full_name = ud["auth_temp"].get("full_name", "")
            nickname  = ud["auth_temp"].get("nickname", "")
            birthday  = text

            self.db.save_user_profile(uid, full_name, nickname, birthday)
            auth_svc.set_authenticated(ud)

            await update.message.reply_text(
                auth_svc.PROFILE_SAVED_MSG.format(
                    full_name=full_name,
                    nickname=nickname,
                    birthday=birthday,
                ),
                reply_markup=self._main_keyboard(),
                parse_mode="Markdown"
            )
            return

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ROUTER UTAMA: Menangani TEKS, FOTO, dan SUARA."""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        uid = str(user_id)
        if str(chat_id) != str(Config.ADMIN_ID):
            return

        self.last_activity = datetime.now()

        # ── Auth Gate: route to auth flow if not authenticated ────────────────
        if not auth_svc.is_authenticated(context.user_data):
            state = auth_svc.get_state(context.user_data)
            if state == "LOCKED":
                await update.message.reply_text(
                    "🚫 Sesi terkunci. Ketik /start untuk mencoba kembali."
                )
                return
            await self._handle_auth_flow(update, context)
            return

        # Ensure user profile exists before processing any transactions
        self.db.upsert_user(uid, {
            "username": update.effective_user.username or "",
            "first_name": update.effective_user.first_name or "",
        })

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
                # 0. Reply-to-Bot = always contextual AI chat
                if reply_context:
                    self.pending_inputs.pop(user_id, None)
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
                    self.pending_inputs.pop(user_id, None)
                    self.pending_expenses.pop(user_id, None)
                    self.pending_income.pop(user_id, None)
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
                if user_id in self.pending_inputs:
                    previous_text = self.pending_inputs.pop(user_id)
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

                # Transaction detection
                if self._is_transaction_input(user_text):
                    status_msg = await update.message.reply_text("⏳ Mencatat transaksi...")
                    try:
                        transactions = await self.ai_service.parse_expense(user_text)

                        # Check for Income
                        has_income = any(
                            str(t.get('category', '')).lower() in ['income', 'pemasukan', 'gaji']
                            for t in transactions
                        )

                        if has_income:
                            self.pending_income[user_id] = transactions
                            keyboard = [
                                [InlineKeyboardButton(" PRIMER (Wajib/Utama)", callback_data='income_primer')],
                                [InlineKeyboardButton(" SEKUNDER (Tambahan)", callback_data='income_sekunder')]
                            ]
                            reply_markup = InlineKeyboardMarkup(keyboard)
                            await context.bot.edit_message_text(
                                chat_id=chat_id, message_id=status_msg.message_id,
                                text="💰 **Mendapat Pemasukan!**\n\nIni termasuk jenis apa?",
                                reply_markup=reply_markup, parse_mode='Markdown'
                            )
                        else:
                            self.pending_expenses[user_id] = transactions

                            first_cat = transactions[0].get('category', '').lower()
                            budgets = self.budget_service.get_budgets()

                            keyboard = [[InlineKeyboardButton("💳 Saldo (Umum)", callback_data='src_saldo')]]

                            if first_cat in budgets:
                                keyboard.append([InlineKeyboardButton(
                                    f"📂 Budget: {first_cat.capitalize()}",
                                    callback_data=f'src_budget_select_{first_cat}'
                                )])
                                keyboard.append([InlineKeyboardButton("📂 Budget Lain...", callback_data='src_budget_list')])
                            else:
                                keyboard.append([InlineKeyboardButton("💰 Pakai Budget...", callback_data='src_budget_list')])

                            reply_markup = InlineKeyboardMarkup(keyboard)
                            await context.bot.edit_message_text(
                                chat_id=chat_id, message_id=status_msg.message_id,
                                text="💸 **Pengeluaran via apa?**",
                                reply_markup=reply_markup, parse_mode='Markdown'
                            )
                    except Exception as e:
                        logging.error(f"Error Text: {e}")
                        await context.bot.edit_message_text(
                            chat_id=chat_id, message_id=status_msg.message_id, text="❌ Error sistem."
                        )
                    return

                # Incomplete Transaction detection
                if self._is_incomplete_transaction(user_text):
                    self.pending_inputs[user_id] = user_text
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
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)

            bio = io.BytesIO()
            await file.download_to_memory(bio)
            image_bytes = bio.getvalue()

            transactions = await self.ai_service.parse_receipt_image(image_bytes)
            await self._save_and_reply(update, context, transactions, status_msg.message_id)
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
                text=f'🎤 "{text}"\n⏳ Mencatat...'
            )
            transactions = await self.ai_service.parse_expense(text)
            await self._save_and_reply(update, context, transactions, status_msg.message_id)
        except Exception as e:
            logging.error(f"Error Voice: {e}")
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=status_msg.message_id, text="❌ Gagal memproses suara."
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

    async def _save_and_reply(self, update, context, transactions, message_id):
        """Save transactions to Supabase and reply with Benny's personality."""
        chat_id = update.effective_chat.id
        uid = self._user_id(update)

        if not transactions:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=message_id,
                text="🤖 Hmm, aku ga nemu data transaksi nih. Coba lagi ya! 💙"
            )
            return

        # Route income vs expense
        is_income_batch = any(
            str(t.get('category', '')).lower() in ['income', 'pemasukan', 'gaji']
            for t in transactions
        )

        if is_income_batch:
            success = self.db.add_income(uid, [
                {
                    "source": t.get("item", ""),
                    "category": t.get("category", "Income"),
                    "amount": t.get("amount", 0),
                    "date": t.get("date", ""),
                    "time": t.get("time", ""),
                    "notes": t.get("notes", ""),
                } for t in transactions
            ])
        else:
            success = self.db.add_transactions_bulk(uid, transactions)

        if not success:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=message_id, text="❌ Gagal simpan ke database."
            )
            return

        # Build personality reply
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

        # Check balance
        try:
            _, _, current_balance = self._calculate_balance(uid)
            if current_balance < 0:
                pass
        except:
            pass

        # Short Summary
        reply_text += "━━━━━━━━━━━━━━━━━━━━\n"
        if total_income_now > 0:
            reply_text += f"➕ PEMASUKAN : Rp {total_income_now:,.0f}".replace(',', '.') + "\n"
        if total_expense_now > 0:
            reply_text += f"➖ PENGELUARAN : Rp {total_expense_now:,.0f}".replace(',', '.') + "\n"

            first_cat = transactions[0].get('category', '').lower()
            budgets = self.budget_service.get_budgets()
            if first_cat in budgets:
                remaining = budgets[first_cat]
                reply_text += f"💰 SALDO {first_cat.upper()} : Rp {remaining:,.0f}".replace(',', '.') + "\n"
                if remaining <= 0:
                    pass

        if total_income_now > 0:
            reply_text += "\n_Nice! Pemasukan masuk, semangat terus! 🔥_"
        else:
            reply_text += "\n_Tenang, kamu pasti bisa balance lagi!_ 💪"

        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=message_id,
            text=reply_text, parse_mode='Markdown'
        )

    # ─── MENUS & REPORTS ────────────────────────────────────

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

        if str(update.effective_user.id) != str(Config.ADMIN_ID):
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

        # Handle Income Classification
        if action.startswith('income_'):
            user_id = update.effective_user.id
            tag = "[Primer]" if action == 'income_primer' else "[Sekunder]"

            if user_id in self.pending_income:
                transactions = self.pending_income.pop(user_id)

                for t in transactions:
                    if str(t.get('category', '')).lower() in ['income', 'pemasukan', 'gaji']:
                        original_item = t.get('item', 'Income')
                        t['item'] = f"{original_item} {tag}"

                await query.edit_message_text("💾 Menyimpan data...")
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
            row = []
            for cat in budgets:
                row.append(InlineKeyboardButton(f"📂 {cat.capitalize()}", callback_data=f'src_budget_select_{cat}'))
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)

            keyboard.append([InlineKeyboardButton("🔙 Batal (Pakai Saldo)", callback_data='src_saldo')])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("💰 **Pilih Budget:**", reply_markup=reply_markup, parse_mode='Markdown')
            return

        if action.startswith('src_budget_select_'):
            user_id = update.effective_user.id
            selected_budget = action.replace('src_budget_select_', '')

            if user_id in self.pending_expenses:
                transactions = self.pending_expenses.pop(user_id)

                total_expense = sum(t.get('amount', 0) for t in transactions)
                deducted, excess = self.budget_service.deduct_budget(selected_budget, total_expense)

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

        if not self.export_service.is_available():
            await update.message.reply_text(
                "⚠️ PDF export belum tersedia.\n"
                "Install: `pip install reportlab matplotlib`",
                parse_mode='Markdown'
            )
            return

        await update.message.reply_text("📄 Generating PDF report...")

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
        """Handle Trend button — show spending trend chart."""
        uid = self._user_id(update)
        await update.message.reply_text("📈 Analyzing trends...")

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

            await update.message.reply_text(message, parse_mode='Markdown')

        except Exception as e:
            logging.error(f"Error generating trend: {e}")
            await update.message.reply_text("❌ Gagal menghasilkan trend. Coba lagi nanti.")
