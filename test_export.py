import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from services.export_service import get_export_service
import logging

logging.basicConfig(level=logging.INFO)

def test_export():
    service = get_export_service()
    if not service.is_available():
        print("Export service not available")
        return

    # Dummy Data
    transactions = [
        {'DATE': '2026-02-01', 'ITEM NAME': 'Gaji', 'CATEGORY': 'Income', 'AMOUNT': 15000000},
        {'DATE': '2026-02-02', 'ITEM NAME': 'Sewa Apartemen', 'CATEGORY': 'Housing', 'AMOUNT': 3500000},
        {'DATE': '2026-02-03', 'ITEM NAME': 'Belanja Bulanan', 'CATEGORY': 'Food', 'AMOUNT': 1200000},
        {'DATE': '2026-02-05', 'ITEM NAME': 'Bensin', 'CATEGORY': 'Transport', 'AMOUNT': 300000},
        {'DATE': '2026-02-06', 'ITEM NAME': 'Nonton Bioskop', 'CATEGORY': 'Entertainment', 'AMOUNT': 150000},
        {'DATE': '2026-02-10', 'ITEM NAME': 'Kopi', 'CATEGORY': 'Food', 'AMOUNT': 50000},
         {'DATE': '2026-02-10', 'ITEM NAME': 'Investasi Saham', 'CATEGORY': 'Investment', 'AMOUNT': 2000000},
    ]

    category_breakdown = {
        'Housing': {'amount': 3500000, 'percentage': 48},
        'Food': {'amount': 1250000, 'percentage': 17},
        'Transport': {'amount': 300000, 'percentage': 4},
        'Entertainment': {'amount': 150000, 'percentage': 2},
        'Investment': {'amount': 2000000, 'percentage': 27},
    }

    summary = {
        'total_income': 15000000,
        'total_expense': 7200000,
        'net': 7800000,
        'count': 7
    }

    coaching_tips = [
        "Pengeluaran Housing cukup besar bulan ini.",
        "Bagus! Kamu sudah menyisihkan untuk investasi.",
        "Coba kurangi jajan kopi untuk hemat lebih banyak."
    ]

    pdf_bytes = service.generate_monthly_report(
        transactions,
        category_breakdown,
        summary,
        coaching_tips,
        period_label="Februari 2026"
    )

    if pdf_bytes:
        with open("test_report.pdf", "wb") as f:
            f.write(pdf_bytes)
        print("✅ PDF generated: test_report.pdf")
    else:
        print("❌ Failed to generate PDF")

if __name__ == "__main__":
    test_export()
