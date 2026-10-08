from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.verification_service import verify_certificate

router = APIRouter(prefix="/api/v1", tags=["verification"])


@router.get("/certificates/verify/{certificate_number}")
async def verify_certificate_route(certificate_number: str, db: Session = Depends(get_db)):
    result = verify_certificate(db, certificate_number)
    if not result.get("valid"):
        raise HTTPException(status_code=404, detail={"error": {"code": "CERTIFICATE_NOT_FOUND", "message": result.get("error", "Certificate not found."), "details": {}}})
    return {
        "valid": True,
        "certificate_number": result["certificate_number"],
        "recipient_name": result["recipient_name"],
        "event_name": result["event_name"],
        "completion_date": result["completion_date"],
        "status": result["status"],
    }
