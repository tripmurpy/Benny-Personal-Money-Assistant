"""Natural-language routing with deterministic expense reporting."""

import asyncio
import re
import calendar
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from services.transactions.capture import TransactionCaptureController


class ExpenseReportService:
    TIMEZONE = ZoneInfo("Asia/Bangkok")
    REPORT_TERMS = re.compile(
        r"\b(laporan|rekap|riwayat|pengeluaran(?:ku| saya)?|total|berapa|apa(?: saja)?)\b",
        re.IGNORECASE,
    )
    TIME_TERMS = re.compile(
        r"\b(hari|minggu|bulan|tanggal|kemarin|kemaren|terakhir|senin|selasa|rabu|kamis|jumat|sabtu|minggu)\b|\d{1,2}[-/]\d{1,2}",
        re.IGNORECASE,
    )
    WEEKDAY_TERMS = re.compile(
        r"\b(senin|selasa|rabu|kamis|jumat|sabtu|minggu)\b", re.IGNORECASE
    )
    DATE_TERMS = re.compile(
        r"\b(tanggal|januari|februari|maret|april|mei|juni|juli|agustus|"
        r"september|oktober|november|desember|sampai|hingga|dari)\b|\d{1,2}[-/]\d{1,2}",
        re.IGNORECASE,
    )
    CATEGORY_LABELS = {
        "Food": "Makanan",
        "Drink": "Minuman",
        "Shopping": "Belanja",
        "Gas": "Bahan bakar",
        "Transport": "Transportasi",
        "Income": "Pemasukan",
        "Komunikasi": "Komunikasi",
        "Study": "Pendidikan",
        "Other": "Lainnya",
    }

    def __init__(self, ai, db, reply_text, now=None):
        self.ai = ai
        self.db = db
        self.reply_text = reply_text
        self.now = now or (lambda: datetime.now(self.TIMEZONE))

    @classmethod
    def looks_like_report(cls, text):
        return bool(cls.REPORT_TERMS.search(text) and cls.TIME_TERMS.search(text))

    async def try_handle(self, update):
        text = (update.message.text or "").strip()
        if not self.looks_like_report(text):
            return False
        if TransactionCaptureController.is_transaction(text) and not re.search(
            r"\b(laporan|rekap|riwayat|total|berapa|apa)\b", text, re.IGNORECASE
        ):
            return False

        current = self.now()
        request = self._direct_request(text)
        if not request:
            try:
                request = await self.ai.parse_report_request(text, current)
            except Exception:
                await self.reply_text(
                    update.message,
                    "Permintaan laporan belum dapat dipahami. Silakan sebutkan periodenya.",
                )
                return True

        if request.get("intent") != "expense_report":
            return False
        if request.get("needs_clarification"):
            await self.reply_text(
                update.message,
                request.get("clarification") or "Rentang waktunya dari kapan sampai kapan?",
            )
            return True

        try:
            start, end = self._range(request, current)
        except (TypeError, ValueError):
            await self.reply_text(
                update.message,
                "Rentang waktu laporan tidak valid. Sebutkan tanggal atau periode yang lebih jelas.",
            )
            return True

        rows = await asyncio.to_thread(
            self.db.get_expenses_between, str(update.effective_user.id), start, end
        )
        if rows is None:
            await self.reply_text(
                update.message,
                "Laporan belum dapat diambil karena koneksi database bermasalah.",
            )
            return True

        for chunk in self._format(rows, start, end):
            await self.reply_text(update.message, chunk)
        return True

    @classmethod
    def _direct_request(cls, text):
        lowered = text.lower()
        days = re.search(r"\b(\d{1,4})\s*hari(?:\s+terakhir)?\b", lowered)
        if days:
            return {
                "intent": "expense_report",
                "range_type": "last_n_days",
                "day_count": int(days.group(1)),
            }
        if re.search(r"\b(kemarin|kemaren)\b", lowered) and not (
            cls.WEEKDAY_TERMS.search(lowered) or cls.DATE_TERMS.search(lowered)
        ):
            return {"intent": "expense_report", "range_type": "yesterday"}
        if "hari ini" in lowered:
            return {"intent": "expense_report", "range_type": "today"}
        if "minggu ini" in lowered:
            return {"intent": "expense_report", "range_type": "this_week"}
        if "bulan ini" in lowered:
            return {"intent": "expense_report", "range_type": "this_month"}
        if re.search(r"\b(1|satu)\s+bulan\s+terakhir\b", lowered):
            return {"intent": "expense_report", "range_type": "rolling_month"}
        return None

    @classmethod
    def _range(cls, request, current):
        current = current.astimezone(cls.TIMEZONE) if current.tzinfo else current.replace(tzinfo=cls.TIMEZONE)
        range_type = request.get("range_type")
        if range_type in {"today", "yesterday"}:
            day = current if range_type == "today" else current - timedelta(days=1)
            return (
                day.replace(hour=0, minute=0, second=0, microsecond=0),
                current if range_type == "today" else day.replace(
                    hour=23, minute=59, second=59, microsecond=0
                ),
            )
        if range_type == "this_week":
            return (
                (current - timedelta(days=current.weekday())).replace(
                    hour=0, minute=0, second=0, microsecond=0
                ),
                current,
            )
        if range_type == "this_month":
            return current.replace(day=1, hour=0, minute=0, second=0, microsecond=0), current
        if range_type == "last_n_days":
            count = int(request.get("day_count", 0))
            if not 1 <= count <= 3660:
                raise ValueError("invalid day count")
            start = (current - timedelta(days=count - 1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            return start, current
        if range_type == "rolling_month":
            year, month = current.year, current.month - 1
            if month == 0:
                year, month = year - 1, 12
            day = min(current.day, calendar.monthrange(year, month)[1])
            return current.replace(year=year, month=month, day=day), current
        if range_type == "weekday_range":
            start_weekday = int(request.get("start_weekday", 0))
            end_weekday = int(request.get("end_weekday", 0))
            if not 1 <= start_weekday <= 7 or not 1 <= end_weekday <= 7:
                raise ValueError("invalid weekday")
            end_time = datetime.strptime(
                request.get("end_time") or "23:59:59", "%H:%M:%S"
            ).time()
            end = (current - timedelta(days=(current.isoweekday() - end_weekday) % 7)).replace(
                hour=end_time.hour, minute=end_time.minute, second=end_time.second,
                microsecond=0,
            )
            if end > current:
                end -= timedelta(days=7)
            start = (end - timedelta(days=(end_weekday - start_weekday) % 7)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            return start, end

        def local(value):
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=cls.TIMEZONE)
            return parsed.astimezone(cls.TIMEZONE)

        start, end = local(request["start_at"]), local(request["end_at"])
        if end.date() == current.date() and end > current:
            end = current
        if start > end or end > current or (end - start).days > 3660:
            raise ValueError("unsafe report range")
        return start, end

    @staticmethod
    def _rupiah(value):
        return f"Rp{int(value):,}".replace(",", ".")

    @classmethod
    def _format(cls, rows, start, end):
        period = (
            f"{start.strftime('%d-%m-%Y %H:%M')} sampai "
            f"{end.strftime('%d-%m-%Y %H:%M')}"
        )
        if not rows:
            return [
                "Pengeluaran\n\n"
                "Rp0\n\n"
                f"0 transaksi pada {period}.\n\n"
                "Tidak ada pengeluaran pada periode tersebut."
            ]

        categories = defaultdict(int)
        total = 0
        details = []
        for index, row in enumerate(rows, 1):
            amount = int(row.get("amount", 0))
            category = row.get("category") or "Other"
            category_label = cls.CATEGORY_LABELS.get(category, category)
            total += amount
            categories[category_label] += amount
            lines = [
                f"{index}. {row.get('item_name') or '-'} — {cls._rupiah(amount)}",
                f"Waktu: {row.get('date')} {str(row.get('time', ''))[:5]}",
                f"Kategori: {category_label}",
            ]
            for label, field in (
                ("Lokasi", "location"),
                ("Pembayaran", "payment_method"),
                ("Catatan", "notes"),
            ):
                if row.get(field):
                    lines.append(f"{label}: {row[field]}")
            details.append("\n".join(lines))

        summary = [
            "Total Pengeluaran",
            "",
            cls._rupiah(total),
            "",
            f"{len(rows)} transaksi pada {period}.",
            "",
            "Per kategori:",
            *(f"{name}: {cls._rupiah(amount)}" for name, amount in sorted(categories.items())),
            "",
            "Transaksi:",
        ]
        chunks, current = [], "\n".join(summary)
        for detail in details:
            addition = f"\n\n{detail}"
            if len(current) + len(addition) > 3800:
                chunks.append(current)
                current = "Total Pengeluaran (lanjutan)" + addition
            else:
                current += addition
        chunks.append(current)
        return chunks
