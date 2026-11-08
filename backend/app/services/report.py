"""Branded PDF summary built with ReportLab."""
from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .segmentation import SEGMENT_META

ESPRESSO, BRONZE, INK = colors.HexColor("#2A1209"), colors.HexColor("#B97C4D"), colors.HexColor("#3A2A22")
H1 = ParagraphStyle("h1", fontName="Times-Roman", fontSize=30, leading=34, textColor=ESPRESSO)
H2 = ParagraphStyle("h2", fontName="Times-Roman", fontSize=17, leading=22, textColor=ESPRESSO, spaceBefore=12, spaceAfter=6)
BODY = ParagraphStyle("b", fontName="Helvetica", fontSize=10, leading=15, textColor=INK)


def _table(rows: list[list[str]], widths: list[float]) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ESPRESSO), ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#F3E4D2")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LINEBELOW", (0, 1), (-1, -1), .4, colors.HexColor("#DCC3AA")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def pdf(analysis: dict) -> bytes:
    """Render a summary; every value comes from the request, so text is escaped."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm,
                            bottomMargin=16 * mm, title="Segmora customer report", author="Segmora")
    cur = analysis["currency"]
    story = [Paragraph("Segmora", H1), Spacer(1, 4),
             Paragraph(f"Customer segment report. {analysis['customers']:,} customers, "
                       f"{cur}{analysis['total_revenue']:,.0f} total revenue. Source: {escape(str(analysis['source_label']))}.", BODY),
             Paragraph("Segments", H2)]
    rows = [["Segment", "Customers", "Share", "Revenue share", "Typical orders", "Last purchase"]]
    for s in analysis["segments"]:
        m = s["medians"]
        rows.append([SEGMENT_META[s["key"]]["name"], f"{s['customers']:,}",
                     f"{s['customer_share'] * 100:.0f}%", f"{s['revenue_share'] * 100:.0f}%",
                     f"{m.get('orders', 0):.0f}", f"{m.get('recency_days', 0):.0f} days ago"])
    story.append(_table(rows, [46 * mm, 24 * mm, 18 * mm, 28 * mm, 26 * mm, 32 * mm]))
    story.append(Paragraph("Contact first", H2))
    rows = [["Customer", "Spend", "Why", "Next step"]]
    for p in analysis["priority"][:15]:
        spend = f"{cur}{p['total_spend']:,.0f}"
        rows.append([p["customer_id"][:16], spend, Paragraph(escape(p["reason"]), BODY), p["action"]])
    if len(rows) == 1:
        story.append(Paragraph("No urgent follow-ups were found in this data.", BODY))
    else:
        story.append(_table(rows, [24 * mm, 22 * mm, 88 * mm, 40 * mm]))
    doc.build(story)
    return buffer.getvalue()
