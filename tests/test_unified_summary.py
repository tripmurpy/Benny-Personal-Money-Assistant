"""Focused deterministic check for unified income/expense summaries."""

import unittest

from services.analytics_service import AnalyticsService


class UnifiedSummaryTest(unittest.TestCase):
    def test_normalizes_filters_and_aggregates_separate_rows(self):
        service = AnalyticsService()
        expenses = [
            {'date': '2026-07-01', 'category': 'Food', 'amount': 100_000},
            {'DATE': '2026-07-15', 'CATEGORY': 'Food', 'EXPENSE': 'Rp 200.000'},
            {'date': '2026-07-20', 'category': 'Transport', 'amount': 150_000},
            {'date': '2026-08-01', 'category': 'Bills', 'amount': 900_000},
            {'date': 'invalid', 'category': 'Other', 'amount': 500_000},
        ]
        incomes = [
            {'date': '2026-07-01', 'source': 'Gaji', 'amount': 1_000_000},
            {'DATE': '2026-07-31', 'SOURCE': 'Bonus', 'INCOME': 'Rp 250.000'},
            {'date': '2026-06-30', 'source': 'Lama', 'amount': 5_000_000},
        ]

        summary = service.get_unified_summary(
            expenses, incomes, '2026-07-01', '2026-07-31', 'Juli 2026'
        )

        self.assertEqual(summary['total_income'], 1_250_000)
        self.assertEqual(summary['total_expense'], 450_000)
        self.assertEqual(summary['cash_flow'], 800_000)
        self.assertEqual(summary['top_expense_category'], {'category': 'Food', 'amount': 300_000})
        self.assertEqual(summary['period']['label'], 'Juli 2026')
        message = service.format_unified_summary_message(summary)
        self.assertIn('Arus kas', message)
        self.assertNotIn('Saldo', message)
        self.assertEqual(service.get_dashboard_data([])['summary']['net'], 0)


if __name__ == '__main__':
    unittest.main()
