from __future__ import annotations

from datetime import date

from app.models.certificate import Certificate
from app.services.generation_service import generate_certificate_number_for_date
from app.services.template_service import CertificateTemplateService


def generate_certificate_number(year: int | None = None, db=None) -> str:
    target_year = year or date.today().year
    if db is None:
        return f"CERT-{target_year}-000001"
    return generate_certificate_number_for_date(target_year, db)


def build_verification_url(certificate_number: str) -> str:
    return f"/api/v1/certificates/verify/{certificate_number}"


def generate_certificate_pdf(certificate: Certificate) -> bytes:
    return CertificateTemplateService.render_certificate_pdf(
        recipient_name=certificate.recipient_name,
        event_name=certificate.event_name,
        certificate_title=certificate.certificate_title,
        certificate_number=certificate.certificate_number,
        completion_date=certificate.completion_date,
    )
