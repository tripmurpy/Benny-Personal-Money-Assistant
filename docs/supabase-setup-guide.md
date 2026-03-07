# 🚀 Panduan Setup Supabase untuk Benny Bot

Panduan lengkap untuk mengganti Google Sheets dengan **Supabase** (PostgreSQL) sebagai database utama project Benny.

---

## 1. Buat Akun & Project Supabase

### 1.1 Buat Akun
1. Buka [supabase.com](https://supabase.com) → klik **Start your project**
2. Sign up pakai **GitHub** (paling gampang)
3. Setelah login, klik **New Project**

### 1.2 Setup Project
| Field | Isi |
|-------|-----|
| **Organization** | Pilih org kamu (atau buat baru) |
| **Project Name** | `benny-finance-bot` |
| **Database Password** | Catat baik-baik! Ini password PostgreSQL kamu |
| **Region** | Pilih **Southeast Asia (Singapore)** — paling dekat dari Indonesia |
| **Plan** | Free Plan (cukup untuk development) |

4. Klik **Create new project** — tunggu ~2 menit sampai selesai provisioning

> [!IMPORTANT]
> **Simpan Database Password!** Password ini tidak bisa dilihat lagi setelah project dibuat. Kalau lupa, harus reset.

---

## 2. Ambil Credentials (API Keys)

Setelah project selesai dibuat:

1. Buka **Project Settings** (ikon gear ⚙️ di sidebar kiri bawah)
2. Klik **API** di menu kiri
3. Catat 3 hal ini:

| Credential | Lokasi | Kegunaan |
|------------|--------|----------|
| **Project URL** | `Project URL` di bagian atas | Base URL untuk API calls |
| **anon (public) key** | `Project API keys` → `anon` `public` | Untuk client-side (read) |
| **service_role key** | `Project API keys` → `service_role` `secret` | Untuk server-side (full access) — **JANGAN expose ke client!** |

> [!CAUTION]
> **`service_role` key** punya akses full ke database, bypass Row Level Security (RLS). Hanya gunakan di backend (server-side). Jangan pernah commit ke Git!

---

## 3. Buat Tabel Database

Kamu punya 2 opsi: **via Dashboard (GUI)** atau **via SQL Editor**. Saya rekomendasikan SQL Editor karena lebih cepat dan reproducible.

### 3.1 Buka SQL Editor
1. Di sidebar kiri Supabase Dashboard, klik **SQL Editor**
2. Klik **New query**
3. Paste SQL di bawah, lalu klik **Run**

### 3.2 SQL Schema (sesuai data model Benny)

> [!NOTE]
> **Design decisions:**
> - **`user_profiles` dibuat pertama** — karena tabel lain merujuk ke sini via Foreign Key.
> - **`BIGINT` untuk semua kolom uang** — Rupiah bisa sangat besar (jutaan–miliaran). `INTEGER` max ~2.1M, `BIGINT` max ~9.2 quintillion. Lebih aman untuk jangka panjang.
> - **Foreign Key `ON DELETE CASCADE`** — kalau user dihapus, semua data terkait (transaksi, goals, budgets, dll) ikut terhapus otomatis. Menjaga referential integrity.

```sql
-- ============================================
-- BENNY FINANCE BOT - SUPABASE SCHEMA
-- ============================================
-- ⚠️ URUTAN PENTING: user_profiles HARUS dibuat pertama
-- karena tabel lain merujuk ke sini via Foreign Key.

-- 1. Tabel User Profiles (HARUS PERTAMA — referenced by FK)
CREATE TABLE user_profiles (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    language TEXT DEFAULT 'id',
    timezone TEXT DEFAULT 'Asia/Jakarta',
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    last_active TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Tabel Transaksi (pengeluaran) — menggantikan sheet "Expenses"
CREATE TABLE transactions (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL
        REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    time TIME NOT NULL DEFAULT CURRENT_TIME,
    item_name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'Other',
    amount BIGINT NOT NULL,          -- BIGINT: aman untuk nominal Rupiah besar
    location TEXT DEFAULT '',
    payment_method TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Tabel Income — menggantikan sheet "Budget" (income rows)
CREATE TABLE income (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL
        REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    time TIME NOT NULL DEFAULT CURRENT_TIME,
    source TEXT NOT NULL,            -- sumber income
    category TEXT NOT NULL DEFAULT 'Income',
    amount BIGINT NOT NULL,          -- BIGINT
    notes TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Tabel Goals — menggantikan sheet "Goals"
CREATE TABLE goals (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL
        REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    target_amount BIGINT NOT NULL,   -- BIGINT
    current_amount BIGINT DEFAULT 0, -- BIGINT
    deadline DATE,
    status TEXT DEFAULT 'active',    -- active, completed, cancelled
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Tabel Budgets — menggantikan sheet "Budgets"
CREATE TABLE budgets (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL
        REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    monthly_limit BIGINT NOT NULL,   -- BIGINT
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, category)
);

-- 6. Tabel Chat History — menggantikan sheet "ChatHistory"
CREATE TABLE chat_history (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT NOT NULL
        REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    role TEXT NOT NULL,              -- 'user' atau 'assistant'
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Tabel User Context — menggantikan sheet "UserContext"
CREATE TABLE user_context (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT UNIQUE NOT NULL
        REFERENCES user_profiles(user_id) ON DELETE CASCADE,
    context_data JSONB DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- INDEXES untuk performa query
-- ============================================
CREATE INDEX idx_transactions_user_date ON transactions(user_id, date);
CREATE INDEX idx_transactions_category ON transactions(category);
CREATE INDEX idx_income_user_date ON income(user_id, date);
CREATE INDEX idx_goals_user ON goals(user_id);
CREATE INDEX idx_budgets_user ON budgets(user_id);
CREATE INDEX idx_chat_history_user ON chat_history(user_id, created_at);

-- ============================================
-- ROW LEVEL SECURITY (opsional, tapi recommended)
-- ============================================
-- Karena kita pakai service_role key di backend,
-- RLS tidak wajib. Tapi bagus untuk keamanan extra.

ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE income ENABLE ROW LEVEL SECURITY;
ALTER TABLE goals ENABLE ROW LEVEL SECURITY;
ALTER TABLE budgets ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_context ENABLE ROW LEVEL SECURITY;

-- Policy: service_role bisa akses semua
-- (ini default behavior, tapi kita explicit-kan)
CREATE POLICY "Service role full access" ON transactions
    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON income
    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON goals
    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON budgets
    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON user_profiles
    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON chat_history
    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON user_context
    FOR ALL USING (true) WITH CHECK (true);
```

4. Klik **Run** — semua tabel akan terbuat
5. Verifikasi: buka **Table Editor** di sidebar kiri, pastikan semua 7 tabel muncul

---

## 4. Setup di Project Python

### 4.1 Install Library

```bash
pip install supabase
```

Atau tambahkan ke `requirements.txt`:
```
supabase
```

Lalu:
```bash
pip install -r requirements.txt
```

### 4.2 Update `.env`

Tambahkan di file `.env`:

```env
# Supabase
SUPABASE_URL=https://xxxxxxxxxxxxx.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxxxx
```

> Ganti `xxx` dengan **Project URL** dan **service_role key** dari Step 2.

### 4.3 Update `config.py`

Tambahkan config Supabase di class `Config`:

```python
# Di config.py, tambahkan di dalam class Config:

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
```

Dan update validasi:

```python
# Di method validate(), tambahkan:
if not cls.SUPABASE_URL:
    errors.append("SUPABASE_URL missing in .env")
if not cls.SUPABASE_KEY:
    errors.append("SUPABASE_KEY missing in .env")
```

### 4.4 Buat `services/supabase_service.py`

Ini adalah file service baru yang menggantikan peran `sheets_service.py`:

```python
"""
Supabase Service - Database operations for Benny Bot.
Replaces Google Sheets with Supabase (PostgreSQL).
"""

from supabase import create_client, Client
from config import Config
from typing import List, Dict, Optional, Any
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
                Config.SUPABASE_KEY
            )
            logger.info("✅ Supabase client initialized")
    
    @property
    def client(self) -> Client:
        return self._client
    
    # ─── TRANSACTIONS ────────────────────────────────

    def add_transactions_bulk(self, user_id: str, transactions: List[Dict]) -> bool:
        """Insert multiple transactions."""
        try:
            rows = []
            for tx in transactions:
                rows.append({
                    "user_id": user_id,
                    "date": tx.get("date", date.today().isoformat()),
                    "time": tx.get("time", datetime.now().strftime("%H:%M")),
                    "item_name": tx.get("item", ""),
                    "category": tx.get("category", "Other"),
                    "amount": int(tx.get("amount", 0)),
                    "location": tx.get("location", ""),
                    "payment_method": tx.get("payment_method", ""),
                    "notes": tx.get("notes", ""),
                })
            
            self._client.table("transactions").insert(rows).execute()
            logger.info(f"✅ {len(rows)} transactions inserted")
            return True
        except Exception as e:
            logger.error(f"❌ Insert transactions failed: {e}")
            return False

    def get_all_transactions(self, user_id: str) -> List[Dict]:
        """Get all transactions for a user."""
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

    def get_transactions_by_date(self, user_id: str, start: str, end: str) -> List[Dict]:
        """Get transactions between date range (YYYY-MM-DD)."""
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

    # ─── INCOME ──────────────────────────────────────

    def add_income(self, user_id: str, transactions: List[Dict]) -> bool:
        """Insert income transactions."""
        try:
            rows = [{
                "user_id": user_id,
                "date": tx.get("date", date.today().isoformat()),
                "time": tx.get("time", datetime.now().strftime("%H:%M")),
                "source": tx.get("source", ""),
                "category": tx.get("category", "Income"),
                "amount": int(tx.get("amount", 0)),
                "notes": tx.get("notes", ""),
            } for tx in transactions]
            
            self._client.table("income").insert(rows).execute()
            return True
        except Exception as e:
            logger.error(f"❌ Insert income failed: {e}")
            return False

    def get_income(self, user_id: str) -> List[Dict]:
        """Get all income for a user."""
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

    # ─── GOALS ───────────────────────────────────────

    def create_goal(self, user_id: str, name: str, target: int, deadline: str = None) -> bool:
        try:
            self._client.table("goals").insert({
                "user_id": user_id,
                "name": name,
                "target_amount": target,
                "deadline": deadline
            }).execute()
            return True
        except Exception as e:
            logger.error(f"❌ Create goal failed: {e}")
            return False

    def get_goals(self, user_id: str) -> List[Dict]:
        try:
            result = (
                self._client.table("goals")
                .select("*")
                .eq("user_id", user_id)
                .eq("status", "active")
                .execute()
            )
            return result.data
        except Exception as e:
            logger.error(f"❌ Get goals failed: {e}")
            return []

    def update_goal(self, goal_id: int, updates: Dict) -> bool:
        try:
            updates["updated_at"] = datetime.now().isoformat()
            self._client.table("goals").update(updates).eq("id", goal_id).execute()
            return True
        except Exception as e:
            logger.error(f"❌ Update goal failed: {e}")
            return False

    def delete_goal(self, goal_id: int) -> bool:
        try:
            self._client.table("goals").update(
                {"status": "cancelled", "updated_at": datetime.now().isoformat()}
            ).eq("id", goal_id).execute()
            return True
        except Exception as e:
            logger.error(f"❌ Delete goal failed: {e}")
            return False

    # ─── BUDGETS ─────────────────────────────────────

    def set_budget(self, user_id: str, category: str, limit: int) -> bool:
        try:
            self._client.table("budgets").upsert({
                "user_id": user_id,
                "category": category,
                "monthly_limit": limit,
                "updated_at": datetime.now().isoformat()
            }).execute()
            return True
        except Exception as e:
            logger.error(f"❌ Set budget failed: {e}")
            return False

    def get_budgets(self, user_id: str) -> List[Dict]:
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
        try:
            self._client.table("budgets").delete().eq(
                "user_id", user_id
            ).eq("category", category).execute()
            return True
        except Exception as e:
            logger.error(f"❌ Delete budget failed: {e}")
            return False

    # ─── USER PROFILES ───────────────────────────────

    def upsert_user(self, user_id: str, data: Dict) -> bool:
        try:
            data["user_id"] = user_id
            data["last_active"] = datetime.now().isoformat()
            self._client.table("user_profiles").upsert(data).execute()
            return True
        except Exception as e:
            logger.error(f"❌ Upsert user failed: {e}")
            return False

    def get_user(self, user_id: str) -> Optional[Dict]:
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

    # ─── CHAT HISTORY ────────────────────────────────

    def add_chat(self, user_id: str, role: str, message: str) -> bool:
        try:
            self._client.table("chat_history").insert({
                "user_id": user_id,
                "role": role,
                "message": message
            }).execute()
            return True
        except Exception as e:
            logger.error(f"❌ Add chat failed: {e}")
            return False

    def get_chat_history(self, user_id: str, limit: int = 20) -> List[Dict]:
        try:
            result = (
                self._client.table("chat_history")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return list(reversed(result.data))
        except Exception as e:
            logger.error(f"❌ Get chat history failed: {e}")
            return []

    # ─── USER CONTEXT ────────────────────────────────

    def set_context(self, user_id: str, context: Dict) -> bool:
        try:
            self._client.table("user_context").upsert({
                "user_id": user_id,
                "context_data": context,
                "updated_at": datetime.now().isoformat()
            }).execute()
            return True
        except Exception as e:
            logger.error(f"❌ Set context failed: {e}")
            return False

    def get_context(self, user_id: str) -> Dict:
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
```

---

## 5. Test Koneksi

Buat file `test_supabase.py` di root project:

```python
"""Quick test — verifikasi koneksi Supabase."""

from dotenv import load_dotenv
load_dotenv()

from services.supabase_service import SupabaseService

db = SupabaseService()

# Test 1: Insert transaksi
success = db.add_transactions_bulk("test_user", [{
    "item": "Kopi Starbucks",
    "category": "Food",
    "amount": 55000,
    "location": "Starbucks GI"
}])
print(f"Insert: {'✅' if success else '❌'}")

# Test 2: Read transaksi
txs = db.get_all_transactions("test_user")
print(f"Read: {len(txs)} transactions found")
for tx in txs:
    print(f"  - {tx['item_name']}: Rp {tx['amount']:,}")

# Test 3: Cleanup — hapus data test
from supabase import create_client
from config import Config
client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
client.table("transactions").delete().eq("user_id", "test_user").execute()
print("Cleanup: ✅")
```

Jalankan:
```bash
python test_supabase.py
```

Output yang diharapkan:
```
Insert: ✅
Read: 1 transactions found
  - Kopi Starbucks: Rp 55,000
Cleanup: ✅
```

---

## 6. Migrasi Data dari Google Sheets (Opsional)

Kalau kamu punya data existing di Google Sheets yang mau dipindahkan:

```python
"""Migrate data from Google Sheets to Supabase."""

from dotenv import load_dotenv
load_dotenv()

from services.sheets_service import SheetsService
from services.supabase_service import SupabaseService

sheets = SheetsService()
db = SupabaseService()

# Migrate transactions
print("📦 Migrating transactions...")
records = sheets.get_all_records()  # dari sheet Expenses
if records:
    rows = []
    for r in records:
        rows.append({
            "user_id": "YOUR_TELEGRAM_USER_ID",  # ganti!
            "date": r.get("Date", ""),
            "time": r.get("Time", ""),
            "item_name": r.get("Item Name", ""),
            "category": r.get("Category", "Other"),
            "amount": int(str(r.get("Amount (IDR)", 0)).replace(",", "")),
            "location": r.get("Location", ""),
        })
    
    # Insert in batches of 100
    batch_size = 100
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        db._client.table("transactions").insert(batch).execute()
        print(f"  ✅ Batch {i//batch_size + 1}: {len(batch)} rows")

print(f"✅ Migrated {len(rows)} transactions total")
```

---

## 7. Integrasi ke Bot (Strategi)

Ada 2 pendekatan untuk mengganti Google Sheets → Supabase:

### Opsi A: Gradual Migration (Recommended ✅)
Jalanin kedua service secara paralel, perlahan pindahkan satu-satu.

```
Step 1: Tambah supabase_service.py        ← sudah dibuat di Step 4
Step 2: Update service yang pakai sheets   ← satu per satu
Step 3: Test tiap perubahan
Step 4: Setelah semua pindah, hapus sheets_service.py
```

### Opsi B: Big Bang (Risky ⚠️)
Ganti semua sekaligus. Cepat tapi kalau error, semua kena.

**Saya rekomendasikan Opsi A** — lebih aman dan bisa rollback.

### File yang Perlu Diupdate:

| File | Perubahan |
|------|-----------|
| `services/ai_service.py` | Ganti panggilan `SheetsService` → `SupabaseService` |
| `services/analytics_service.py` | Query analytics dari Supabase |
| `services/budget_service.py` | CRUD budget via Supabase |
| `services/goals_service.py` | CRUD goals via Supabase |
| `services/telegram_service.py` | Handler utama — ganti semua data calls |
| `services/chat_service.py` | Chat history via Supabase |
| `services/export_service.py` | Export data dari Supabase |
| `config.py` | Tambah Supabase config |
| `.env` | Tambah `SUPABASE_URL` & `SUPABASE_KEY` |
| `requirements.txt` | Tambah `supabase` |

---

## 8. Supabase Free Plan Limits

| Resource | Free Tier Limit |
|----------|----------------|
| **Database** | 500 MB |
| **API Requests** | Unlimited |
| **Bandwidth** | 5 GB / month |
| **Storage** | 1 GB |
| **Realtime** | 200 concurrent connections |
| **Edge Functions** | 500K invocations/month |

> Untuk bot personal / small team, Free Tier **lebih dari cukup**.

---

## 9. Checklist Ringkasan

- [ ] Buat akun Supabase & project baru
- [ ] Catat URL + API keys
- [ ] Jalankan SQL schema (Step 3.2)
- [ ] `pip install supabase`
- [ ] Tambahkan env vars ke `.env`
- [ ] Update `config.py`
- [ ] Buat `services/supabase_service.py`
- [ ] Jalankan `test_supabase.py` — pastikan ✅
- [ ] (Opsional) Migrasi data lama
- [ ] Mulai integrasi ke bot secara bertahap

---

## 10. Troubleshooting Umum

| Error | Solusi |
|-------|--------|
| `AuthApiError: Invalid API key` | Cek lagi `SUPABASE_KEY` di `.env` — pastikan pakai **service_role** key |
| `ConnectionError` | Cek `SUPABASE_URL` — harus format `https://xxxxx.supabase.co` |
| `relation "transactions" does not exist` | SQL schema belum di-run — jalankan ulang Step 3.2 |
| `duplicate key value violates unique constraint` | Data sudah ada — gunakan `.upsert()` instead of `.insert()` |
| `RLS policy violation` | Pastikan pakai `service_role` key, bukan `anon` key |

---

**Setelah setup selesai, bilang aja kalau mau lanjut ke implementasi integrasi ke bot! 🚀**
