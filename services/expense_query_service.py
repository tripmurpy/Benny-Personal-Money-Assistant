"""
Expense Query Service — Detects expense-related questions and parses time periods.

Handles natural language like:
- "pengeluaran bulan januari"
- "berapa total belanja minggu lalu?"
- "detail pengeluaran dari 1 sampai 15 maret"
"""

import re
import calendar
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)


# Indonesian month name → number mapping
BULAN_MAP = {
    'januari': 1, 'february': 2, 'februari': 2, 'maret': 3,
    'april': 4, 'mei': 5, 'juni': 6, 'juli': 7,
    'agustus': 8, 'september': 9, 'oktober': 10,
    'november': 11, 'desember': 12,
    # Abbreviations
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
    'jun': 6, 'jul': 7, 'agu': 8, 'aug': 8,
    'sep': 9, 'okt': 10, 'oct': 10, 'nov': 11, 'des': 12, 'dec': 12,
}

BULAN_LABEL = {
    1: 'Januari', 2: 'Februari', 3: 'Maret', 4: 'April',
    5: 'Mei', 6: 'Juni', 7: 'Juli', 8: 'Agustus',
    9: 'September', 10: 'Oktober', 11: 'November', 12: 'Desember',
}

# Keywords that indicate an expense query
EXPENSE_KEYWORDS = [
    'pengeluaran', 'belanja', 'habis', 'spending', 'total',
    'berapa', 'keluar', 'expense', 'laporan', 'report',
    'biaya', 'catatan', 'transaksi',
]

# Purchase verbs that combined with a question indicate a query
PURCHASE_VERBS = [
    'beli', 'bayar', 'habis', 'keluar', 'belanja', 'jajan',
    'makan', 'minum', 'catat',
]

# Question indicators
QUESTION_PATTERNS = [
    'apa saja', 'apa aja', 'berapa', 'brp', 'apa ya',
    'apa yang', 'what', 'how much', 'ada apa',
]

# Keywords that indicate user wants detail
DETAIL_KEYWORDS = [
    'detail', 'lengkap', 'rinci', 'semua', 'list', 'daftar',
    'satu per satu', 'apa saja', 'apa aja',
]

# Time-related keywords (to confirm it's a time-based query)
TIME_KEYWORDS = [
    'hari ini', 'kemarin', 'minggu ini', 'minggu lalu',
    'bulan ini', 'bulan lalu', 'tahun ini', 'tahun lalu',
    'jam', 'pukul', 'tadi', 'pagi', 'siang', 'sore', 'malam', 'waktu'
]


