"""Supabase adapter for finance capture and explicit conversation memory."""

import logging
from datetime import date, datetime
from typing import Dict, List, Optional

from supabase import Client, create_client

from config import Config

logger = logging.getLogger(__name__)


class SupabaseService:
    """Keep ledger persistence and ownership checks in one boundary."""

    _instance = None
    _client: Client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is None:
            self._client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
            logger.info("Supabase client initialized")

    @staticmethod
    def _invalid_result() -> Dict:
        return {"ok": False, "records": [], "error": "invalid_transaction"}

    @staticmethod
    def _rows(user_id: str, transactions: List[Dict], income: bool) -> List[Dict]:
        now = datetime.now()
        current_date, current_time = date.today().isoformat(), now.strftime("%H:%M")

        def value(raw, default):
            return default if not raw or str(raw).lower() == "null" else str(raw)

        rows = []
        for transaction in transactions:
            row = {
                "user_id": user_id,
                "date": value(transaction.get("date"), current_date),
                "time": value(transaction.get("time"), current_time),
                "category": transaction.get("category", "Income" if income else "Other"),
                "amount": int(transaction.get("amount", 0)),
                "notes": transaction.get("notes", ""),
            }
            if income:
                row["source"] = transaction.get("source", "")
            else:
                row.update({
                    "item_name": transaction.get("item", ""),
                    "location": transaction.get("location", ""),
                    "payment_method": transaction.get("payment_method", ""),
                })
            rows.append(row)
        return rows

    def _write_rows(
        self, table: str, user_id: str, rows: List[Dict], operation_id: Optional[str]
    ) -> Dict:
        if not user_id or not rows:
            return self._invalid_result()
        try:
            if operation_id:
                for index, row in enumerate(rows):
                    row["operation_id"] = f"{operation_id}:{index}"
                result = self._client.table(table).upsert(
                    rows, on_conflict="user_id,operation_id"
                ).execute()
            else:
                result = self._client.table(table).insert(rows).execute()
            records = result.data or []
            confirmed = len(records) == len(rows)
            return {
                "ok": confirmed,
                "records": records,
                "error": None if confirmed else "write_not_confirmed",
            }
        except Exception as error:
            logger.error("Write to %s failed: %s", table, error)
            return {"ok": False, "records": [], "error": "database_write_failed"}

    def _add(
        self, table: str, user_id: str, transactions: List[Dict], operation_id=None
    ) -> Dict:
        income = table == "income"
        try:
            rows = self._rows(user_id, transactions, income)
            name = "source" if income else "item_name"
            if any(not row[name] or row["amount"] <= 0 for row in rows):
                return self._invalid_result()
            return self._write_rows(table, user_id, rows, operation_id)
        except (TypeError, ValueError) as error:
            logger.warning("Invalid %s transaction: %s", table, error)
            return self._invalid_result()

    def add_transactions_bulk(
        self, user_id: str, transactions: List[Dict], operation_id=None
    ) -> Dict:
        return self._add("transactions", user_id, transactions, operation_id)

    def add_income(
        self, user_id: str, transactions: List[Dict], operation_id=None
    ) -> Dict:
        return self._add("income", user_id, transactions, operation_id)

    def _update_record(
        self, table: str, user_id: str, record_id: str, updates: Dict, name_field: str
    ) -> bool:
        updates = dict(updates or {})
        if "item" in updates and name_field not in updates:
            updates[name_field] = updates.pop("item")
        common = {"category", "amount", "date", "time", "notes"}
        allowed = common | ({"source"} if table == "income" else {
            "item_name", "location", "payment_method"
        })
        updates = {key: value for key, value in updates.items() if key in allowed}
        try:
            if "amount" in updates:
                updates["amount"] = int(updates["amount"])
            if not updates or updates.get("amount", 1) <= 0:
                return False
            result = (
                self._client.table(table).update(updates)
                .eq("user_id", user_id).eq("id", record_id).execute()
            )
            return bool(result.data)
        except (TypeError, ValueError):
            return False
        except Exception as error:
            logger.error("Update %s failed: %s", table, error)
            return False

    def update_transaction(self, user_id: str, record_id: str, updates: Dict) -> bool:
        return self._update_record(
            "transactions", user_id, record_id, updates, "item_name"
        )

    def update_income(self, user_id: str, record_id: str, updates: Dict) -> bool:
        return self._update_record("income", user_id, record_id, updates, "source")

    def delete_transaction(self, user_id: str, record_id: str) -> bool:
        """Delete one expense; retained as the narrow public ledger operation."""
        try:
            result = (
                self._client.table("transactions").delete()
                .eq("user_id", user_id).eq("id", record_id).execute()
            )
            return bool(result.data)
        except Exception as error:
            logger.error("Delete transaction failed: %s", error)
            return False

    def delete_operation(self, user_id: str, table: str, operation_id: str) -> bool:
        if table not in {"transactions", "income"} or not operation_id:
            return False
        try:
            result = (
                self._client.table(table).delete().eq("user_id", user_id)
                .like("operation_id", f"{operation_id}:%").execute()
            )
            return bool(result.data)
        except Exception as error:
            logger.error("Delete capture operation failed: %s", error)
            return False

    def get_record(self, user_id: str, table: str, record_id: str) -> Optional[Dict]:
        if table not in {"transactions", "income"}:
            return None
        try:
            result = (
                self._client.table(table).select("*").eq("user_id", user_id)
                .eq("id", record_id).limit(1).execute()
            )
            return result.data[0] if result.data else None
        except Exception as error:
            logger.error("Get record failed: %s", error)
            return None

    def get_expenses_between(self, user_id: str, start: datetime, end: datetime):
        """Read user-owned expenses in an inclusive local datetime range."""
        try:
            result = (
                self._client.table("transactions").select("*")
                .eq("user_id", user_id)
                .gte("date", start.date().isoformat())
                .lte("date", end.date().isoformat())
                .order("date").order("time").execute()
            )
            rows = []
            for row in result.data or []:
                occurred = datetime.fromisoformat(
                    f"{row['date']}T{str(row['time']).split('+')[0]}"
                ).replace(tzinfo=start.tzinfo)
                if start <= occurred <= end:
                    rows.append(row)
            return rows
        except Exception as error:
            logger.error("Expense report query failed: %s", error)
            return None

    def get_finance_snapshot(self, user_id: str, limit: int = 10_000):
        """Return a user-scoped, read-only ledger snapshot for local analytics."""
        try:
            rows = []
            for table, kind, name, extra in (
                ("transactions", "expense", "item_name", ",notes,location"),
                ("income", "income", "source", ",notes"),
            ):
                result = (
                    self._client.table(table)
                    .select(f"date,time,{name},category,amount{extra}")
                    .eq("user_id", user_id)
                    .order("date", desc=True)
                    .order("time", desc=True)
                    .limit(limit + 1)
                    .execute()
                )
                rows.extend({
                    "kind": kind,
                    "date": str(row["date"]),
                    "time": str(row["time"]).split("+")[0],
                    "name": str(row.get(name) or ""),
                    "category": str(row.get("category") or "Other"),
                    "amount": int(row["amount"]),
                    "notes": str(row.get("notes") or ""),
                    "location": str(row.get("location") or ""),
                } for row in result.data or [])
            rows.sort(key=lambda row: (row["date"], row["time"]), reverse=True)
            return {"rows": rows[:limit], "truncated": len(rows) > limit}
        except (KeyError, TypeError, ValueError) as error:
            logger.error("Invalid finance snapshot data: %s", type(error).__name__)
            return None
        except Exception as error:
            logger.error("Finance snapshot query failed: %s", type(error).__name__)
            return None

    def upsert_user(self, user_id: str, data: Dict) -> bool:
        try:
            profile = {
                **data,
                "user_id": user_id,
                "last_active": datetime.now().isoformat(),
            }
            self._client.table("user_profiles").upsert(
                profile, on_conflict="user_id"
            ).execute()
            return True
        except Exception as error:
            logger.error("Upsert user failed: %s", error)
            return False

    def get_or_create_chat_session(self, user_id: str, chat_id: str) -> Optional[str]:
        try:
            query = (
                self._client.table("chat_sessions").select("id")
                .eq("user_id", user_id).eq("telegram_chat_id", chat_id)
                .eq("status", "active").limit(1).execute()
            )
            if query.data:
                return query.data[0]["id"]
            created = self._client.table("chat_sessions").insert({
                "user_id": user_id,
                "telegram_chat_id": chat_id,
            }).execute()
            return created.data[0]["id"] if created.data else None
        except Exception as error:
            logger.error("Get or create chat session failed: %s", error)
            return None

    def add_chat_message(
        self, user_id: str, chat_id: str, role: str, content: str,
        telegram_message_id: Optional[int] = None,
    ) -> bool:
        if role not in {"user", "assistant"} or not content:
            return False
        session_id = self.get_or_create_chat_session(user_id, chat_id)
        if not session_id:
            return False
        try:
            row = {
                "session_id": session_id,
                "user_id": user_id,
                "role": role,
                "content": content[:4000],
            }
            if telegram_message_id is not None:
                row["telegram_message_id"] = telegram_message_id
            self._client.table("chat_messages").upsert(
                row, on_conflict="session_id,telegram_message_id,role"
            ).execute()
            self._client.table("chat_sessions").update({
                "last_message_at": datetime.now().isoformat()
            }).eq("id", session_id).eq("user_id", user_id).execute()
            return True
        except Exception as error:
            logger.error("Add chat message failed: %s", error)
            return False

    def get_recent_chat_messages(
        self, user_id: str, chat_id: str, limit: int = 6
    ) -> List[Dict]:
        session_id = self.get_or_create_chat_session(user_id, chat_id)
        if not session_id:
            return []
        try:
            result = (
                self._client.table("chat_messages").select("role,content,created_at")
                .eq("user_id", user_id).eq("session_id", session_id)
                .order("created_at", desc=True).limit(max(1, min(limit, 12))).execute()
            )
            return list(reversed(result.data or []))
        except Exception as error:
            logger.error("Get recent chat messages failed: %s", error)
            return []

    def get_explicit_memories(self, user_id: str) -> List[Dict]:
        try:
            result = (
                self._client.table("user_preferences")
                .select("preference_key,preference_value,updated_at")
                .eq("user_id", user_id).eq("source", "explicit")
                .eq("is_active", True).order("updated_at").execute()
            )
            return result.data or []
        except Exception as error:
            logger.error("Get explicit memories failed: %s", error)
            return []

    def upsert_explicit_memory(self, user_id: str, key: str, text: str) -> bool:
        try:
            result = self._client.table("user_preferences").upsert({
                "user_id": user_id,
                "preference_key": key,
                "preference_value": {"text": text},
                "source": "explicit",
                "confidence": 1,
                "is_active": True,
                "observed_at": datetime.now().isoformat(),
            }, on_conflict="user_id,preference_key").execute()
            return bool(result.data)
        except Exception as error:
            logger.error("Upsert explicit memory failed: %s", error)
            return False

    def forget_explicit_memory(self, user_id: str, key: str) -> bool:
        try:
            result = (
                self._client.table("user_preferences").update({"is_active": False})
                .eq("user_id", user_id).eq("preference_key", key)
                .eq("source", "explicit").execute()
            )
            return bool(result.data)
        except Exception as error:
            logger.error("Forget explicit memory failed: %s", error)
            return False
