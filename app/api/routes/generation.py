from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.job import GenerationJob
from app.schemas.generation import GenerationJobCreateRequest, GenerationJobCreateResponse, GenerationJobRead
from app.services.csv_service import validate_csv_upload
from app.services.generation_service import (
    build_job_zip_archive,
    cancel_generation_job,
    create_generation_job,
    enqueue_generation_job,
    get_job_by_id,
    retry_failed_certificates,
)
from app.services.storage_service import StorageService

router = APIRouter(prefix="/api/v1", tags=["generation"])


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _build_progress(job: GenerationJob) -> dict[str, Any]:
    total = max(job.total_count, 0)
    completed = max(job.completed_count, 0)
    failed = max(job.failed_count, 0)
    pending = max(job.pending_count, 0)
    processing = max(job.processing_count, 0)
    denominator = total if total else 1
    percentage = round(((completed + failed) / denominator) * 100, 2) if total else 0.0
    return {
        "total": total,
        "pending": pending,
        "processing": processing,
        "completed": completed,
        "failed": failed,
        "percentage": percentage,
    }


@router.get("/generation-jobs", summary="List generation jobs")
def list_jobs(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    jobs = db.query(GenerationJob).order_by(GenerationJob.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    total = db.query(GenerationJob).count()
    return {
        "items": [
            {
                "job_id": job.id,
                "status": job.status,
                "progress": _build_progress(job),
                "created_at": _iso(job.created_at),
                "started_at": _iso(job.started_at),
                "completed_at": _iso(job.completed_at),
            }
            for job in jobs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/generation-jobs", status_code=202, response_model=GenerationJobCreateResponse, summary="Create a bulk certificate generation job")
def create_generation_job_route(
    payload: GenerationJobCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    payload_dict = payload.model_dump(mode="json")
    job = create_generation_job(db, payload_dict, idempotency_key=idempotency_key)
    enqueue_generation_job(job.id)
    return GenerationJobCreateResponse(
        job_id=job.id,
        status=job.status,
        total_count=job.total_count,
        message="Certificate generation job accepted",
    )


@router.post("/generation-jobs/csv", status_code=202, summary="Create generation job from CSV upload")
async def create_generation_job_from_csv(
    file: UploadFile = File(...),
    event_name: str = Form(...),
    certificate_title: str = Form(...),
    completion_date: date = Form(...),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    recipients, validation_errors = validate_csv_upload(file)
    if validation_errors:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "CSV_VALIDATION_ERROR",
                    "message": "CSV input is invalid.",
                    "details": validation_errors,
                }
            },
        )

    payload = {
        "event_name": event_name,
        "certificate_title": certificate_title,
        "completion_date": completion_date.isoformat(),
        "recipients": recipients,
    }
    job = create_generation_job(db, payload, idempotency_key=idempotency_key)
    enqueue_generation_job(job.id)
    return GenerationJobCreateResponse(
        job_id=job.id,
        status=job.status,
        total_count=job.total_count,
        message="Certificate generation job accepted from CSV",
    )


@router.get("/generation-jobs/{job_id}", response_model=GenerationJobRead, summary="Fetch generation job status")
def get_generation_job_route(job_id: str, db: Session = Depends(get_db)):
    job = get_job_by_id(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "JOB_NOT_FOUND", "message": "Generation job not found", "details": {}}})
    return GenerationJobRead(
        job_id=job.id,
        status=job.status,
        progress=_build_progress(job),
        created_at=_iso(job.created_at),
        started_at=_iso(job.started_at),
        completed_at=_iso(job.completed_at),
        error_message=job.error_message,
    )


@router.get("/generation-jobs/{job_id}/certificates", summary="List certificates in a generation job")
def list_job_certificates(
    job_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    job = get_job_by_id(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "JOB_NOT_FOUND", "message": "Generation job not found", "details": {}}})

    total = len(job.certificates)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = job.certificates[start:end]

    return {
        "job_id": job.id,
        "page": page,
        "page_size": page_size,
        "total": total,
        "certificates": [
            {
                "id": cert.id,
                "recipient_name": cert.recipient_name,
                "recipient_email": cert.recipient_email,
                "certificate_number": cert.certificate_number,
                "status": cert.status,
                "file_path": cert.file_path,
                "failure_reason": cert.failure_reason,
                "created_at": _iso(cert.created_at),
                "generated_at": _iso(cert.generated_at),
            }
            for cert in page_items
        ],
    }


@router.get("/generation-jobs/{job_id}/download", summary="Download completed certificates for a job as ZIP")
def download_generation_job_zip(job_id: str, db: Session = Depends(get_db)):
    archive_path = build_job_zip_archive(db, job_id, StorageService())
    return FileResponse(path=archive_path, filename=f"{job_id}.zip", media_type="application/zip")


@router.post("/generation-jobs/{job_id}/retry-failed", summary="Reset failed certificates to pending for retry")
def retry_failed_generation_job(job_id: str, db: Session = Depends(get_db)):
    queued_count = retry_failed_certificates(db, job_id)
    job = get_job_by_id(db, job_id)
    return {"job_id": job_id, "queued_count": queued_count, "status": job.status if job else None}


@router.post("/generation-jobs/{job_id}/cancel", summary="Cooperatively cancel a running job")
def cancel_generation_job_route(job_id: str, db: Session = Depends(get_db)):
    job = cancel_generation_job(db, job_id)
    return {"job_id": job.id, "status": job.status, "message": "Cancellation requested"}
