"""Read-only natural-language analytics over a user-scoped ledger snapshot."""

import asyncio
import html
import re
import sqlite3
from datetime import date

from services.ai.service import FinanceSqlError
from services.reporting.service import ExpenseReportService
from services.transactions.capture import TransactionCaptureController


class FinanceSqlAssistant:
    FINANCE = re.compile(
        r"\b(pengeluaran|pemasukan|transaksi|kategori|belanja|boros|income|expense|uang|"
        r"beli|bayar|langganan|subscribe|keluar|masuk)\b",
        re.IGNORECASE,
    )
    ANALYTIC = re.compile(
        r"\b(total|jumlah|berapa|rata.?rata|average|terbesar|tertinggi|terbanyak|"
        r"paling|top|bandingkan|perbandingan|selisih|minimum|maksimum|min|max|"
        r"kapan|dimana|range|rentang|antara)\b|\bapa\s*(?:saja|aja|yang)\b",
        re.IGNORECASE,
    )
    WRITE = re.compile(
        r"\b(hapus|ubah|edit|delete|update|insert|drop|alter|create|attach|detach|pragma)\b",
        re.IGNORECASE,
    )
    FORBIDDEN_SQL = re.compile(
        r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum|reindex|analyze)\b",
        re.IGNORECASE,
    )
    MONEY_COLUMNS = re.compile(
        r"(^|_)(amount|harga|nominal|total|rata_rata|average|avg|minimum|min|maximum|max|selisih|pengeluaran|pemasukan)($|_)",
        re.IGNORECASE,
    )
    FUNCTIONS = {
        "abs", "avg", "coalesce", "count", "date", "datetime", "julianday",
        "like", "lower", "max", "min", "printf", "round", "strftime", "substr", "sum", "upper",
    }

    def __init__(self, ai, db, reply_text, today=None):
        self.ai = ai
        self.db = db
        self.reply_text = reply_text
        self.today = today or date.today

    @classmethod
    def looks_like_query(cls, text):
        return bool(cls.FINANCE.search(text) and cls.ANALYTIC.search(text))

    async def try_handle(self, update):
        text = (update.message.text or "").strip()
        if self.FINANCE.search(text) and self.WRITE.search(text):
            await self.reply_text(update.message, "Benny SQL hanya dapat membaca data, bukan mengubah atau menghapus transaksi.")
            return True
        if not self.looks_like_query(text):
            return False
        if TransactionCaptureController.is_transaction(text) and not self.ANALYTIC.search(text):
            return False
        snapshot = await asyncio.to_thread(
            self.db.get_finance_snapshot, str(update.effective_user.id)
        )
        if snapshot is None:
            await self.reply_text(update.message, "Data keuangan belum dapat diambil dari database.")
            return True
        if not snapshot["rows"]:
            await self.reply_text(update.message, "Data Keuangan\n\nBelum ada transaksi yang dapat dianalisis.")
            return True

        try:
            request = await self.ai.generate_finance_sql(text, self.today().isoformat())
            if request["intent"] == "clarification":
                await self.reply_text(
                    update.message,
                    request.get("clarification") or "Periode atau analisis apa yang ingin diperiksa?",
                )
                return True
            if request["intent"] != "query":
                await self.reply_text(
                    update.message,
                    "Benny SQL hanya menjawab analisis read-only dari data keuangan pribadi.",
                )
                return True
            columns, rows = await asyncio.to_thread(
                self.execute, snapshot["rows"], request.get("sql", "")
            )
        except FinanceSqlError as error:
            await self.reply_text(
                update.message,
                "Layanan analitik sementara tidak tersedia."
                if str(error) == "provider_failed"
                else "Query analitik tidak aman atau tidak dapat dipahami.",
            )
            return True
        except (sqlite3.Error, ValueError):
            await self.reply_text(update.message, "Query analitik tidak aman atau tidak dapat dijalankan.")
            return True

        for answer in self.format_answers(columns, rows, text, snapshot["truncated"], request):
            await self.reply_text(update.message, answer, parse_mode="HTML")
        return True

    @classmethod
    def validate(cls, sql):
        sql = (sql or "").strip()
        if not sql or "--" in sql or "/*" in sql or "*/" in sql:
            raise ValueError("invalid SQL")
        sql = sql[:-1].rstrip() if sql.endswith(";") else sql
        if ";" in sql or not re.match(r"^(select|with)\b", sql, re.IGNORECASE):
            raise ValueError("one SELECT required")
        if cls.FORBIDDEN_SQL.search(sql):
            raise ValueError("write SQL rejected")
        tables = re.findall(r"\b(?:from|join)\s+([a-z_][a-z0-9_]*)", sql, re.IGNORECASE)
        ctes = {
            name.lower() for name in re.findall(
                r"(?:\bwith|,)\s*([a-z_][a-z0-9_]*)\s+as\s*\(", sql, re.IGNORECASE
            )
        }
        if "ledger" not in {table.lower() for table in tables} or any(
            table.lower() not in {"ledger", *ctes} for table in tables
        ):
            raise ValueError("ledger only")
        detail = not re.search(r"\b(count|sum|avg|min|max)\s*\(|\bgroup\s+by\b", sql, re.IGNORECASE)
        limit = re.search(r"\blimit\s+(\d+)\b", sql, re.IGNORECASE)
        if detail and not limit:
            raise ValueError("detail query requires LIMIT")
        if limit and not 1 <= int(limit.group(1)) <= 100:
            raise ValueError("unsafe LIMIT")
        return sql

    @classmethod
    def execute(cls, ledger, sql):
        sql = cls.validate(sql)
        connection = sqlite3.connect(":memory:")
        try:
            connection.execute(
                "CREATE TABLE ledger(kind TEXT, date TEXT, time TEXT, name TEXT, category TEXT, "
                "amount INTEGER, notes TEXT, location TEXT)"
            )
            connection.executemany(
                "INSERT INTO ledger VALUES(?,?,?,?,?,?,?,?)",
                [(
                    row.get("kind", ""), row.get("date", ""), row.get("time", ""),
                    row.get("name", ""), row.get("category", ""), row.get("amount", 0),
                    row.get("notes", ""), row.get("location", ""),
                ) for row in ledger],
            )

            denied = {
                sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE,
                sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_DROP_TABLE,
                sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH,
                sqlite3.SQLITE_PRAGMA, sqlite3.SQLITE_TRANSACTION,
            }

            def authorize(action, arg1, arg2, _db, _source):
                if action in denied:
                    return sqlite3.SQLITE_DENY
                if action == sqlite3.SQLITE_READ and arg1 != "ledger":
                    return sqlite3.SQLITE_DENY
                if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() not in cls.FUNCTIONS:
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK

            connection.set_authorizer(authorize)
            connection.set_progress_handler(lambda: 1, 100_000)
            cursor = connection.execute(sql)
            rows = cursor.fetchmany(101)
            if len(rows) > 100:
                raise ValueError("result limit exceeded")
            return [column[0] for column in cursor.description], rows
        finally:
            connection.close()

    @classmethod
    def format_answers(cls, columns, rows, question, truncated=False, request=None):
        if not rows:
            return ["Data Belum Ditemukan\n\nTidak ada transaksi yang cocok dengan permintaanmu."]

        def label(column):
            labels = {
                "category": "Kategori", "kind": "Jenis", "name": "Transaksi",
                "date": "Tanggal", "time": "Waktu", "notes": "Note",
                "location": "Lokasi", "amount": "Harga",
            }
            return labels.get(column.lower(), column.replace("_", " ").strip().capitalize())

        def value(column, raw):
            if raw is None:
                return "-"
            if column.lower() == "category":
                return ExpenseReportService.CATEGORY_LABELS.get(str(raw), str(raw))
            if isinstance(raw, (int, float)) and cls.MONEY_COLUMNS.search(column):
                return f"Rp{int(round(raw)):,}".replace(",", ".")
            if isinstance(raw, float):
                return f"{raw:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return str(raw)

        lowered = [column.lower() for column in columns]
        detail = (
            any(column in lowered for column in ("name", "transaksi"))
            and any(column in lowered for column in ("date", "time"))
        )
        ranking = bool(re.search(r"\b(paling|terbesar|tertinggi|terbanyak|top)\b", question, re.IGNORECASE))
        comparison = bool(re.search(r"\b(bandingkan|perbandingan|dibanding|selisih)\b", question, re.IGNORECASE))
        money_indexes = [index for index, column in enumerate(columns) if cls.MONEY_COLUMNS.search(column)]
        response_type = (
            "transaction_list" if detail else
            "comparison" if comparison else
            "ranking" if ranking else
            "category_breakdown" if "category" in lowered and len(rows) > 1 else
            "financial_summary" if len(rows) == 1 and money_indexes else
            "generic_answer"
        )
        titles = {
            "transaction_list": "Daftar Transaksi",
            "comparison": "Perbandingan Keuangan",
            "ranking": "Pengeluaran Terbesar",
            "category_breakdown": "Pengeluaran per Kategori",
            "financial_summary": "Ringkasan Keuangan",
            "generic_answer": "Hasil Keuangan",
        }
        structured = {
            "response_type": response_type,
            "title": titles[response_type],
            "primary_value": (
                rows[0][money_indexes[0]]
                if len(rows) == 1 and money_indexes
                and response_type in {"financial_summary", "ranking"}
                else None
            ),
            "currency": "IDR",
            "details": [],
        }
        blocks = []
        for index, row in enumerate(rows, 1):
            values = dict(zip(lowered, row))
            if detail:
                transaction = next((values[key] for key in ("transaksi", "name") if key in values), "-")
                amount_key = next((key for key in ("harga", "amount", "nominal") if key in values), None)
                note = next((values[key] for key in ("note", "notes") if key in values), "")
                location = next((values[key] for key in ("lokasi", "location") if key in values), "")
                occurred = " ".join(str(values[key]) for key in ("date", "time") if values.get(key)) or "-"
                lines = [f"{index}. {html.escape(str(transaction))}"]
                if amount_key:
                    lines.append(f"   <b>{value(amount_key, values[amount_key])}</b>")
                lines.append(f"   {html.escape(occurred)}")
                if note:
                    lines.append(f"   Catatan: {html.escape(str(note))}")
                if location:
                    lines.append(f"   Lokasi: {html.escape(str(location))}")
            else:
                lines = [
                    f"{html.escape(label(column))}: "
                    f"{'<b>' if cls.MONEY_COLUMNS.search(column) else ''}{html.escape(value(column, raw))}"
                    f"{'</b>' if cls.MONEY_COLUMNS.search(column) else ''}"
                    for column, raw in zip(columns, row)
                ]
            block = "\n".join(lines)
            if not detail and len(rows) > 1:
                block = f"{index}. {block}"
            blocks.append(block)
            structured["details"].append(values)

        primary = structured["primary_value"]
        header = html.escape(structured["title"])
        if primary is not None:
            header += f"\n\n<b>{value(columns[money_indexes[0]], primary)}</b>"
            if len(columns) == 1:
                blocks = []
        footer = ""
        if truncated:
            footer = "\n\nAnalisis dibatasi pada 10.000 transaksi terbaru."
        chunks, current = [], header
        for block in blocks:
            addition = f"\n\n{block}"
            if len(current) + len(addition) + len(footer) > 3900 and current != header:
                chunks.append(current)
                current = f"{html.escape(structured['title'])} (lanjutan)" + addition
            else:
                current += addition
        if len(current) + len(footer) <= 4000:
            current += footer
        else:
            chunks.append(current)
            current = footer.strip()
        chunks.append(current)
        return chunks