class ExpenseQueryService:
    """Detects and parses expense queries from user text."""

    def detect(self, text: str) -> Optional[dict]:
        """
        Detect if text is an expense query and parse the time period.

        Returns None if not an expense query, or a dict:
        {
            "start": "YYYY-MM-DD",
            "end": "YYYY-MM-DD",
            "label": "Januari 2026",
            "wants_detail": bool
        }
        """
        text_lower = text.lower().strip()

        # Guard: if text has a monetary amount, it's a transaction, not a query
        # Only match amounts with currency indicators (rb/ribu/k/jt/rp) or plain large numbers
        has_currency_marker = bool(re.search(
            r'\d+\s*(?:rb|ribu|jt|juta|k|rupiah)\b|(?:rp|idr)\s*\.?\d+',
            text_lower
        ))

        # Check for plain numbers typical of amounts (e.g. 62500, 15000)
        has_plain_amount = False
        plain_numbers = re.findall(r'\b\d{3,9}\b', text_lower.replace('.', ''))
        for num_str in plain_numbers:
            try:
                num = int(num_str)
                # If number is >= 100 and NOT in the typical year range (1900-2100), assume it's a price/amount
                if num >= 100 and not (1900 <= num <= 2100):
                    has_plain_amount = True
                    break
            except ValueError:
                pass

        if has_currency_marker or has_plain_amount:
            return None

        # Check time reference first (required for ALL expense queries)
        has_time_ref = (
            any(kw in text_lower for kw in TIME_KEYWORDS) or
            any(b in text_lower for b in BULAN_MAP) or
            bool(re.search(r'tanggal\s+\d+', text_lower))
        )

        if not has_time_ref:
            return None

        # Detection path 1: explicit expense keywords
        has_expense_kw = any(kw in text_lower for kw in EXPENSE_KEYWORDS)

        # Detection path 2: question about purchases at a time
        # e.g. "kemarin aku beli apa saja ya?", "hari ini bayar apa?"
        has_purchase_question = (
            any(v in text_lower for v in PURCHASE_VERBS) and
            (
                any(q in text_lower for q in QUESTION_PATTERNS) or
                '?' in text
            )
        )

        if not (has_expense_kw or has_purchase_question):
            return None

        wants_detail = any(kw in text_lower for kw in DETAIL_KEYWORDS)
        now = datetime.now()

        # Try each parser in order of specificity
        result = (
            self._parse_date_range(text_lower, now) or
            self._parse_specific_date(text_lower, now) or
            self._parse_relative_period(text_lower, now) or
            self._parse_month_year(text_lower, now) or
            self._parse_month_only(text_lower, now)
        )

        if result:
            result['wants_detail'] = wants_detail
            return result

        return None

    # ── Parsers (most specific → least specific) ─────────────

    def _parse_date_range(self, text: str, now: datetime) -> Optional[dict]:
        """Parse: 'dari 1 sampai 15 januari 2026' or 'tanggal 1-15 maret'"""
        # Pattern: dari X sampai/hingga/ke Y [bulan] [tahun]
        pattern = r'(?:dari|tanggal)\s+(\d{1,2})\s+(?:sampai|hingga|ke|s/?d|-)\s+(\d{1,2})\s+(\w+)(?:\s+(\d{4}))?'
        match = re.search(pattern, text)
        if not match:
            # Also try: 1-15 januari
            pattern2 = r'(\d{1,2})\s*[-–]\s*(\d{1,2})\s+(\w+)(?:\s+(\d{4}))?'
            match = re.search(pattern2, text)

        if match:
            day_start = int(match.group(1))
            day_end = int(match.group(2))
            month_name = match.group(3)
            year = int(match.group(4)) if match.group(4) else now.year

            month = BULAN_MAP.get(month_name)
            if month:
                # Clamp days
                max_day = calendar.monthrange(year, month)[1]
                day_start = min(day_start, max_day)
                day_end = min(day_end, max_day)

                label = f"{day_start}-{day_end} {BULAN_LABEL[month]} {year}"
                return {
                    'start': f"{year}-{month:02d}-{day_start:02d}",
                    'end': f"{year}-{month:02d}-{day_end:02d}",
                    'label': label,
                }

        return None

    def _parse_specific_date(self, text: str, now: datetime) -> Optional[dict]:
        """Parse: 'tanggal 5 januari' or 'tgl 15 maret 2025'"""
        pattern = r'(?:tanggal|tgl)\s+(\d{1,2})\s+(\w+)(?:\s+(\d{4}))?'
        match = re.search(pattern, text)
        if match:
            day = int(match.group(1))
            month_name = match.group(2)
            year = int(match.group(3)) if match.group(3) else now.year

            month = BULAN_MAP.get(month_name)
            if month:
                max_day = calendar.monthrange(year, month)[1]
                day = min(day, max_day)
                date_str = f"{year}-{month:02d}-{day:02d}"
                label = f"{day} {BULAN_LABEL[month]} {year}"
                return {'start': date_str, 'end': date_str, 'label': label}

        return None

    def _parse_relative_period(self, text: str, now: datetime) -> Optional[dict]:
        """Parse: 'hari ini', 'kemarin', 'minggu ini', 'minggu lalu', 'bulan lalu'"""

        if 'kemarin' in text or 'yesterday' in text:
            d = (now - timedelta(days=1)).strftime('%Y-%m-%d')
            return {'start': d, 'end': d, 'label': 'Kemarin'}

        if 'hari ini' in text or 'today' in text:
            d = now.strftime('%Y-%m-%d')
            return {'start': d, 'end': d, 'label': 'Hari Ini'}

        if 'minggu ini' in text or 'this week' in text:
            start = now - timedelta(days=now.weekday())  # Monday
            end = now
            return {
                'start': start.strftime('%Y-%m-%d'),
                'end': end.strftime('%Y-%m-%d'),
                'label': 'Minggu Ini',
            }

        if 'minggu lalu' in text or 'last week' in text:
            end = now - timedelta(days=now.weekday() + 1)  # Last Sunday
            start = end - timedelta(days=6)  # Last Monday
            return {
                'start': start.strftime('%Y-%m-%d'),
                'end': end.strftime('%Y-%m-%d'),
                'label': 'Minggu Lalu',
            }

        if 'bulan lalu' in text or 'last month' in text:
            first_this = now.replace(day=1)
            last_prev = first_this - timedelta(days=1)
            first_prev = last_prev.replace(day=1)
            month_num = first_prev.month
            label = f"{BULAN_LABEL[month_num]} {first_prev.year}"
            return {
                'start': first_prev.strftime('%Y-%m-%d'),
                'end': last_prev.strftime('%Y-%m-%d'),
                'label': label,
            }

        if 'tahun ini' in text or 'this year' in text:
            return {
                'start': f"{now.year}-01-01",
                'end': now.strftime('%Y-%m-%d'),
                'label': f"Tahun {now.year}",
            }

        if 'tahun lalu' in text or 'last year' in text:
            yr = now.year - 1
            return {
                'start': f"{yr}-01-01",
                'end': f"{yr}-12-31",
                'label': f"Tahun {yr}",
            }

        if any(w in text for w in ['jam', 'pukul', 'tadi', 'pagi', 'siang', 'sore', 'malam', 'sekarang']):
            d = now.strftime('%Y-%m-%d')
            return {'start': d, 'end': d, 'label': 'Hari Ini'}

        return None

    def _parse_month_year(self, text: str, now: datetime) -> Optional[dict]:
        """Parse: 'januari 2025' or 'bulan maret 2026'"""
        pattern = r'(?:bulan\s+)?(\w+)\s+(\d{4})'
        match = re.search(pattern, text)
        if match:
            month_name = match.group(1)
            year = int(match.group(2))
            month = BULAN_MAP.get(month_name)
            if month:
                last_day = calendar.monthrange(year, month)[1]
                label = f"{BULAN_LABEL[month]} {year}"
                return {
                    'start': f"{year}-{month:02d}-01",
                    'end': f"{year}-{month:02d}-{last_day:02d}",
                    'label': label,
                }
        return None

    def _parse_month_only(self, text: str, now: datetime) -> Optional[dict]:
        """Parse: 'januari', 'bulan maret' (assumes current year)."""
        # Try to find month name in text
        for name, num in BULAN_MAP.items():
            if name in text and len(name) >= 3:
                year = now.year
                # If queried month is in the future, assume last year
                if num > now.month:
                    year -= 1
                last_day = calendar.monthrange(year, num)[1]
                label = f"{BULAN_LABEL[num]} {year}"
                return {
                    'start': f"{year}-{num:02d}-01",
                    'end': f"{year}-{num:02d}-{last_day:02d}",
                    'label': label,
                }
        return None


# Singleton
_instance = None


def get_expense_query_service() -> ExpenseQueryService:
    global _instance
    if _instance is None:
        _instance = ExpenseQueryService()
    return _instance
