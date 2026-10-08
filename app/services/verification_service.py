from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.certificate import Certificate


def verify_certificate(db: Session, certificate_number: str) -> dict:
    certificate = db.query(Certificate).filter(Certificate.certificate_number == certificate_number).first()
    if certificate is None:
        return {"valid": False, "error": "Certificate not found."}
    return {
        "valid": certificate.status == "COMPLETED" and bool(certificate.file_path),
        "certificate_number": certificate.certificate_number,
        "recipient_name": certificate.recipient_name,
        "event_name": certificate.event_name,
        "completion_date": certificate.completion_date.isoformat(),
        "status": certificate.status,
    }
