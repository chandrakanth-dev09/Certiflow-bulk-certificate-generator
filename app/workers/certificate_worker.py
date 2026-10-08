from __future__ import annotations

from app.core import database
from app.workers.celery_app import celery_app
from app.workers.generation_worker import GenerationWorker


@celery_app.task(name="app.workers.certificate_worker.generate_certificate_job")
def generate_certificate_job(job_id: str) -> None:
    db = database.SessionLocal()
    try:
        GenerationWorker(db).process_job(job_id)
    finally:
        db.close()
