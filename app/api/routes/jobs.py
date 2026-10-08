from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.job import GenerationJob
from app.schemas.generation import GenerationJobCreateRequest, GenerationJobCreateResponse
from app.services.generation_service import cancel_generation_job, create_generation_job, enqueue_generation_job, get_job_by_id, retry_failed_certificates

router = APIRouter(prefix="/api/v1", tags=["jobs"])


@router.post("/jobs", status_code=202, response_model=GenerationJobCreateResponse)
def create_job_route(
    payload: GenerationJobCreateRequest,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    job = create_generation_job(db, payload.model_dump(mode="json"), idempotency_key=idempotency_key)
    enqueue_generation_job(job.id)
    return GenerationJobCreateResponse(job_id=job.id, status=job.status, total_count=job.total_count)


@router.get("/jobs")
def list_jobs_route(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    items = db.query(GenerationJob).order_by(GenerationJob.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [{"job_id": item.id, "status": item.status, "total_count": item.total_count} for item in items], "total": db.query(GenerationJob).count()}


@router.get("/jobs/{job_id}")
def get_job_route(job_id: str, db: Session = Depends(get_db)):
    job = get_job_by_id(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "JOB_NOT_FOUND", "message": "Generation job not found", "details": {}}})
    total = job.total_count or 1
    percentage = round(((job.completed_count + job.failed_count) / total) * 100, 2) if total else 0.0
    return {
        "job_id": job.id,
        "status": job.status,
        "progress": {"total": job.total_count, "pending": job.pending_count, "processing": job.processing_count, "completed": job.completed_count, "failed": job.failed_count, "percentage": percentage},
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


@router.post("/jobs/{job_id}/retry-failed")
def retry_failed_job_route(job_id: str, db: Session = Depends(get_db)):
    queued = retry_failed_certificates(db, job_id)
    return {"job_id": job_id, "queued_count": queued}


@router.post("/jobs/{job_id}/cancel")
def cancel_job_route(job_id: str, db: Session = Depends(get_db)):
    job = cancel_generation_job(db, job_id)
    return {"job_id": job.id, "status": job.status, "message": "Cancellation requested"}
