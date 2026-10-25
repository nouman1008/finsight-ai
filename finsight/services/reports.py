"""PDF financial report generation with ReportLab."""
from __future__ import annotations

from datetime import date
from io import BytesIO
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from finsight.formatting import format_currency, format_percent
from finsight.services.calculations import Summary

NAVY = colors.HexColor("#0B1220")
EMERALD = colors.HexColor("#059669")
ZEBRA = colors.HexColor("#F1F5F9")
MAX_TRANSACTION_ROWS = 300


def _table(data: list[list[str]], col_widths: list[int]) -> Table:
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table


def build_pdf_report(
    title: str,
    period_label: str,
    summary: Summary,
    categories: pd.DataFrame,
    transactions: pd.DataFrame,
    insight_lines: list[str],
) -> bytes:
    """Render a PDF with summary metrics, category totals, insights and transaction details."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=40, rightMargin=40,
                            topMargin=40, bottomMargin=40, title=title, author="FinSight AI")
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("FSTitle", parent=styles["Title"], textColor=NAVY, alignment=0, fontSize=20)
    heading = ParagraphStyle("FSHeading", parent=styles["Heading3"], textColor=EMERALD, spaceBefore=12, spaceAfter=6)
    body = styles["BodyText"]

    story = [
        Paragraph(escape(title), title_style),
        Paragraph(f"Period: {escape(period_label)}", body),
        Paragraph(f"Generated {date.today():%d %b %Y}", body),
        Spacer(1, 8),
        Paragraph("Summary", heading),
        _table([
            ["Metric", "Value"],
            ["Income", format_currency(summary.income)],
            ["Expenses", format_currency(summary.expenses)],
            ["Net savings", format_currency(summary.net)],
            ["Savings rate", format_percent(summary.savings_rate)],
            ["Transactions recorded", str(summary.transaction_count)],
        ], [200, 200]),
        Paragraph("Expense categories", heading),
    ]

    if categories.empty:
        story.append(Paragraph("No expenses recorded in this period.", body))
    else:
        rows = [["Category", "Amount", "Share"]]
        rows += [[c.category, format_currency(c.amount), format_percent(c.share)] for c in categories.itertuples(index=False)]
        story.append(_table(rows, [200, 150, 100]))

    story.append(Paragraph("Insights", heading))
    if insight_lines:
        for line in insight_lines:
            story.append(Paragraph("- " + escape(line), body))
    else:
        story.append(Paragraph("No insights for this period.", body))

    story.append(Paragraph("Transactions", heading))
    if transactions.empty:
        story.append(Paragraph("No transactions in this period.", body))
    else:
        ordered = transactions.sort_values(["date", "id"]).head(MAX_TRANSACTION_ROWS)
        rows = [["Date", "Title", "Category", "Type", "Amount"]]
        for t in ordered.itertuples(index=False):
            rows.append([t.date.strftime("%d %b %Y"), str(t.title)[:40], t.category,
                         t.type.capitalize(), format_currency(t.amount)])
        story.append(_table(rows, [65, 180, 110, 60, 100]))
        if len(transactions) > MAX_TRANSACTION_ROWS:
            story.append(Paragraph(
                f"Showing the first {MAX_TRANSACTION_ROWS} of {len(transactions)} transactions. "
                "Export CSV for the full list.", body))

    doc.build(story)
    return buffer.getvalue()
