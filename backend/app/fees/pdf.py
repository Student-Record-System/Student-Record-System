from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def generate_receipt(payment):
    student = payment.student
    invoice = payment.invoice

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=25 * mm,
        leftMargin=25 * mm,
        topMargin=25 * mm,
        bottomMargin=25 * mm,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReceiptTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=20,
        spaceAfter=18,
    )

    rows = [
        ["Receipt Number", payment.receipt_number],
        ["Invoice Number", invoice.invoice_number],
        ["Student ID", str(payment.student_id)],
        ["Student Login ID", student.login_id],
        ["Description", invoice.description],
        ["Amount Paid", f"{payment.currency} {payment.amount}"],
        ["Payment Status", payment.status],
        ["Payment Gateway", payment.gateway],
        ["Transaction ID", payment.gateway_transaction_id],
        [
            "Payment Date",
            payment.paid_at.strftime("%d-%m-%Y %H:%M:%S")
            if payment.paid_at else "N/A",
        ],
    ]

    table = Table(rows, colWidths=[55 * mm, 105 * mm])

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))

    story = [
        Paragraph("FEE PAYMENT RECEIPT", title_style),
        Spacer(1, 10),
        table,
        Spacer(1, 20),
        Paragraph(
            "This is a system-generated receipt for the recorded payment.",
            styles["Normal"],
        ),
    ]

    document.build(story)
    buffer.seek(0)

    return buffer