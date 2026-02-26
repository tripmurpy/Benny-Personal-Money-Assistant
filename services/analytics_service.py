"""
Advanced Analytics Service
Provides spending trends, visualizations, and dashboard data
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
import io

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Advanced analytics engine for generating spending insights,
    trends, and visualization data.
    """
    
    def __init__(self):
        self.chart_colors = {
            'Food': '#FF6B6B',
            'Transport': '#4ECDC4',
            'Bills': '#45B7D1',
            'Shopping': '#96CEB4',
            'Income': '#2ECC71',
            'Other': '#95A5A6'
        }
    
    def get_dashboard_data(
        self, 
        transactions: List[Dict],
        period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Generate comprehensive dashboard data.
        
        Returns complete analytics for dashboard display.
        """
        if not transactions:
            return self._empty_dashboard()
        
        # Filter to period
        cutoff = datetime.now() - timedelta(days=period_days)
        filtered = self._filter_by_date(transactions, cutoff)
        
        return {
            'summary': self._get_summary(filtered),
            'trends': self._get_spending_trends(filtered, period_days),
            'category_distribution': self._get_category_distribution(filtered),
            'daily_average': self._get_daily_average(filtered, period_days),
            'top_expenses': self._get_top_expenses(filtered, limit=5),
            'burn_rate': self._calculate_burn_rate(filtered, period_days),
            'comparison': self._get_period_comparison(transactions, period_days)
        }
    
    def _empty_dashboard(self) -> Dict[str, Any]:
        """Return empty dashboard structure."""
        return {
            'summary': {'total_expense': 0, 'total_income': 0, 'net': 0, 'count': 0},
            'trends': [],
            'category_distribution': {},
            'daily_average': 0,
            'top_expenses': [],
            'burn_rate': None,
            'comparison': None
        }
    
    def _filter_by_date(
        self, 
        transactions: List[Dict], 
        cutoff: datetime
    ) -> List[Dict]:
        """Filter transactions by date."""
        filtered = []
        for t in transactions:
            try:
                date_str = str(t.get('DATE') or t.get('date') or '')
                if date_str:
                    t_date = datetime.strptime(date_str, '%Y-%m-%d')
                    if t_date >= cutoff:
                        filtered.append(t)
            except ValueError:
                continue
        return filtered
    
    def _get_summary(self, transactions: List[Dict]) -> Dict[str, int]:
        """Calculate summary metrics."""
        total_expense = 0
        total_income = 0
        count = 0
        
        for t in transactions:
            amount = self._extract_amount(t)
            category = str(t.get('CATEGORY') or t.get('category') or '').lower()
            
            if category in ['income', 'pemasukan']:
                total_income += amount
            else:
                total_expense += amount
                count += 1
        
        return {
            'total_expense': total_expense,
            'total_income': total_income,
            'net': total_income - total_expense,
            'count': count
        }
    
    def _get_spending_trends(
        self, 
        transactions: List[Dict],
        period_days: int
    ) -> List[Dict]:
        """Generate daily spending trend data."""
        daily_spending = defaultdict(int)
        
        for t in transactions:
            date_str = str(t.get('DATE') or t.get('date') or '')
            amount = self._extract_amount(t)
            category = str(t.get('CATEGORY') or t.get('category') or '').lower()
            
            if date_str and category not in ['income', 'pemasukan']:
                daily_spending[date_str] += amount
        
        # Fill missing dates with 0
        trends = []
        for i in range(period_days):
            date = (datetime.now() - timedelta(days=period_days-1-i)).strftime('%Y-%m-%d')
            trends.append({
                'date': date,
                'amount': daily_spending.get(date, 0)
            })
        
        return trends
    
    def _get_category_distribution(self, transactions: List[Dict]) -> Dict[str, Any]:
        """Calculate category distribution."""
        categories = defaultdict(lambda: {'amount': 0, 'count': 0})
        total = 0
        
        for t in transactions:
            amount = self._extract_amount(t)
            category = str(t.get('CATEGORY') or t.get('category') or 'Other')
            
            if category.lower() not in ['income', 'pemasukan']:
                categories[category]['amount'] += amount
                categories[category]['count'] += 1
                total += amount
        
        # Add percentages
        result = {}
        for cat, data in sorted(categories.items(), key=lambda x: x[1]['amount'], reverse=True):
            result[cat] = {
                'amount': data['amount'],
                'count': data['count'],
                'percentage': round((data['amount'] / total * 100), 1) if total > 0 else 0,
                'color': self.chart_colors.get(cat, '#95A5A6')
            }
        
        return result
    
    def _get_daily_average(self, transactions: List[Dict], period_days: int) -> float:
        """Calculate daily average spending."""
        total = sum(
            self._extract_amount(t) for t in transactions 
            if str(t.get('CATEGORY') or t.get('category') or '').lower() not in ['income', 'pemasukan']
        )
        return round(total / max(period_days, 1))
    
    def _get_top_expenses(self, transactions: List[Dict], limit: int = 5) -> List[Dict]:
        """Get top expenses."""
        expenses = []
        for t in transactions:
            amount = self._extract_amount(t)
            category = str(t.get('CATEGORY') or t.get('category') or '').lower()
            
            if category not in ['income', 'pemasukan'] and amount > 0:
                expenses.append({
                    'item': str(t.get('ITEM NAME') or t.get('item') or 'Unknown'),
                    'amount': amount,
                    'category': str(t.get('CATEGORY') or t.get('category') or 'Other'),
                    'date': str(t.get('DATE') or t.get('date') or '')
                })
        
        return sorted(expenses, key=lambda x: x['amount'], reverse=True)[:limit]
    
    def _calculate_burn_rate(
        self, 
        transactions: List[Dict], 
        period_days: int
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate burn rate - how fast money is being spent.
        
        Returns estimated days until budget depletes at current rate.
        """
        summary = self._get_summary(transactions)
        daily_avg = self._get_daily_average(transactions, period_days)
        
        if daily_avg <= 0:
            return None
        
        # Assume a monthly budget of 2x current spending as reference
        estimated_monthly_budget = daily_avg * 30 * 1.5
        current_balance = summary['total_income'] - summary['total_expense']
        
        if current_balance > 0 and daily_avg > 0:
            days_remaining = int(current_balance / daily_avg)
        else:
            days_remaining = 0
        
        return {
            'daily_rate': daily_avg,
            'days_remaining': days_remaining,
            'status': 'healthy' if days_remaining > 14 else ('warning' if days_remaining > 7 else 'critical')
        }
    
    def _get_period_comparison(
        self, 
        transactions: List[Dict],
        period_days: int
    ) -> Optional[Dict[str, Any]]:
        """Compare current period with previous period."""
        now = datetime.now()
        current_start = now - timedelta(days=period_days)
        previous_start = current_start - timedelta(days=period_days)
        
        current_filtered = self._filter_by_date(transactions, current_start)
        previous_filtered = []
        for t in transactions:
            try:
                date_str = str(t.get('DATE') or t.get('date') or '')
                if date_str:
                    t_date = datetime.strptime(date_str, '%Y-%m-%d')
                    if previous_start <= t_date < current_start:
                        previous_filtered.append(t)
            except ValueError:
                continue
        
        current_total = sum(
            self._extract_amount(t) for t in current_filtered
            if str(t.get('CATEGORY') or t.get('category') or '').lower() not in ['income', 'pemasukan']
        )
        previous_total = sum(
            self._extract_amount(t) for t in previous_filtered
            if str(t.get('CATEGORY') or t.get('category') or '').lower() not in ['income', 'pemasukan']
        )
        
        if previous_total == 0:
            return None
        
        change = current_total - previous_total
        change_percent = round((change / previous_total) * 100, 1)
        
        return {
            'current_total': current_total,
            'previous_total': previous_total,
            'change': change,
            'change_percent': change_percent,
            'trend': '↑ naik' if change_percent > 5 else ('↓ turun' if change_percent < -5 else '→ stabil')
        }
    
    def _extract_amount(self, transaction: Dict) -> int:
        """Extract and clean amount from transaction."""
        import re
        amount = (
            transaction.get('EXPENSE') or 
            transaction.get('AMOUNTH(IDR)') or 
            transaction.get('amount') or 
            transaction.get('Amount (IDR)') or 
            0
        )
        
        if isinstance(amount, str):
            clean = re.sub(r'[^\d]', '', amount)
            return int(clean) if clean else 0
        
        return int(amount) if amount else 0
    
    def format_dashboard_message(self, data: Dict[str, Any], period_label: str = "30 Hari") -> str:
        """Format dashboard data as Telegram message."""
        summary = data['summary']
        categories = data['category_distribution']
        comparison = data['comparison']
        top_expenses = data['top_expenses']
        burn_rate = data['burn_rate']
        
        lines = [
            "📊 **DASHBOARD ANALYTICS**",
            f"📅 Periode: {period_label}",
            "",
            "━━━━━ RINGKASAN ━━━━━"
        ]
        
        # Summary
        expense_str = f"{summary['total_expense']:,}".replace(',', '.')
        income_str = f"{summary['total_income']:,}".replace(',', '.')
        net_str = f"{abs(summary['net']):,}".replace(',', '.')
        
        lines.append(f"💸 Pengeluaran: Rp {expense_str}")
        lines.append(f"💵 Pemasukan: Rp {income_str}")
        net_emoji = "✅" if summary['net'] >= 0 else "⚠️"
        net_sign = "" if summary['net'] >= 0 else "-"
        lines.append(f"{net_emoji} Selisih: {net_sign}Rp {net_str}")
        lines.append(f"📝 Transaksi: {summary['count']} kali")
        
        # Comparison
        if comparison:
            lines.append("")
            trend_emoji = "📈" if comparison['change'] > 0 else "📉"
            change_str = f"{abs(comparison['change']):,}".replace(',', '.')
            lines.append(f"{trend_emoji} vs Periode Lalu: {comparison['trend']}")
            lines.append(f"   ({'+' if comparison['change'] > 0 else '-'}Rp {change_str}, {comparison['change_percent']}%)")
        
        # Burn Rate
        if burn_rate:
            lines.append("")
            daily_str = f"{burn_rate['daily_rate']:,}".replace(',', '.')
            status_emoji = "🟢" if burn_rate['status'] == 'healthy' else ("🟡" if burn_rate['status'] == 'warning' else "🔴")
            lines.append(f"🔥 Burn Rate: Rp {daily_str}/hari")
            lines.append(f"{status_emoji} Estimasi: ~{burn_rate['days_remaining']} hari lagi")
        
        # Category breakdown
        lines.append("")
        lines.append("━━━ DISTRIBUSI KATEGORI ━━━")
        for cat, info in list(categories.items())[:5]:
            amt_str = f"{info['amount']:,}".replace(',', '.')
            bar = self._generate_text_bar(info['percentage'])
            lines.append(f"{cat}: {bar} {info['percentage']}%")
            lines.append(f"   Rp {amt_str} ({info['count']}x)")
        
        # Top expenses
        if top_expenses:
            lines.append("")
            lines.append("━━━━ TOP 5 TERBESAR ━━━━")
            for i, exp in enumerate(top_expenses, 1):
                amt_str = f"{exp['amount']:,}".replace(',', '.')
                lines.append(f"{i}. {exp['item'][:20]}")
                lines.append(f"   Rp {amt_str} • {exp['category']}")
        
        return "\n".join(lines)
    
    def _generate_text_bar(self, percentage: float, width: int = 10) -> str:
        """Generate text-based progress bar."""
        filled = int(percentage / 100 * width)
        empty = width - filled
        return "█" * filled + "░" * empty
    
    def generate_trend_chart_text(self, trends: List[Dict], title: str = "TREND PENGELUARAN") -> str:
        """Generate ASCII text chart for spending trends."""
        if not trends:
            return "No data available"
        
        lines = [f"📈 {title}", ""]
        
        # Get last 7 days only for readability
        recent_trends = trends[-7:]
        max_amount = max((t['amount'] for t in recent_trends), default=1)
        
        for t in recent_trends:
            date_short = t['date'][-5:]  # MM-DD
            amount = t['amount']
            bar_length = int((amount / max_amount) * 15) if max_amount > 0 else 0
            bar = "▓" * bar_length + "░" * (15 - bar_length)
            amt_str = f"{amount:,}".replace(',', '.')
            lines.append(f"{date_short} {bar} Rp {amt_str}")
        
        return "\n".join(lines)


# Singleton instance
_analytics_service = None

def get_analytics_service() -> AnalyticsService:
    """Get singleton analytics service instance."""
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsService()
    return _analytics_service
