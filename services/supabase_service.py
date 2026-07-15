"""
Supabase Service — Database operations for Benny Bot.
Replaces Google Sheets with Supabase (PostgreSQL).

Architecture:
    - Singleton pattern for connection reuse
    - All methods return typed results (bool, List, Dict, Optional)
    - Consistent error handling with structured logging
"""

from supabase import create_client, Client
from config import Config
from typing import List, Dict, Optional
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)


class SupabaseService:
    """Supabase database service — singleton pattern."""

    _instance = None
    _client: Client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is None:
            self._client = create_client(
                Config.SUPABASE_URL,
                Config.SUPABASE_KEY,
            )
            logger.info("✅ Supabase client initialized")

    @property
    def client(self) -> Client:
        return self._client

    # ─── TRANSACTIONS ────────────────────────────────────

    def _write_rows(
        self, table: str, user_id: str, rows: List[Dict], operation_id: Optional[str]
    ) -> Dict:
        """Write rows and return database-confirmed records."""
        if not user_id or not rows:
            return {"ok": False, "records": [], "error": "invalid_transaction"}

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
        except Exception as e:
            logger.error(f"❌ Write to {table} failed: {e}")
            return {"ok": False, "records": [], "error": "database_write_failed"}

    def add_transactions_bulk(
        self,
        user_id: str,
        transactions: List[Dict],
        operation_id: Optional[str] = None,
    ) -> Dict:
        """Insert expense transactions and return confirmed records."""
        try:
            now = datetime.now()
            today_str = date.today().isoformat()
            time_str = now.strftime("%H:%M")

            def get_valid_date(val):
                return today_str if not val or str(val).lower() == 'null' else str(val)

            def get_valid_time(val):
                return time_str if not val or str(val).lower() == 'null' else str(val)

            rows = [
                {
                    "user_id": user_id,
                    "date": get_valid_date(tx.get("date")),
                    "time": get_valid_time(tx.get("time")),
                    "item_name": tx.get("item", ""),
                    "category": tx.get("category", "Other"),
                    "amount": int(tx.get("amount", 0)),
                    "location": tx.get("location", ""),
                    "payment_method": tx.get("payment_method", ""),
                    "notes": tx.get("notes", ""),
                }
                for tx in transactions
            ]

            if any(not row["item_name"] or row["amount"] <= 0 for row in rows):
                return {"ok": False, "records": [], "error": "invalid_transaction"}

            return self._write_rows("transactions", user_id, rows, operation_id)
        except Exception as e:
            logger.error(f"❌ Insert transactions failed: {e}")
            return {"ok": False, "records": [], "error": "invalid_transaction"}

    def get_all_transactions(self, user_id: str) -> List[Dict]:
        """Get all transactions for a user, newest first."""
        try:
            result = (
                self._client.table("transactions")
                .select("*")
                .eq("user_id", user_id)
                .order("date", desc=True)
                .execute()
            )
            return result.data
        except Exception as e:
            logger.error(f"❌ Get transactions failed: {e}")
            return []

    def get_transactions_by_date(
        self, user_id: str, start: str, end: str
    ) -> List[Dict]:
        """Get transactions within a date range (inclusive, YYYY-MM-DD)."""
        try:
            result = (
                self._client.table("transactions")
                .select("*")
                .eq("user_id", user_id)
                .gte("date", start)
                .lte("date", end)
                .order("date", desc=True)
                .execute()
            )
            return result.data
        except Exception as e:
            logger.error(f"❌ Get transactions by date failed: {e}")
            return []

    def update_transaction(self, user_id: str, transaction_id: str, updates: Dict) -> bool:
        """Update one transaction owned by the user."""
        try:
            result = (
                self._client.table("transactions")
                .update(updates)
                .eq("user_id", user_id)
                .eq("id", transaction_id)
                .execute()
            )
            if not result.data:
                return False
            logger.info(f"✅ Transaction {transaction_id} updated successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Update transaction failed: {e}")
            return False

    def delete_transaction(self, user_id: str, transaction_id: str) -> bool:
        """Delete one transaction owned by the user."""
        try:
            result = (
                self._client.table("transactions")
                .delete()
                .eq("user_id", user_id)
                .eq("id", transaction_id)
                .execute()
            )
            if not result.data:
                return False
            logger.info(f"✅ Transaction {transaction_id} deleted successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Delete transaction failed: {e}")
            return False

    def delete_operation(self, user_id: str, table: str, operation_id: str) -> bool:
        """Delete records created by one idempotent capture operation."""
        if table not in {"transactions", "income"} or not operation_id:
            return False

        try:
            result = (
                self._client.table(table)
                .delete()
                .eq("user_id", user_id)
                .like("operation_id", f"{operation_id}:%")
                .execute()
            )
            return bool(result.data)
        except Exception as e:
            logger.error(f"❌ Delete capture operation failed: {e}")
            return False

    def get_record(self, user_id: str, table: str, record_id: str) -> Optional[Dict]:
        """Fetch one user-owned expense or income record."""
        if table not in {"transactions", "income"}:
            return None

        try:
            result = (
                self._client.table(table)
                .select("*")
                .eq("user_id", user_id)
                .eq("id", record_id)
                .limit(1)
                .execute()
            )
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"❌ Get record failed: {e}")
            return None

    def get_recent_transactions(self, user_id: str, limit: int = 50) -> List[Dict]:
        """Get recent transactions for a user, newest first, with limit."""
        try:
            result = (
                self._client.table("transactions")
                .select("*")
                .eq("user_id", user_id)
                .order("date", desc=True)
                .order("time", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data
        except Exception as e:
            logger.error(f"❌ Get recent transactions failed: {e}")
            return []

    # ─── INCOME ──────────────────────────────────────────

    def add_income(
        self,
        user_id: str,
        transactions: List[Dict],
        operation_id: Optional[str] = None,
    ) -> Dict:
        """Insert income records and return confirmed records."""
        try:
            now = datetime.now()
            today_str = date.today().isoformat()
            time_str = now.strftime("%H:%M")

            def get_valid_date(val):
                return today_str if not val or str(val).lower() == 'null' else str(val)

            def get_valid_time(val):
                return time_str if not val or str(val).lower() == 'null' else str(val)

            rows = [
                {
                    "user_id": user_id,
                    "date": get_valid_date(tx.get("date")),
                    "time": get_valid_time(tx.get("time")),
                    "source": tx.get("source", ""),
                    "category": tx.get("category", "Income"),
                    "amount": int(tx.get("amount", 0)),
                    "notes": tx.get("notes", ""),
                }
                for tx in transactions
            ]

            if any(not row["source"] or row["amount"] <= 0 for row in rows):
                return {"ok": False, "records": [], "error": "invalid_transaction"}

            return self._write_rows("income", user_id, rows, operation_id)
        except Exception as e:
            logger.error(f"❌ Insert income failed: {e}")
            return {"ok": False, "records": [], "error": "invalid_transaction"}

    def get_income(self, user_id: str) -> List[Dict]:
        """Get all income records for a user, newest first."""
        try:
            result = (
                self._client.table("income")
                .select("*")
                .eq("user_id", user_id)
                .order("date", desc=True)
                .execute()
            )
            return result.data
        except Exception as e:
            logger.error(f"❌ Get income failed: {e}")
            return []

    def update_income(self, user_id: str, income_id: str, updates: Dict) -> bool:
        """Update one income record owned by the user."""
        try:
            result = (
                self._client.table("income")
                .update(updates)
                .eq("user_id", user_id)
                .eq("id", income_id)
                .execute()
            )
            return bool(result.data)
        except Exception as e:
            logger.error(f"❌ Update income failed: {e}")
            return False

    def delete_income(self, user_id: str, income_id: str) -> bool:
        """Delete one income record owned by the user."""
        try:
            result = (
                self._client.table("income")
                .delete()
                .eq("user_id", user_id)
                .eq("id", income_id)
                .execute()
            )
            return bool(result.data)
        except Exception as e:
            logger.error(f"❌ Delete income failed: {e}")
            return False

    # ─── GOALS ───────────────────────────────────────────

    def _mutate_goal(
        self,
        user_id: str,
        action: str,
        goal_id: Optional[int] = None,
        name: Optional[str] = None,
        target: Optional[int] = None,
        deadline: Optional[str] = None,
        amount: Optional[int] = None,
    ) -> Optional[Dict]:
        """Run a goal mutation and its audit write in one database transaction."""
        if not user_id or action not in {"create", "cancel", "contribute", "withdraw"}:
            return None
        try:
            result = self._client.rpc(
                "mutate_goal",
                {
                    "p_user_id": user_id,
                    "p_action": action,
                    "p_goal_id": goal_id,
                    "p_name": name,
                    "p_target_amount": target,
                    "p_deadline": deadline,
                    "p_amount": amount,
                },
            ).execute()
            if isinstance(result.data, list):
                return result.data[0] if result.data else None
            return result.data if isinstance(result.data, dict) else None
        except Exception as e:
            logger.error(f"Goal {action} failed: {e}")
            return None

    def create_goal(
        self,
        user_id: str,
        name: str,
        target: int,
        deadline: Optional[str] = None,
    ) -> bool:
        """Create a new financial goal."""
        try:
            if self._mutate_goal(
                user_id, "create", name=name, target=target, deadline=deadline
            ) is None:
                return False
            logger.info(f"✅ Goal '{name}' created for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Create goal failed: {e}")
            return False

    def get_goals(self, user_id: str) -> List[Dict]:
        """Get all active goals for a user."""
        try:
            result = (
                self._client.table("goals")
                .select("*")
                .eq("user_id", user_id)
                .neq("status", "cancelled")
                .execute()
            )
            return result.data
        except Exception as e:
            logger.error(f"❌ Get goals failed: {e}")
            return []

    def contribute_goal(self, user_id: str, goal_id: int, amount: int) -> Optional[Dict]:
        return self._mutate_goal(user_id, "contribute", goal_id=goal_id, amount=amount)

    def withdraw_goal(self, user_id: str, goal_id: int, amount: int) -> Optional[Dict]:
        return self._mutate_goal(user_id, "withdraw", goal_id=goal_id, amount=amount)

    def get_goal_history(
        self, user_id: str, goal_id: int, limit: int = 20
    ) -> List[Dict]:
        """Get newest audit entries for one user-owned goal."""
        try:
            result = (
                self._client.table("goal_history")
                .select("*")
                .eq("user_id", user_id)
                .eq("goal_id", goal_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data
        except Exception as e:
            logger.error(f"Get goal history failed: {e}")
            return []

    def delete_goal(self, user_id: str, goal_id: int) -> bool:
        """Soft-delete a goal by marking it as cancelled."""
        try:
            return self._mutate_goal(user_id, "cancel", goal_id=goal_id) is not None
        except Exception as e:
            logger.error(f"❌ Delete goal failed: {e}")
            return False

    # ─── BUDGETS ─────────────────────────────────────────

    def set_budget(self, user_id: str, category: str, limit: int) -> bool:
        """Create or update a monthly budget for a category (upsert)."""
        try:
            self._client.table("budgets").upsert(
                {
                    "user_id": user_id,
                    "category": category,
                    "monthly_limit": limit,
                    "updated_at": datetime.now().isoformat(),
                },
                on_conflict="user_id,category"
            ).execute()
            return True
        except Exception as e:
            logger.error(f"❌ Set budget failed: {e}")
            return False

    def get_budgets(self, user_id: str) -> List[Dict]:
        """Get all budgets for a user."""
        try:
            result = (
                self._client.table("budgets")
                .select("*")
                .eq("user_id", user_id)
                .execute()
            )
            return result.data
        except Exception as e:
            logger.error(f"❌ Get budgets failed: {e}")
            return []

    def delete_budget(self, user_id: str, category: str) -> bool:
        """Delete a budget by user + category."""
        try:
            (
                self._client.table("budgets")
                .delete()
                .eq("user_id", user_id)
                .eq("category", category)
                .execute()
            )
            return True
        except Exception as e:
            logger.error(f"❌ Delete budget failed: {e}")
            return False

    # ─── USER PROFILES ───────────────────────────────────

    def upsert_user(self, user_id: str, data: Dict) -> bool:
        """Create or update a user profile."""
        try:
            data["user_id"] = user_id
            data["last_active"] = datetime.now().isoformat()
            self._client.table("user_profiles").upsert(data, on_conflict="user_id").execute()
            return True
        except Exception as e:
            logger.error(f"❌ Upsert user failed: {e}")
            return False

    def get_user(self, user_id: str) -> Optional[Dict]:
        """Get a single user profile, or None if not found."""
        try:
            result = (
                self._client.table("user_profiles")
                .select("*")
                .eq("user_id", user_id)
                .single()
                .execute()
            )
            return result.data
        except Exception:
            return None

    def save_user_profile(self, user_id: str, full_name: str, nickname: str, birthday: str) -> bool:
        """Save onboarding profile data (full_name, nickname, birthday) for a user."""
        try:
            self._client.table("user_profiles").upsert({
                "user_id": user_id,
                "full_name": full_name,
                "nickname": nickname,
                "birthday": birthday,
                "last_active": datetime.now().isoformat(),
            }, on_conflict="user_id").execute()
            logger.info(f"✅ Profile saved for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Save profile failed: {e}")
            return False

    # ─── CHAT HISTORY ────────────────────────────────────

    def add_chat(self, user_id: str, role: str, message: str) -> bool:
        """Append a chat message (role = 'user' | 'assistant')."""
        try:
            self._client.table("chat_history").insert(
                {
                    "user_id": user_id,
                    "role": role,
                    "message": message,
                }
            ).execute()
            return True
        except Exception as e:
            logger.error(f"❌ Add chat failed: {e}")
            return False

    def get_chat_history(self, user_id: str, limit: int = 20) -> List[Dict]:
        """Get recent chat history, oldest-first (chronological)."""
        try:
            result = (
                self._client.table("chat_history")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            # Reverse so oldest message comes first (chronological order)
            return list(reversed(result.data))
        except Exception as e:
            logger.error(f"❌ Get chat history failed: {e}")
            return []

    # ─── USER CONTEXT ────────────────────────────────────

    def set_context(self, user_id: str, context: Dict) -> bool:
        """Store or update user context as JSONB."""
        try:
            self._client.table("user_context").upsert(
                {
                    "user_id": user_id,
                    "context_data": context,
                    "updated_at": datetime.now().isoformat(),
                },
                on_conflict="user_id"
            ).execute()
            return True
        except Exception as e:
            logger.error(f"❌ Set context failed: {e}")
            return False

    def get_context(self, user_id: str) -> Dict:
        """Retrieve user context, or empty dict if not found."""
        try:
            result = (
                self._client.table("user_context")
                .select("context_data")
                .eq("user_id", user_id)
                .single()
                .execute()
            )
            return result.data.get("context_data", {})
        except Exception:
            return {}

    # ─── RAG / KNOWLEDGE BASE ────────────────────────────

    def search_knowledge_base(self, query_embedding: List[float], limit: int = 3, threshold: float = 0.5) -> List[Dict]:
        """Search the knowledge base using vector similarity."""
        try:
            result = self._client.rpc(
                'match_kb_documents',
                {
                    'query_embedding': query_embedding,
                    'match_threshold': threshold,
                    'match_count': limit
                }
            ).execute()
            return result.data
        except Exception as e:
            logger.error(f"❌ Search knowledge base failed: {e}")
            return []
