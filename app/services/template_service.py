from __future__ import annotations

from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


class CertificateTemplateService:
    @staticmethod
    def render_certificate_pdf(
        *,
        recipient_name: str,
        event_name: str,
        certificate_title: str,
        certificate_number: str,
        completion_date: date,
        organization_name: str = "CertiFlow",
        issuer_name: str = "Assessment Office",
    ) -> bytes:
        import io

        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        # Keep the layout professional and deterministic while staying easy to explain.
        c.setStrokeColor(colors.HexColor("#1F2937"))
        c.setFillColor(colors.HexColor("#F8FAFC"))
        c.rect(18, 18, width - 36, height - 36, fill=1, stroke=1)

        c.setFillColor(colors.HexColor("#0F172A"))
        c.setFont("Helvetica-Bold", 30)
        c.drawCentredString(width / 2, height - 60, certificate_title)

        c.setStrokeColor(colors.HexColor("#0F172A"))
        c.line(80, height - 98, width - 80, height - 98)

        c.setFillColor(colors.HexColor("#111827"))
        c.setFont("Helvetica-Bold", 22)
        c.drawCentredString(width / 2, height - 150, organization_name)

        c.setFont("Helvetica", 16)
        c.drawCentredString(width / 2, height - 185, "This certifies that")

        c.setFillColor(colors.HexColor("#0F172A"))
        c.setFont("Helvetica-Bold", 28)
        c.drawCentredString(width / 2, height - 245, recipient_name)

        c.setFont("Helvetica", 16)
        c.drawCentredString(width / 2, height - 290, f"has successfully completed {event_name}")

        c.setFont("Helvetica", 14)
        c.drawCentredString(width / 2, height - 335, f"on {completion_date.isoformat()}")

        c.setFillColor(colors.HexColor("#374151"))
        c.setFont("Helvetica-Bold", 12)
        c.drawString(70, 120, f"Certificate Number: {certificate_number}")
        c.drawString(70, 95, f"Issued by: {issuer_name}")
        c.drawString(70, 70, f"Generated on: {date.today().isoformat()}")

        c.setFont("Helvetica-Bold", 12)
        c.drawString(width - 220, 120, "Authorized Signature")
        c.line(width - 240, 110, width - 80, 110)
        c.setFont("Helvetica", 10)
        c.drawString(width - 220, 90, issuer_name)

        c.setFillColor(colors.HexColor("#1D4ED8"))
        c.roundRect(width - 170, 150, 110, 110, 12, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#FFFFFF"))
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(width - 115, 196, "CERT")
        c.setFont("Helvetica", 10)
        c.drawCentredString(width - 115, 178, certificate_number)

        c.showPage()
        c.save()
        return buffer.getvalue()
