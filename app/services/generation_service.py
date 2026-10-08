from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.models.certificate import Certificate, CertificateStatus
from app.models.job import GenerationJob, JobStatus
from app.schemas.generation import GenerationJobCreateRequest
from app.services.storage_service import StorageService


def _fingerprint_payload(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "event_name": str(payload.get("event_name", "")).strip(),
        "certificate_title": str(payload.get("certificate_title", "")).strip(),
        "completion_date": payload.get("completion_date"),
        "recipients": [],
    }
    for recipient in payload.get("recipients", []):
        normalized["recipients"].append({
            "name": str(recipient.get("name", "")).strip(),
            "email": str(recipient.get("email", "")).strip().lower(),
        })
    return normalized


def create_generation_job(db: Session, payload: dict[str, Any], idempotency_key: str | None = None) -> GenerationJob:
    validated = GenerationJobCreateRequest.model_validate(payload)
    fingerprint = _fingerprint_payload(normalize_payload(payload))

    if idempotency_key:
        existing_job = db.query(GenerationJob).filter(GenerationJob.idempotency_key == idempotency_key).first()
        if existing_job is not None:
            if existing_job.request_hash != fingerprint:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": {
                            "code": "IDEMPOTENCY_CONFLICT",
                            "message": "The idempotency key was reused with a different request payload.",
                            "details": {},
                        }
                    },
                )
            return existing_job

    job = GenerationJob(
        status=JobStatus.PENDING.value,
        total_count=len(validated.recipients),
        pending_count=len(validated.recipients),
        processing_count=0,
        completed_count=0,
        failed_count=0,
        idempotency_key=idempotency_key,
        idempotency_fingerprint=fingerprint,
        request_hash=fingerprint,
        error_message=None,
    )
    db.add(job)
    db.flush()

    certificates: list[Certificate] = []
    used_certificate_numbers: set[str] = set()
    for recipient in validated.recipients:
        certificate_number = generate_certificate_number_for_date(validated.completion_date.year, db, used_certificate_numbers)
        certificate = Certificate(
            job_id=job.id,
            recipient_name=recipient.name,
            recipient_email=recipient.email,
            certificate_title=validated.certificate_title,
            event_name=validated.event_name,
            completion_date=validated.completion_date,
            certificate_number=certificate_number,
            status=CertificateStatus.PENDING.value,
        )
        used_certificate_numbers.add(certificate_number)
        certificates.append(certificate)
    db.add_all(certificates)
    db.commit()
    db.refresh(job)
    return job


def generate_certificate_number_for_date(year: int, db: Session, reserved_numbers: set[str] | None = None) -> str:
    prefix = f"CERT-{year}-"
    existing = db.query(Certificate.certificate_number).filter(Certificate.certificate_number.like(f"{prefix}%")).all()
    used = {row[0] for row in existing}
    if reserved_numbers:
        used.update(reserved_numbers)
    counter = 1
    while True:
        candidate = f"{prefix}{counter:06d}"
        if candidate not in used:
            return candidate
        counter += 1


def get_job_by_id(db: Session, job_id: str) -> GenerationJob | None:
    return db.query(GenerationJob).filter(GenerationJob.id == job_id).first()


def enqueue_generation_job(job_id: str) -> None:
    from app.workers.certificate_worker import generate_certificate_job

    try:
        generate_certificate_job.delay(job_id)
    except Exception as exc:
        logger.exception(
            "GENERATION_JOB_ENQUEUE_FAILED",
            extra={"job_id": job_id, "error": str(exc)},
        )
        from app.core import database

        db = database.SessionLocal()
        try:
            job = get_job_by_id(db, job_id)
            if job is not None and job.status in {JobStatus.PENDING.value, JobStatus.PROCESSING.value}:
                job.status = JobStatus.FAILED.value
                job.error_message = "The generation job could not be queued for processing."
                job.completed_at = datetime.utcnow()
                db.commit()
        except Exception:
            db.rollback()
            logger.exception(
                "GENERATION_JOB_ENQUEUE_FAILURE_STATUS_UPDATE_FAILED",
                extra={"job_id": job_id},
            )
        finally:
            db.close()
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "code": "GENERATION_QUEUE_UNAVAILABLE",
                    "message": "The generation job was saved but could not be queued for processing.",
                    "details": {"job_id": job_id},
                }
            },
        ) from exc


def retry_failed_certificates(db: Session, job_id: str) -> int:
    job = get_job_by_id(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "JOB_NOT_FOUND", "message": "Generation job not found", "details": {}}})

    requeued = 0
    for certificate in job.certificates:
        if certificate.status == CertificateStatus.FAILED.value:
            certificate.status = CertificateStatus.PENDING.value
            certificate.failure_reason = None
            certificate.file_path = None
            certificate.generated_at = None
            requeued += 1
    if requeued:
        job.status = JobStatus.PENDING.value
        job.error_message = None
        job.started_at = None
        db.commit()
        enqueue_generation_job(job_id)
    return requeued


def cancel_generation_job(db: Session, job_id: str) -> GenerationJob:
    job = get_job_by_id(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "JOB_NOT_FOUND", "message": "Generation job not found", "details": {}}})

    for certificate in job.certificates:
        if certificate.status == CertificateStatus.PENDING.value:
            certificate.status = CertificateStatus.CANCELLED.value
            certificate.failure_reason = "Cancelled by operator"
        elif certificate.status == CertificateStatus.PROCESSING.value:
            certificate.failure_reason = certificate.failure_reason or "Cancellation requested while processing"

    job.status = JobStatus.PENDING.value
    if not any(certificate.status == CertificateStatus.PROCESSING.value for certificate in job.certificates):
        job.status = JobStatus.CANCELLED.value
        job.completed_at = job.completed_at or datetime.utcnow()
    db.commit()
    return job


def build_job_zip_archive(db: Session, job_id: str, storage_service: StorageService | None = None) -> str:
    job = get_job_by_id(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "JOB_NOT_FOUND", "message": "Generation job not found", "details": {}}})
    if job.status in {JobStatus.PENDING.value, JobStatus.PROCESSING.value}:
        raise HTTPException(status_code=409, detail={"error": {"code": "JOB_NOT_READY", "message": "Job is still processing and cannot be downloaded yet", "details": {}}})

    completed_certificates = [cert for cert in job.certificates if cert.status == CertificateStatus.COMPLETED.value and cert.file_path]
    if not completed_certificates:
        raise HTTPException(status_code=404, detail={"error": {"code": "NO_COMPLETED_CERTIFICATES", "message": "No certificates are available to download for this job", "details": {}}})

    storage = storage_service or StorageService(settings.STORAGE_DIR)
    archive_path = storage.build_zip_for_completed_certificates(job_id, completed_certificates)
    return archive_path
