"""Quick test for ExpenseQueryService date parsing."""
from services.expense_query_service import get_expense_query_service

svc = get_expense_query_service()

tests = [
    ("pengeluaran bulan januari", True),
    ("berapa total belanja minggu lalu", True),
    ("detail pengeluaran maret", True),
    ("pengeluaran dari 1 sampai 15 januari", True),
    ("makan siang 25rb", False),
    ("halo benny", False),
    ("laporan hari ini", True),
    ("pengeluaran kemarin", True),
    ("pengeluaran januari 2025", True),
    ("total pengeluaran bulan ini", True),
]

print("=== ExpenseQueryService Tests ===\n")
passed = 0
for text, expected in tests:
    result = svc.detect(text)
    is_detected = result is not None
    ok = is_detected == expected
    passed += ok
    status = "✅" if ok else "❌"
    detail = result if result else "None"
    print(f"  {status} '{text}'")
    print(f"     Expected={expected}, Got={is_detected}, Result={detail}\n")

print(f"\n{passed}/{len(tests)} tests passed")
