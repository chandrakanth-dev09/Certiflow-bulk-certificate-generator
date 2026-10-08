from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.job import GenerationJob
from app.services.generation_service import create_generation_job, enqueue_generation_job, get_job_by_id


def create_job(db: Session, payload: dict, idempotency_key: str | None = None) -> GenerationJob:
    return create_generation_job(db, payload, idempotency_key=idempotency_key)


def get_job(db: Session, job_id: str) -> GenerationJob | None:
    return get_job_by_id(db, job_id)


def list_jobs(db: Session, page: int = 1, page_size: int = 20):
    query = db.query(GenerationJob).order_by(GenerationJob.created_at.desc())
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def trigger_background_job(job_id: str) -> None:
    enqueue_generation_job(job_id)
