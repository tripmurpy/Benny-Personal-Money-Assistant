"""Read-only spending roast from a bounded user ledger snapshot."""

import asyncio
import re
from collections import defaultdict
from datetime import date, timedelta


class RoastService:
    TRIGGER = re.compile(r"^/?roast(?:\b|$)", re.IGNORECASE)
    UNSUPPORTED = re.compile(
        r"\b(tidak punya tujuan|tidak memiliki tujuan|tujuan hidup|kecanduan|pecandu|miskin|pemalas)\b",
        re.IGNORECASE,
    )

    def __init__(self, ai, db, reply_text, today=None):
        self.ai = ai
        self.db = db
        self.reply_text = reply_text
        self.today = today or date.today

    @classmethod
    def looks_like_roast(cls, text):
        return bool(cls.TRIGGER.search((text or "").strip()))

    @staticmethod
    def _top(stats):
        if not stats:
            return None
        name, values = min(
            stats.items(),
            key=lambda item: (-item[1]["amount"], -item[1]["count"], item[0].lower()),
        )
        return {"name": name, **values}

    @classmethod
    def summarize(cls, rows, today):
        period_start = today - timedelta(days=29)
        filtered, expenses = [], []
        item_stats = defaultdict(lambda: {"count": 0, "amount": 0})
        category_stats = defaultdict(lambda: {"count": 0, "amount": 0})

        for raw in rows or []:
            try:
                occurred = date.fromisoformat(str(raw.get("date", "")))
                amount = int(raw.get("amount", 0))
            except (TypeError, ValueError):
                continue
            if not period_start <= occurred <= today or amount <= 0:
                continue
            kind = str(raw.get("kind", ""))
            if kind not in {"expense", "income"}:
                continue
            row = {"kind": kind, "date": occurred.isoformat(), "amount": amount}
            filtered.append(row)
            if kind != "expense":
                continue
            row.update({
                "name": str(raw.get("name") or "Lainnya"),
                "category": str(raw.get("category") or "Other"),
            })
            expenses.append(row)
            for stats, key in ((item_stats, row["name"]), (category_stats, row["category"])):
                stats[key]["count"] += 1
                stats[key]["amount"] += amount

        total_expense = sum(row["amount"] for row in expenses)
        total_income = sum(row["amount"] for row in filtered if row["kind"] == "income")
        largest = sorted(
            expenses,
            key=lambda row: (row["amount"], row["date"], row["name"]),
            reverse=True,
        )[:5]
        return {
            "period_start": period_start.isoformat(),
            "period_end": today.isoformat(),
            "total_income": total_income,
            "total_expense": total_expense,
            "net_cashflow": total_income - total_expense,
            "transaction_count": len(filtered),
            "expense_count": len(expenses),
            "top_category": cls._top(category_stats),
            "top_item": cls._top(item_stats),
            "largest_expenses": [
                {key: row[key] for key in ("name", "category", "amount", "date")}
                for row in largest
            ],
        }

    @staticmethod
    def _rupiah(amount):
        return f"Rp{int(amount):,}".replace(",", ".")

    @classmethod
    def fallback(cls, summary):
        top = summary.get("top_item")
        if top:
            evidence = (
                f"{top['name']} muncul {top['count']} kali dengan total "
                f"{cls._rupiah(top['amount'])}"
            )
            action = f"Batasi {top['name']} satu kali minggu depan dan simpan selisihnya."
        else:
            evidence = "pengeluaranmu tetap bocor tanpa pola yang bisa dibela"
            action = "Batasi satu pembelian impulsif minggu depan dan simpan selisihnya."
        return (
            "AI roast sedang tidak tersedia, tapi angkanya sudah cukup memalukan. "
            f"Kamu menghabiskan {cls._rupiah(summary['total_expense'])} dalam 30 hari; "
            f"{evidence}. {action}"
        )

    @classmethod
    def supported(cls, text, summary):
        top = summary.get("top_item") or {}
        lowered = (text or "").lower()
        evidence = {
            cls._rupiah(summary["total_expense"]).lower(),
            cls._rupiah(top.get("amount", 0)).lower(),
        }
        return bool(
            text
            and top.get("name", "").lower() in lowered
            and any(amount in lowered for amount in evidence)
            and not cls.UNSUPPORTED.search(text)
        )

    async def try_handle(self, update):
        if not self.looks_like_roast(update.message.text):
            return False
        snapshot = await asyncio.to_thread(
            self.db.get_finance_snapshot, str(update.effective_user.id)
        )
        if snapshot is None:
            await self.reply_text(
                update.message, "Data keuangan belum dapat dibaca. Coba roast lagi nanti."
            )
            return True
        summary = self.summarize(snapshot.get("rows", []), self.today())
        if not summary["expense_count"]:
            await self.reply_text(
                update.message,
                "Belum ada transaksi 30 hari terakhir yang bisa kuroast. Catat dulu, misalnya: kopi 25 ribu.",
            )
            return True
        try:
            text = (await self.ai.generate_roast(summary)).strip()
            if not self.supported(text, summary):
                raise ValueError("unsupported roast")
        except Exception:
            text = self.fallback(summary)
        await self.reply_text(update.message, text[:900])
        return True
