"""
AI Financial Coaching Engine
Generates intelligent weekly reports, spending pattern analysis, and actionable advice
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)


class CoachingEngine:
    """
    Intelligent financial coaching system that analyzes spending patterns
    and generates personalized advice.
    """
    
    def __init__(self):
        self.category_benchmarks = {
            'Food': 0.30,       # 30% of spending is typical
            'Transport': 0.15,  # 15%
            'Bills': 0.25,      # 25%
            'Shopping': 0.15,   # 15%
            'Other': 0.15       # 15%
        }
    
    def generate_weekly_report(
        self, 
        transactions: List[Dict], 
        previous_week_transactions: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive weekly coaching report.
        
        Returns:
            Dict with summary, category_breakdown, comparison, and tips
        """
        if not transactions:
            return {
                'summary': {'total': 0, 'count': 0, 'daily_avg': 0},
                'category_breakdown': {},
                'comparison': None,
                'tips': ['Mulai catat pengeluaranmu minggu ini! 📝'],
                'achievements': [],
                'warnings': []
            }
        
        # Calculate current week metrics
        current_metrics = self._calculate_metrics(transactions)
        
        # Calculate previous week comparison if available
        comparison = None
        if previous_week_transactions:
            prev_metrics = self._calculate_metrics(previous_week_transactions)
            comparison = self._generate_comparison(current_metrics, prev_metrics)
        
        # Generate personalized tips
        tips = self._generate_tips(current_metrics, comparison)
        
        # Detect achievements and warnings
        achievements = self._detect_achievements(current_metrics, comparison)
        warnings = self._detect_warnings(current_metrics)
        
        return {
            'summary': {
                'total': current_metrics['total'],
                'count': current_metrics['count'],
                'daily_avg': current_metrics['daily_avg'],
                'highest_day': current_metrics.get('highest_day'),
                'lowest_day': current_metrics.get('lowest_day')
            },
            'category_breakdown': current_metrics['categories'],
            'comparison': comparison,
            'tips': tips,
            'achievements': achievements,
            'warnings': warnings,
            'top_expenses': current_metrics.get('top_expenses', [])[:5]
        }
    
    def _calculate_metrics(self, transactions: List[Dict]) -> Dict[str, Any]:
        """Calculate comprehensive spending metrics."""
        total = 0
        categories = defaultdict(lambda: {'amount': 0, 'count': 0, 'items': []})
        daily_spending = defaultdict(int)
        all_expenses = []
        
        for t in transactions:
            try:
                # Get amount (handle different column names)
                amount = self._extract_amount(t)
                category = str(t.get('CATEGORY') or t.get('category') or 'Other')
                date = str(t.get('DATE') or t.get('date') or '')
                item = str(t.get('ITEM NAME') or t.get('item') or 'Unknown')
                
                # Skip income
                if category.lower() in ['income', 'pemasukan']:
                    continue
                
                total += amount
                categories[category]['amount'] += amount
                categories[category]['count'] += 1
                categories[category]['items'].append({'item': item, 'amount': amount})
                
                if date:
                    daily_spending[date] += amount
                
                all_expenses.append({
                    'item': item,
                    'amount': amount,
                    'category': category,
                    'date': date
                })
                
            except Exception as e:
                logger.debug(f"Error processing transaction: {e}")
                continue
        
        # Calculate percentages
        for cat in categories:
            if total > 0:
                categories[cat]['percentage'] = round(
                    (categories[cat]['amount'] / total) * 100, 1
                )
            else:
                categories[cat]['percentage'] = 0
        
        # Sort categories by amount
        sorted_categories = dict(
            sorted(categories.items(), key=lambda x: x[1]['amount'], reverse=True)
        )
        
        # Find highest and lowest spending days
        highest_day = None
        lowest_day = None
        if daily_spending:
            highest_day = max(daily_spending.items(), key=lambda x: x[1])
            lowest_day = min(daily_spending.items(), key=lambda x: x[1])
        
        # Top expenses
        top_expenses = sorted(all_expenses, key=lambda x: x['amount'], reverse=True)[:10]
        
        return {
            'total': total,
            'count': len([t for t in transactions if self._extract_amount(t) > 0]),
            'daily_avg': total / 7 if total > 0 else 0,
            'categories': sorted_categories,
            'highest_day': highest_day,
            'lowest_day': lowest_day,
            'top_expenses': top_expenses,
            'daily_spending': dict(daily_spending)
        }
    
    def _extract_amount(self, transaction: Dict) -> int:
        """Extract and clean amount from transaction."""
        # Try different column names
        amount = (
            transaction.get('EXPENSE') or 
            transaction.get('AMOUNTH(IDR)') or 
            transaction.get('amount') or 
            transaction.get('Amount (IDR)') or 
            0
        )
        
        if isinstance(amount, str):
            # Clean string: remove dots, commas, non-digits
            import re
            clean = re.sub(r'[^\d]', '', amount)
            return int(clean) if clean else 0
        
        return int(amount) if amount else 0
    
    def _generate_comparison(
        self, 
        current: Dict[str, Any], 
        previous: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate week-over-week comparison."""
        if previous['total'] == 0:
            return {
                'total_change': current['total'],
                'total_change_percent': 100,
                'trend': 'new'
            }
        
        total_change = current['total'] - previous['total']
        total_change_percent = round((total_change / previous['total']) * 100, 1)
        
        # Category-wise comparison
        category_changes = {}
        all_categories = set(current['categories'].keys()) | set(previous['categories'].keys())
        
        for cat in all_categories:
            curr_amt = current['categories'].get(cat, {}).get('amount', 0)
            prev_amt = previous['categories'].get(cat, {}).get('amount', 0)
            
            if prev_amt > 0:
                change_pct = round(((curr_amt - prev_amt) / prev_amt) * 100, 1)
            elif curr_amt > 0:
                change_pct = 100
            else:
                change_pct = 0
            
            category_changes[cat] = {
                'current': curr_amt,
                'previous': prev_amt,
                'change': curr_amt - prev_amt,
                'change_percent': change_pct,
                'trend': '↑' if change_pct > 5 else ('↓' if change_pct < -5 else '→')
            }
        
        return {
            'total_change': total_change,
            'total_change_percent': total_change_percent,
            'trend': '↑ naik' if total_change_percent > 5 else (
                '↓ turun' if total_change_percent < -5 else '→ stabil'
            ),
            'category_changes': category_changes
        }
    
    def _generate_tips(
        self, 
        metrics: Dict[str, Any], 
        comparison: Optional[Dict] = None
    ) -> List[str]:
        """Generate personalized actionable tips."""
        tips = []
        categories = metrics['categories']
        total = metrics['total']
        
        if not categories or total == 0:
            return ['Mulai catat transaksimu untuk mendapat insight! 📊']
        
        # Tip 1: Biggest spending category
        top_cat = list(categories.keys())[0] if categories else None
        if top_cat and categories[top_cat]['percentage'] > 35:
            top_items = categories[top_cat]['items']
            if top_items:
                freq_items = defaultdict(int)
                for item in top_items:
                    freq_items[item['item']] += 1
                most_frequent = max(freq_items.items(), key=lambda x: x[1])
                tips.append(
                    f"💡 {top_cat} adalah pengeluaran terbesar ({categories[top_cat]['percentage']}%). "
                    f"'{most_frequent[0]}' muncul {most_frequent[1]}x minggu ini. "
                    f"Coba kurangi 1-2x untuk hemat ~Rp {categories[top_cat]['amount'] // most_frequent[1]:,}".replace(',', '.')
                )
        
        # Tip 2: Comparison-based tip
        if comparison and comparison.get('category_changes'):
            for cat, change in comparison['category_changes'].items():
                if change['change_percent'] > 30 and change['change'] > 50000:
                    tips.append(
                        f"📈 {cat} naik {change['change_percent']}% dari minggu lalu "
                        f"(+Rp {change['change']:,}). Perlu dikontrol?".replace(',', '.')
                    )
                    break
        
        # Tip 3: Spending pattern tip
        if metrics.get('highest_day') and metrics.get('lowest_day'):
            high_day, high_amt = metrics['highest_day']
            low_day, low_amt = metrics['lowest_day']
            if high_amt > low_amt * 3:  # Spending 3x higher on some days
                tips.append(
                    f"🎯 Pengeluaran tertinggi di {high_day[-5:]} (Rp {high_amt:,}). "
                    f"Coba ratakan pengeluaran harianmu!".replace(',', '.')
                )
        
        # Tip 4: General daily average tip
        if metrics['daily_avg'] > 0:
            tips.append(
                f"📊 Rata-rata harianmu Rp {metrics['daily_avg']:,.0f}. "
                f"Target <Rp {metrics['daily_avg'] * 0.9:,.0f}/hari untuk hemat 10%!".replace(',', '.')
            )
        
        return tips[:3]  # Max 3 tips per report
    
    def _detect_achievements(
        self, 
        metrics: Dict[str, Any], 
        comparison: Optional[Dict] = None
    ) -> List[str]:
        """Detect positive achievements to celebrate."""
        achievements = []
        
        if comparison:
            # Spending reduction achievement
            if comparison['total_change_percent'] < -10:
                achievements.append(
                    f"🏆 Hebat! Pengeluaran turun {abs(comparison['total_change_percent'])}% dari minggu lalu!"
                )
            
            # Category improvement
            if comparison.get('category_changes'):
                for cat, change in comparison['category_changes'].items():
                    if change['change_percent'] < -20 and change['previous'] > 100000:
                        achievements.append(
                            f"⭐ {cat} berhasil dikurangi {abs(change['change_percent'])}%!"
                        )
                        break
        
        # Consistency achievement
        if metrics.get('count', 0) >= 10:
            achievements.append("📝 Konsisten mencatat! Sudah 10+ transaksi minggu ini.")
        
        return achievements[:2]
    
    def _detect_warnings(self, metrics: Dict[str, Any]) -> List[str]:
        """Detect potential issues or warnings."""
        warnings = []
        categories = metrics['categories']
        total = metrics['total']
        
        # Overspending in single category
        for cat, data in categories.items():
            if data['percentage'] > 50:
                warnings.append(
                    f"⚠️ {cat} menghabiskan {data['percentage']}% dari total. Terlalu dominan!"
                )
        
        # High single transaction
        if metrics.get('top_expenses'):
            top = metrics['top_expenses'][0]
            if top['amount'] > total * 0.3:
                warnings.append(
                    f"⚠️ Transaksi besar: {top['item']} (Rp {top['amount']:,}) = "
                    f"{round(top['amount']/total*100)}% pengeluaran minggu ini".replace(',', '.')
                )
        
        return warnings[:2]
    
    def analyze_spending_patterns(
        self, 
        transactions: List[Dict], 
        lookback_days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze spending patterns over a longer period.
        Useful for detecting recurring expenses and anomalies.
        """
        if not transactions:
            return {'patterns': [], 'recurring': [], 'anomalies': []}
        
        # Group by item name to find recurring
        item_frequency = defaultdict(list)
        
        for t in transactions:
            item = str(t.get('ITEM NAME') or t.get('item') or '').lower()
            amount = self._extract_amount(t)
            date = str(t.get('DATE') or t.get('date') or '')
            
            if item and amount > 0:
                item_frequency[item].append({
                    'amount': amount,
                    'date': date
                })
        
        # Detect recurring expenses (same item, 3+ times)
        recurring = []
        for item, occurrences in item_frequency.items():
            if len(occurrences) >= 3:
                amounts = [o['amount'] for o in occurrences]
                avg_amount = statistics.mean(amounts)
                recurring.append({
                    'item': item,
                    'frequency': len(occurrences),
                    'avg_amount': round(avg_amount),
                    'total': sum(amounts)
                })
        
        recurring.sort(key=lambda x: x['frequency'], reverse=True)
        
        # Detect anomalies (spending significantly higher than average)
        all_amounts = [self._extract_amount(t) for t in transactions 
                       if self._extract_amount(t) > 0]
        anomalies = []
        
        if len(all_amounts) >= 5:
            mean_amt = statistics.mean(all_amounts)
            std_amt = statistics.stdev(all_amounts) if len(all_amounts) > 1 else 0
            threshold = mean_amt + (2 * std_amt)
            
            for t in transactions:
                amount = self._extract_amount(t)
                if amount > threshold and amount > 100000:
                    anomalies.append({
                        'item': str(t.get('ITEM NAME') or t.get('item') or 'Unknown'),
                        'amount': amount,
                        'date': str(t.get('DATE') or t.get('date') or ''),
                        'category': str(t.get('CATEGORY') or t.get('category') or 'Other')
                    })
        
        return {
            'recurring': recurring[:5],
            'anomalies': anomalies[:5],
            'insights': {
                'total_transactions': len(transactions),
                'unique_items': len(item_frequency),
                'avg_transaction': round(statistics.mean(all_amounts)) if all_amounts else 0
            }
        }
    
    def format_weekly_report_message(self, report: Dict[str, Any]) -> str:
        """Format weekly report as Telegram message."""
        summary = report['summary']
        categories = report['category_breakdown']
        comparison = report['comparison']
        tips = report['tips']
        achievements = report['achievements']
        warnings = report['warnings']
        
        # Header
        lines = ["🧠 **LAPORAN MINGGUAN AI COACHING**", ""]
        
        # Summary
        total_str = f"{summary['total']:,}".replace(',', '.')
        avg_str = f"{summary['daily_avg']:,.0f}".replace(',', '.')
        lines.append(f"💰 **Total Pengeluaran:** Rp {total_str}")
        lines.append(f"📊 **Transaksi:** {summary['count']} kali")
        lines.append(f"📅 **Rata-rata Harian:** Rp {avg_str}")
        
        # Comparison with previous week
        if comparison:
            trend_emoji = "📈" if comparison['total_change'] > 0 else "📉"
            change_str = f"{abs(comparison['total_change']):,}".replace(',', '.')
            lines.append("")
            lines.append(f"{trend_emoji} **vs Minggu Lalu:** {comparison['trend']} "
                        f"({'+' if comparison['total_change'] > 0 else '-'}Rp {change_str})")
        
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        
        # Category breakdown
        lines.append("📂 **BREAKDOWN KATEGORI:**")
        for cat, data in list(categories.items())[:5]:
            amt_str = f"{data['amount']:,}".replace(',', '.')
            trend = ""
            if comparison and comparison.get('category_changes', {}).get(cat):
                trend = f" {comparison['category_changes'][cat]['trend']}"
            lines.append(f"  • {cat}: Rp {amt_str} ({data['percentage']}%){trend}")
        
        # Achievements
        if achievements:
            lines.append("")
            lines.append("🏆 **PENCAPAIAN:**")
            for ach in achievements:
                lines.append(f"  {ach}")
        
        # Warnings
        if warnings:
            lines.append("")
            for warn in warnings:
                lines.append(warn)
        
        # Tips
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("💡 **TIPS MINGGU INI:**")
        for i, tip in enumerate(tips, 1):
            lines.append(f"{i}. {tip}")
        
        lines.append("")
        lines.append("Semangat mengelola keuangan! 💪")
        
        return "\n".join(lines)


# Singleton instance
_coaching_engine = None

def get_coaching_engine() -> CoachingEngine:
    """Get singleton coaching engine instance."""
    global _coaching_engine
    if _coaching_engine is None:
        _coaching_engine = CoachingEngine()
    return _coaching_engine
