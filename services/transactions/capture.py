"""AI-assisted income and expense capture lifecycle."""

import asyncio
import io
import logging
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from services.ai.service import (
    ReceiptProcessingError,
    TextProcessingError,
    VoiceProcessingError,
)
from services.infrastructure.events import log_event

logger = logging.getLogger(__name__)


class TransactionCaptureController:
    """Handle text, receipt, voice, confirmation, and ledger mutations."""

    def __init__(self, ai_service, db, reply_text, edit_message_text, memory=None):
        self.ai = ai_service
        self.db = db
        self.reply_text = reply_text
        self.edit_message_text = edit_message_text
        self.memory = memory

    async def handle(self, update, context):
        if context.user_data.get("pending_confirmation"):
            await self.reply_text(
                update.message,
                "Masih ada transaksi yang menunggu konfirmasi. Pilih Simpan, Edit Teks, atau Batal dulu.",
            )
            return
        message = update.message
        if message.photo or (
            message.document
            and message.document.mime_type
            and message.document.mime_type.startswith("image/")
        ):
            await self.handle_photo(update, context)
            return
        if message.voice:
            await self.handle_voice(update, context)
            return
        await self.handle_text(update, context)

    async def handle_text(self, update, context):
        text = (update.message.text or "").strip()
        if not text:
            return

        uid, chat_id = str(update.effective_user.id), str(update.effective_chat.id)
        pending_edit = context.user_data.pop("edit_capture", None)
        if pending_edit:
            await self._prepare_edit(update, context, text, pending_edit)
            return

        previous = context.user_data.pop("pending_input", None)
        if previous:
            text = f"{previous} {text}"

        status = await self.reply_text(update.message, "Memahami pesanmu...")
        try:
            if self.memory:
                session, explicit = await asyncio.to_thread(
                    self.memory.context, uid, chat_id
                )
                result = await self.ai.interpret_message(text, session, explicit)
            else:
                result = await self.ai.interpret_message(text)
            if result["intent"] == "clarification":
                context.user_data["pending_input"] = text
                reply = result.get("clarification") or "Transaksinya apa dan nominalnya berapa?"
                if self.memory:
                    await asyncio.to_thread(
                        self.memory.remember_exchange, uid, chat_id, text, reply,
                        update.effective_message.message_id,
                    )
                await self.edit_message_text(
                    context.bot,
                    chat_id=update.effective_chat.id,
                    message_id=status.message_id,
                    text=reply,
                )
                return
            if result["intent"] == "conversation":
                reply = result.get("reply") or "Aku siap bantu mencatat dan mengecek keuanganmu."
                if self.memory:
                    await asyncio.to_thread(
                        self.memory.remember_exchange, uid, chat_id, text, reply,
                        update.effective_message.message_id,
                    )
                await self.edit_message_text(
                    context.bot,
                    chat_id=update.effective_chat.id,
                    message_id=status.message_id,
                    text=reply,
                )
                return
            await self.ask_confirmation(
                update, context, result["items"], status.message_id, "Teks"
            )
        except TextProcessingError as error:
            message = (
                "AI pencatat sedang tidak tersedia. Pesanmu belum diproses dan tidak ada data yang disimpan."
                if str(error) == "provider_failed"
                else "Respons AI tidak dapat dibaca. Coba tulis ulang item dan nominalnya."
            )
            await self.edit_message_text(
                context.bot,
                chat_id=update.effective_chat.id,
                message_id=status.message_id,
                text=message,
            )
        except Exception:
            logger.exception("Text capture failed")
            await self.edit_message_text(
                context.bot,
                chat_id=update.effective_chat.id,
                message_id=status.message_id,
                text="Gagal memproses transaksi.",
            )

    async def handle_photo(self, update, context):
        status = await self.reply_text(update.message, "Membaca struk...")
        try:
            file_id = (
                update.message.photo[-1].file_id
                if update.message.photo
                else update.message.document.file_id
            )
            file = await context.bot.get_file(file_id)
            data = io.BytesIO()
            await file.download_to_memory(data)
            artifact = await self.ai.parse_receipt_image(data.getvalue())
            if isinstance(artifact, list):
                artifact = {"status": "readable", "raw_text": "", "items": artifact}
            transactions = artifact.get("items", [])
            raw_text = artifact.get("raw_text", "")[:1200]
            if artifact.get("status") == "unreadable" and not raw_text:
                await self.edit_message_text(
                    context.bot,
                    chat_id=update.effective_chat.id,
                    message_id=status.message_id,
                    text="Teks struk tidak terbaca. Pastikan foto terang, fokus, dan total pembayaran terlihat.",
                )
                return
            if not transactions:
                preview = f"\n\nTeks terbaca:\n{raw_text}" if raw_text else ""
                await self.edit_message_text(
                    context.bot,
                    chat_id=update.effective_chat.id,
                    message_id=status.message_id,
                    text=f"Hasil OCR masih ambigu. Belum ada transaksi yang disimpan.{preview}",
                )
                return
            await self.ask_confirmation(
                update,
                context,
                transactions,
                status.message_id,
                "Struk OCR",
                artifact_text=raw_text,
                needs_review=artifact.get("status") == "low_confidence",
            )
        except ReceiptProcessingError as error:
            invalid_response = str(error) == "invalid_response"
            logger.info("Receipt processing unavailable: %s", str(error))
            await self.edit_message_text(
                context.bot,
                chat_id=update.effective_chat.id,
                message_id=status.message_id,
                text=(
                    "Hasil OCR tidak dapat dibaca. Foto belum menjadi transaksi; coba kirim ulang foto yang lebih jelas."
                    if invalid_response
                    else "OCR sedang tidak tersedia. Foto belum diproses dan tidak ada transaksi yang disimpan."
                ),
            )
        except Exception:
            logger.exception("Receipt capture failed")
            await self.edit_message_text(
                context.bot,
                chat_id=update.effective_chat.id,
                message_id=status.message_id,
                text="Gagal membaca struk.",
            )

    async def handle_voice(self, update, context):
        status = await self.reply_text(update.message, "Mendengarkan...")
        try:
            file = await context.bot.get_file(update.message.voice.file_id)
            data = io.BytesIO()
            await file.download_to_memory(data)
            artifact = await self.ai.transcribe_audio(data.getvalue())
            if isinstance(artifact, str):
                artifact = {"text": artifact, "status": "transcribed"}
            text = artifact.get("text", "").strip()
            if not text:
                await self.edit_message_text(
                    context.bot,
                    chat_id=update.effective_chat.id,
                    message_id=status.message_id,
                    text="Suara tidak dapat dikenali.",
                )
                return
            result = await self.ai.interpret_message(text)
            if result["intent"] != "transaction":
                follow_up = (
                    result.get("clarification")
                    if result["intent"] == "clarification"
                    else result.get("reply")
                ) or "Aku belum menemukan transaksi yang jelas."
                await self.edit_message_text(
                    context.bot,
                    chat_id=update.effective_chat.id,
                    message_id=status.message_id,
                    text=f"Transkrip\n{text[:1200]}\n\n{follow_up}",
                )
                return
            await self.ask_confirmation(
                update,
                context,
                result["items"],
                status.message_id,
                "Voice Note",
                artifact_text=text[:1200],
                needs_review=artifact.get("status") == "low_confidence",
            )
        except VoiceProcessingError:
            await self.edit_message_text(
                context.bot,
                chat_id=update.effective_chat.id,
                message_id=status.message_id,
                text="Transkripsi suara sedang tidak tersedia. Voice note belum diproses dan tidak ada transaksi yang disimpan.",
            )
        except TextProcessingError as error:
            message = (
                "Transkrip berhasil, tetapi AI pencatat sedang tidak tersedia. Tidak ada transaksi yang disimpan."
                if str(error) == "provider_failed"
                else "Transkrip berhasil, tetapi hasil ekstraksi masih ambigu. Tidak ada transaksi yang disimpan."
            )
            await self.edit_message_text(
                context.bot,
                chat_id=update.effective_chat.id,
                message_id=status.message_id,
                text=message,
            )
        except Exception:
            logger.exception("Voice capture failed")
            await self.edit_message_text(
                context.bot,
                chat_id=update.effective_chat.id,
                message_id=status.message_id,
                text="Gagal memproses suara.",
            )

    async def ask_confirmation(
        self, update, context, transactions, message_id, source,
        artifact_text="", needs_review=False,
    ):
        if not transactions:
            await self.edit_message_text(
                context.bot,
                chat_id=update.effective_chat.id,
                message_id=message_id,
                text="Data transaksi tidak ditemukan. Silakan coba lagi.",
            )
            return
        operation_id = f"{update.effective_user.id}:{update.effective_message.message_id}"
        context.user_data["pending_confirmation"] = {
            "transactions": transactions,
            "operation_id": operation_id,
        }
        lines = [
            "Aku menangkap transaksi ini. Cek dulu sebelum disimpan.",
            "",
            f"Sumber: {source}",
        ]
        if needs_review:
            lines.append("Status: Perlu dicek, hasil input kurang yakin")
        if artifact_text:
            label = "Transkrip" if source == "Voice Note" else "Teks terbaca"
            lines.extend((f"{label}:", artifact_text, ""))
        else:
            lines.append("")
        for transaction in transactions:
            amount = f"{int(transaction.get('amount', 0)):,.0f}".replace(",", ".")
            income = str(transaction.get("category", "")).lower() == "income"
            name = transaction.get("item", transaction.get("item_name", "?"))
            lines.extend((
                f"Jenis: {'Pemasukan' if income else 'Pengeluaran'}",
                f"Tanggal: {transaction.get('date') or '-'} {transaction.get('time') or ''}".rstrip(),
                f"{'Sumber' if income else 'Item'}: {name}",
                f"Kategori: {transaction.get('category') or '-'}",
                f"Nominal: Rp {amount}",
                f"Lokasi: {transaction.get('location') or '-'}",
                "",
            ))
        await self.edit_message_text(
            context.bot,
            chat_id=update.effective_chat.id,
            message_id=message_id,
            text="\n".join(lines).strip(),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Simpan", callback_data=f"confirm_save_yes:{operation_id}")],
                [
                    InlineKeyboardButton("Edit Teks", callback_data=f"confirm_save_edit:{operation_id}"),
                    InlineKeyboardButton("Batal", callback_data=f"confirm_save_no:{operation_id}"),
                ],
            ]),
        )

    async def save_and_reply(self, update, context, transactions, message_id, operation_id=None):
        uid = str(update.effective_user.id)
        operation_id = operation_id or f"{uid}:{update.effective_message.message_id}"
        income_flags = [
            str(row.get("category", "")).lower() in {"income", "pemasukan", "gaji"}
            for row in transactions
        ]
        if not transactions or (any(income_flags) and not all(income_flags)):
            await self.edit_message_text(
                context.bot,
                chat_id=update.effective_chat.id,
                message_id=message_id,
                text="Belum tersimpan\n\nPisahkan pemasukan dan pengeluaran ke pesan berbeda.",
            )
            return

        if all(income_flags):
            rows = [{
                "source": row.get("item", ""),
                "category": row.get("category", "Income"),
                "amount": row.get("amount", 0),
                "date": row.get("date", ""),
                "time": row.get("time", ""),
                "notes": row.get("notes", ""),
            } for row in transactions]
            result = await asyncio.to_thread(
                self.db.add_income, uid, rows, operation_id
            )
            table_code = "i"
        else:
            result = await asyncio.to_thread(
                self.db.add_transactions_bulk, uid, transactions, operation_id
            )
            table_code = "e"

        if not result["ok"]:
            context.user_data["retry_capture"] = {
                "transactions": transactions,
                "operation_id": operation_id,
            }
            await self.edit_message_text(
                context.bot,
                chat_id=update.effective_chat.id,
                message_id=message_id,
                text="Belum tersimpan\n\nKoneksi sedang bermasalah. Datamu belum masuk.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Coba Lagi", callback_data="retry_capture")
                ]]),
            )
            return

        log_event("capture_saved", uid, count=len(result["records"]))
        total = sum(int(row.get("amount", 0)) for row in transactions)
        kind = "Pemasukan" if all(income_flags) else "Pengeluaran"
        details = "\n\n".join(
            f"{row.get('item', 'Item')}\n{row.get('category', 'Lainnya')} · Rp{int(row.get('amount', 0)):,.0f}".replace(",", ".")
            for row in transactions
        )
        record_id = result["records"][0].get("id", "")
        await self.edit_message_text(
            context.bot,
            chat_id=update.effective_chat.id,
            message_id=message_id,
            text=f"Tersimpan\n\n{details}\n\n{kind} Rp{total:,.0f}".replace(",", "."),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Batalkan", callback_data=f"undo_capture:{table_code}:{operation_id}")],
                [InlineKeyboardButton("Edit", callback_data=f"edit_capture:{table_code}:{record_id}")],
            ]),
        )

    async def handle_callback(self, update, context):
        query = update.callback_query
        action = query.data
        uid = str(update.effective_user.id)
        await query.answer()

        if action.startswith("confirm_save_"):
            pending = context.user_data.get("pending_confirmation")
            action, _, operation_id = action.partition(":")
            if not pending or operation_id != pending["operation_id"]:
                await self.edit_message_text(query, "Sesi kedaluwarsa. Silakan ulangi input.")
                return
            if action == "confirm_save_no":
                context.user_data.pop("pending_confirmation", None)
                await self.edit_message_text(query, "Aksi dibatalkan.")
                return
            pending = context.user_data.pop("pending_confirmation")
            if action == "confirm_save_edit":
                context.user_data["pending_input"] = ""
                await self.edit_message_text(query, "Ketik ulang transaksi beserta nominal yang benar.")
                return
            await self.edit_message_text(query, "Menyimpan transaksi...")
            await self.save_and_reply(
                update, context, pending["transactions"], query.message.message_id,
                pending["operation_id"],
            )
            return

        if action == "retry_capture":
            pending = context.user_data.get("retry_capture")
            if not pending:
                await self.edit_message_text(query, "Sesi coba lagi sudah berakhir.")
                return
            await self.save_and_reply(
                update, context, pending["transactions"], query.message.message_id,
                pending["operation_id"],
            )
            return

        if action.startswith("undo_capture:"):
            _, table_code, operation_id = action.split(":", 2)
            table = "income" if table_code == "i" else "transactions"
            deleted = await asyncio.to_thread(
                self.db.delete_operation, uid, table, operation_id
            )
            await self.edit_message_text(query, "Dibatalkan" if deleted else "Transaksi tidak ditemukan.")
            return

        if action.startswith("edit_capture:"):
            _, table_code, record_id = action.split(":", 2)
            table = "income" if table_code == "i" else "transactions"
            original = await asyncio.to_thread(
                self.db.get_record, uid, table, record_id
            )
            if not original:
                await self.edit_message_text(query, "Transaksi tidak ditemukan.")
                return
            context.user_data["edit_capture"] = {
                "table": table, "record_id": record_id, "original": original,
            }
            await self.edit_message_text(query, "Kirim ulang transaksi lengkap dengan nilai yang benar.")
            return

        if action.startswith("confirm_mod_"):
            pending = context.user_data.pop("pending_modification", None)
            if not pending:
                await self.edit_message_text(query, "Sesi edit sudah berakhir.")
                return
            if action == "confirm_mod_no":
                await self.edit_message_text(query, "Perubahan dibatalkan.")
                return
            update_record = (
                self.db.update_income
                if pending["table"] == "income"
                else self.db.update_transaction
            )
            success = await asyncio.to_thread(
                update_record, uid, pending["record_id"], pending["data"]
            )
            await self.edit_message_text(query, "Transaksi berhasil diubah." if success else "Gagal mengubah transaksi.")
            return

        await self.edit_message_text(query, "Aksi tidak tersedia.")

    async def _prepare_edit(self, update, context, text, pending):
        rows = await self.ai.parse_expense(text)
        if len(rows) != 1:
            await self.reply_text(update.message, "Kirim satu transaksi lengkap.")
            return
        row = rows[0]
        amount = int(row.get("amount", 0))
        item = row.get("item", "")
        if amount <= 0 or not item:
            await self.reply_text(update.message, "Item atau nominal belum valid.")
            return
        data = {
            ("source" if pending["table"] == "income" else "item_name"): item,
            "category": row.get("category", "Income" if pending["table"] == "income" else "Other"),
            "amount": amount,
            "date": row.get("date") or pending["original"].get("date"),
            "time": row.get("time") or pending["original"].get("time"),
        }
        if pending["table"] == "transactions":
            data["location"] = row.get("location", pending["original"].get("location", ""))
        context.user_data["pending_modification"] = {
            "table": pending["table"], "record_id": pending["record_id"], "data": data,
        }
        await self.reply_text(
            update.message,
            "Konfirmasi perubahan",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Konfirmasi", callback_data="confirm_mod_yes"),
                InlineKeyboardButton("Batal", callback_data="confirm_mod_no"),
            ]]),
        )

    @staticmethod
    def is_transaction(text):
        words = set(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())
        keywords = {
            "beli", "bayar", "belanja", "makan", "minum", "bensin", "parkir",
            "gaji", "income", "dapat", "terima", "transfer", "jual", "rp",
            "ribu", "rb", "juta", "jt",
        }
        return bool(words & keywords) and any(char.isdigit() for char in text)
