"""
Export Service - Professional Redesign
Generates high-quality, data-analyst style financial reports.

Features:
- Professional "Clean & Minimalist" Layout
- Visual charts (Income vs Expense, Category Breakdown)
- "Storytelling" summary (AI-like analysis)
- Structured data tables
"""

import io
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# START: Import Check
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as ReportLabImage
    )
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logger.warning("❌ reportlab not installed. Run: pip install reportlab")

try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("❌ matplotlib not installed. Run: pip install matplotlib")
# END: Import Check


class ExportService:
    """
    Service for generating professional financial PDF reports.
    """

    def __init__(self):
        self.styles = None
        if REPORTLAB_AVAILABLE:
            self._setup_styles()

    def _setup_styles(self):
        """Setup custom paragraph styles for the report."""
        self.styles = getSampleStyleSheet()

        # 1. Main Title
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            leading=28,
            spaceAfter=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#2C3E50'),
            fontName='Helvetica-Bold'
        ))

        # 2. Subtitle (Date)
        self.styles.add(ParagraphStyle(
            name='ReportSubtitle',
            parent=self.styles['Normal'],
            fontSize=12,
            leading=14,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#7F8C8D'),
            fontName='Helvetica'
        ))

        # 3. Section Headers
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            leading=20,
            spaceBefore=20,
            spaceAfter=10,
            textColor=colors.HexColor('#2980B9'),
            fontName='Helvetica-Bold',
            borderPadding=5,
            borderWidth=0,
            allowWidows=0
        ))

        # 4. Normal Text (Storytelling)
        self.styles.add(ParagraphStyle(
            name='StoryText',
            parent=self.styles['Normal'],
            fontSize=11,
            leading=15,
            spaceAfter=12,
            alignment=TA_JUSTIFY,
            textColor=colors.HexColor('#34495E'),
            fontName='Helvetica'
        ))

        # 5. Footer
        self.styles.add(ParagraphStyle(
            name='FooterText',
            parent=self.styles['Normal'],
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#BDC3C7')
        ))

    def is_available(self) -> bool:
        return REPORTLAB_AVAILABLE

    def _create_income_expense_chart(self, income: int, expense: int) -> Optional[io.BytesIO]:
        """Generate a bar chart comparing Income vs Expense."""
        if not MATPLOTLIB_AVAILABLE:
            return None

        try:
            plt.figure(figsize=(6, 4))

            # Data
            labels = ['Pemasukan', 'Pengeluaran']
            values = [income, expense]
            colors_list = ['#2ECC71', '#E74C3C']  # Green, Red

            # Create bars
            bars = plt.bar(labels, values, color=colors_list, width=0.5)

            # Formatting
            plt.title('Pemasukan vs Pengeluaran', fontsize=12, pad=10, fontweight='bold', color='#2C3E50')
            plt.grid(axis='y', linestyle='--', alpha=0.3)
            plt.gca().spines['top'].set_visible(False)
            plt.gca().spines['right'].set_visible(False)

            # Add values on top of bars
            for bar in bars:
                height = bar.get_height()
                plt.text(bar.get_x() + bar.get_width() / 2., height,
                         f'Rp {int(height):,}',
                         ha='center', va='bottom', fontsize=10, color='#34495E')

            plt.tight_layout()

            # Save to buffer
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
            buf.seek(0)
            plt.close()
            return buf
        except Exception as e:
            logger.error(f"Failed to create income/expense chart: {e}")
            plt.close()
            return None

    def _create_category_pie_chart(self, category_breakdown: Dict) -> Optional[io.BytesIO]:
        """Generate a donut chart for expense categories."""
        if not MATPLOTLIB_AVAILABLE or not category_breakdown:
            return None

        try:
            plt.figure(figsize=(6, 4))

            # Sort categories by amount
            sorted_cats = sorted(
                category_breakdown.items(),
                key=lambda x: x[1].get('amount', 0),
                reverse=True
            )

            # Check if any data exists to plot
            total_amount_check = sum(item[1].get('amount', 0) for item in sorted_cats)
            if total_amount_check == 0:
                plt.close()
                return None

            # Take top 5 + Others
            top_n = 5
            labels = []
            sizes = []

            if len(sorted_cats) > top_n:
                others_amount = 0
                for i in range(len(sorted_cats)):
                    cat, data = sorted_cats[i]
                    if i < top_n:
                        labels.append(cat)
                        sizes.append(data.get('amount', 0))
                    else:
                        others_amount += data.get('amount', 0)
                if others_amount > 0:
                    labels.append('Lainnya')
                    sizes.append(others_amount)
            else:
                for cat, data in sorted_cats:
                    if data.get('amount', 0) > 0:
                        labels.append(cat)
                        sizes.append(data.get('amount', 0))

            if not sizes:
                plt.close()
                return None

            # Colors - Professional Palette
            colors_palette = ['#3498DB', '#9B59B6', '#F1C40F', '#E67E22', '#1ABC9C', '#95A5A6']

            # Create Pie/Donut Chart
            wedges, texts, autotexts = plt.pie(
                sizes,
                labels=labels,
                autopct='%1.1f%%',
                startangle=90,
                colors=colors_palette[:len(labels)],
                pctdistance=0.85,
                explode=[0.05] + [0] * (len(labels) - 1)  # Explode the first slice
            )

            # Draw center circle for donut style
            centre_circle = plt.Circle((0, 0), 0.70, fc='white')
            fig = plt.gcf()
            fig.gca().add_artist(centre_circle)

            # Decoration
            plt.title('Distribusi Pengeluaran', fontsize=12, pad=10, fontweight='bold', color='#2C3E50')
            plt.setp(autotexts, size=8, weight="bold", color="white")
            plt.setp(texts, size=9)

            plt.tight_layout()

            # Save
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=300, bbox_inches='tight')
            buf.seek(0)
            plt.close()
            return buf
        except Exception as e:
            logger.error(f"Failed to create pie chart: {e}")
            plt.close()
            return None

    def _generate_story(self, summary: Dict, category_breakdown: Dict) -> str:
        """Generate a professional 'Story' summary."""
        income = summary.get('total_income', 0)
        expense = summary.get('total_expense', 0)
        net = summary.get('net', 0)

        # 1. Overall Health
        if income == 0 and expense == 0:
            return "Belum ada transaksi yang tercatat untuk periode ini. Silakan mulai mencatat pemasukan dan pengeluaran Anda."

        savings_rate = (net / income * 100) if income > 0 else 0

        story = []

        # Paragraph 1: General Overview
        if net > 0:
            story.append(f"Secara keseluruhan, kondisi keuangan Anda periode ini **positif**. Total pemasukan tercatat sebesar **Rp {income:,}**, dengan total pengeluaran **Rp {expense:,}**.")
            story.append(f"Anda berhasil menyisihkan **Rp {net:,}** (surplus), yang setara dengan **{savings_rate:.1f}%** dari total pemasukan.")
        elif net < 0:
            story.append(f"Perhatian diperlukan untuk periode ini. Total pengeluaran (**Rp {expense:,}**) telah melebihi pemasukan (**Rp {income:,}**).")
            story.append(f"Terjadi defisit sebesar **Rp {abs(net):,}**. Disarankan untuk mengevaluasi kembali pos-pos pengeluaran yang tidak esensial.")
        else:
            story.append(f"Anda berada di titik impas (break-even). Pemasukan dan pengeluaran seimbang di angka **Rp {income:,}**.")

        # Paragraph 2: Top Spending Analysis
        if category_breakdown:
            # Find top category
            sorted_cats = sorted(category_breakdown.items(), key=lambda x: x[1].get('amount', 0), reverse=True)
            if sorted_cats:
                top_cat, top_data = sorted_cats[0]
                top_amount = top_data.get('amount', 0)
                top_percent = top_data.get('percentage', 0)

                story.append(f"\nFokus utama pengeluaran bulan ini adalah pada kategori **{top_cat}**, yang memakan porsi **{top_percent}%** dari total pengeluaran (Rp {top_amount:,}).")

                if len(sorted_cats) > 1:
                    second_cat, second_data = sorted_cats[1]
                    story.append(f"Pos pengeluaran terbesar kedua adalah **{second_cat}** ({second_data.get('percentage', 0)}%).")

        return " ".join(story).replace(',', '.')  # Format numbers Indonesian style manually if needed, or stick to standard

    def generate_monthly_report(
        self,
        transactions: List[Dict],
        category_breakdown: Dict[str, Any],
        summary: Dict[str, int],
        coaching_tips: List[str],
        period_label: str = "Bulan Ini"
    ) -> Optional[bytes]:
        """
        Generate the Full Professional Report.
        """
        if not REPORTLAB_AVAILABLE:
            return None

        try:
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=2 * cm, leftMargin=2 * cm,
                topMargin=2 * cm, bottomMargin=2 * cm,
                title=f"Laporan Keuangan - {period_label}"
            )

            elements = []

            # --- 1. HEADER ---
            elements.append(Paragraph("Laporan Analisis Keuangan", self.styles['ReportTitle']))
            elements.append(Paragraph(f"Periode: {period_label} | Generated: {datetime.now().strftime('%d %B %Y')}", self.styles['ReportSubtitle']))
            elements.append(Spacer(1, 10))

            # --- 2. EXECUTIVE SUMMARY (STORY) ---
            elements.append(Paragraph("Executive Summary", self.styles['SectionHeader']))
            story_text = self._generate_story(summary, category_breakdown)

            # Bold logic for markdown-like syntax (**text**)
            # ReportLab checks for <b> tags, so let's convert simple markdown bold to HTML bold
            formatted_story = story_text.replace('**', '<b>', 1).replace('**', '</b>', 1)
            while '**' in formatted_story:
                formatted_story = formatted_story.replace('**', '<b>', 1).replace('**', '</b>', 1)

            elements.append(Paragraph(formatted_story, self.styles['StoryText']))
            elements.append(Spacer(1, 10))

            # --- 3. KEY METRICS ---
            # Create a simple high-impact table
            elements.append(Paragraph("Financial Overview", self.styles['SectionHeader']))

            metrics_data = [
                ['PEMASUKAN', 'PENGELUARAN', 'NET CASH FLOW'],
                [
                    f"Rp {summary.get('total_income', 0):,}".replace(',', '.'),
                    f"Rp {summary.get('total_expense', 0):,}".replace(',', '.'),
                    f"Rp {summary.get('net', 0):,}".replace(',', '.')
                ]
            ]

            # Color logic for net
            net_val = summary.get('net', 0)
            net_color = colors.HexColor('#2ECC71') if net_val >= 0 else colors.HexColor('#E74C3C')

            t_metrics = Table(metrics_data, colWidths=[5.5 * cm, 5.5 * cm, 5.5 * cm])
            t_metrics.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.gray),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 1), (-1, -1), 14),
                ('TEXTCOLOR', (0, 1), (0, 1), colors.HexColor('#27AE60')),  # Income Green
                ('TEXTCOLOR', (1, 1), (1, 1), colors.HexColor('#C0392B')),  # Expense Red
                ('TEXTCOLOR', (2, 1), (2, 1), net_color),  # Net Color
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
            ]))
            elements.append(t_metrics)
            elements.append(Spacer(1, 20))

            # --- 4. VISUALIZATION (CHARTS) ---
            # We want side-by-side charts if possible, or stacked
            # Stacked is safer for PDF width

            # Bar Chart (Income vs Expense)
            bar_chart_buf = self._create_income_expense_chart(
                summary.get('total_income', 0),
                summary.get('total_expense', 0)
            )

            # Pie Chart (Categories)
            pie_chart_buf = self._create_category_pie_chart(category_breakdown)

            if bar_chart_buf and pie_chart_buf:
                # Create a table to hold charts side by side
                chart_img1 = ReportLabImage(bar_chart_buf, width=8 * cm, height=5.5 * cm)
                chart_img2 = ReportLabImage(pie_chart_buf, width=8 * cm, height=5.5 * cm)

                chart_data = [[chart_img1, chart_img2]]
                chart_table = Table(chart_data, colWidths=[8.5 * cm, 8.5 * cm])
                chart_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))
                elements.append(chart_table)
            elif bar_chart_buf:
                elements.append(ReportLabImage(bar_chart_buf, width=12 * cm, height=8 * cm))
            elif pie_chart_buf:
                elements.append(ReportLabImage(pie_chart_buf, width=12 * cm, height=8 * cm))

            elements.append(Spacer(1, 20))

            # --- 5. DETAILED BREAKDOWN ---
            # Only top 10 transactions to save space, or categorized summary
            elements.append(Paragraph("Category Breakdown", self.styles['SectionHeader']))

            if category_breakdown:
                cat_data = [['CATEGORY', 'AMOUNT', '%']]
                # Sort
                sorted_cats = sorted(category_breakdown.items(), key=lambda x: x[1].get('amount', 0), reverse=True)

                for cat, info in sorted_cats:
                    cat_data.append([
                        cat,
                        f"Rp {info.get('amount', 0):,}".replace(',', '.'),
                        f"{info.get('percentage', 0)}%"
                    ])

                t_cat = Table(cat_data, colWidths=[8 * cm, 5 * cm, 3 * cm])
                t_cat.setStyle(TableStyle([
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ECF0F1')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#2C3E50')),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),  # Amount right aligned
                    ('ALIGN', (2, 0), (-1, -1), 'CENTER'),  # % Center
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('PADDING', (0, 0), (-1, -1), 6),
                ]))
                elements.append(t_cat)
            else:
                elements.append(Paragraph("No expense data available.", self.styles['Normal']))

            elements.append(Spacer(1, 30))

            # --- 6. FOOTER ---
            elements.append(Paragraph("Report generated by Benny - Professional Financial Assistant", self.styles['FooterText']))

            # BUILD
            doc.build(elements)
            pdf_bytes = buffer.getvalue()
            buffer.close()

            return pdf_bytes

        except Exception as e:
            logger.error(f"Failed to generate report: {e}", exc_info=True)
            return None

    def _extract_amount(self, transaction: Dict) -> int:
        # Legacy helper, keeping it just in case, though not used in new layout directly
        # unless we add transaction list back.
        amount = (
            transaction.get('EXPENSE') or
            transaction.get('INCOME') or
            transaction.get('AMOUNTH(IDR)') or
            transaction.get('amount') or
            transaction.get('Amount (IDR)') or
            0
        )
        if isinstance(amount, str):
            clean = ''.join(c for c in amount if c.isdigit())
            return int(clean) if clean else 0
        try:
            return int(amount)
        except (ValueError, TypeError):
            return 0


# Singleton
_export_service = None


def get_export_service() -> ExportService:
    global _export_service
    if _export_service is None:
        _export_service = ExportService()
    return _export_service
