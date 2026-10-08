from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.certificate import Certificate

router = APIRouter(prefix="/api/v1", tags=["certificates"])


def _iso(value):
    return value.isoformat() if value else None


@router.get("/certificates", summary="List certificates")
def list_certificates_route(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    job_id: str | None = Query(default=None, alias="job"),
    db: Session = Depends(get_db),
):
    query = db.query(Certificate)
    if status:
        query = query.filter(Certificate.status == status)
    if job_id:
        query = query.filter(Certificate.job_id == job_id)
    total = query.count()
    items = query.order_by(Certificate.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [
            {
                "id": certificate.id,
                "job_id": certificate.job_id,
                "recipient_name": certificate.recipient_name,
                "recipient_email": certificate.recipient_email,
                "certificate_number": certificate.certificate_number,
                "status": certificate.status,
                "file_path": certificate.file_path,
                "created_at": _iso(certificate.created_at),
                "generated_at": _iso(certificate.generated_at),
            }
            for certificate in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/certificates/{certificate_id}/metadata", summary="Get certificate metadata")
def get_certificate_metadata(certificate_id: str, db: Session = Depends(get_db)):
    certificate = db.query(Certificate).filter(Certificate.id == certificate_id).first()
    if certificate is None:
        raise HTTPException(404, detail={"error": {"code": "CERTIFICATE_NOT_FOUND", "message": "Certificate not found", "details": {}}})
    return {
        "id": certificate.id,
        "job_id": certificate.job_id,
        "recipient_name": certificate.recipient_name,
        "recipient_email": certificate.recipient_email,
        "certificate_title": certificate.certificate_title,
        "event_name": certificate.event_name,
        "completion_date": _iso(certificate.completion_date),
        "certificate_number": certificate.certificate_number,
        "status": certificate.status,
        "file_path": certificate.file_path,
        "failure_reason": certificate.failure_reason,
        "created_at": _iso(certificate.created_at),
        "generated_at": _iso(certificate.generated_at),
    }


@router.get("/certificates/{certificate_id}", summary="Download a completed certificate")
def download_certificate(certificate_id: str, db: Session = Depends(get_db)):
    certificate = db.query(Certificate).filter(Certificate.id == certificate_id).first()
    if certificate is None:
        raise HTTPException(404, detail={"error": {"code": "CERTIFICATE_NOT_FOUND", "message": "Certificate not found", "details": {}}})
    if certificate.status in {"PENDING", "PROCESSING"}:
        raise HTTPException(409, detail={"error": {"code": "CERTIFICATE_NOT_READY", "message": "Certificate is not ready for download yet", "details": {"status": certificate.status}}})
    if certificate.status == "FAILED":
        raise HTTPException(409, detail={"error": {"code": "CERTIFICATE_GENERATION_FAILED", "message": "Certificate generation failed", "details": {"failure_reason": certificate.failure_reason or "Unknown failure"}}})
    if not certificate.file_path:
        raise HTTPException(404, detail={"error": {"code": "CERTIFICATE_FILE_NOT_FOUND", "message": "Certificate file not found", "details": {}}})
    return FileResponse(path=certificate.file_path, filename=f"{certificate.certificate_number}.pdf", media_type="application/pdf")


@router.get("/certificates/{certificate_id}/download", summary="Download certificate PDF via explicit endpoint")
def download_certificate_alias(certificate_id: str, db: Session = Depends(get_db)):
    return download_certificate(certificate_id, db)


@router.get("/certificates/verify/{certificate_number}", summary="Verify certificate by certificate number")
def verify_certificate(certificate_number: str, db: Session = Depends(get_db)):
    certificate = db.query(Certificate).filter(Certificate.certificate_number == certificate_number).first()
    if certificate is None:
        raise HTTPException(404, detail={"error": {"code": "CERTIFICATE_NOT_FOUND", "message": "Certificate not found", "details": {}}})
    return {
        "valid": certificate.status == "COMPLETED" and bool(certificate.file_path),
        "certificate_number": certificate.certificate_number,
        "recipient_name": certificate.recipient_name,
        "event_name": certificate.event_name,
        "completion_date": certificate.completion_date.isoformat(),
        "status": certificate.status,
    }
