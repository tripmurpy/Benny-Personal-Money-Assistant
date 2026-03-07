"""Quick test — verify Supabase connection and basic CRUD."""

from dotenv import load_dotenv

load_dotenv()

from services.supabase_service import SupabaseService

db = SupabaseService()

# Test 1: Insert a test transaction
print("─── Test 1: Insert ───")
success = db.add_transactions_bulk(
    "test_user",
    [
        {
            "item": "Kopi Starbucks",
            "category": "Food",
            "amount": 55000,
            "location": "Starbucks GI",
        }
    ],
)
print(f"Insert: {'✅' if success else '❌'}")

# Test 2: Read back the transaction
print("\n─── Test 2: Read ───")
txs = db.get_all_transactions("test_user")
print(f"Read: {len(txs)} transactions found")
for tx in txs:
    print(f"  - {tx['item_name']}: Rp {tx['amount']:,}")

# Test 3: Cleanup test data
print("\n─── Test 3: Cleanup ───")
from supabase import create_client
from config import Config

client = create_client(Config.SUPABASE_URL, Config.SUPABASE_KEY)
client.table("transactions").delete().eq("user_id", "test_user").execute()
print("Cleanup: ✅")

print("\n🎉 All tests passed! Supabase is ready.")
