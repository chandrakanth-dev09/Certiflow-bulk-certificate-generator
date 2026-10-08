from __future__ import annotations

from datetime import datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.models.certificate import Certificate, CertificateStatus
from app.models.job import GenerationJob, JobStatus
from app.services.storage_service import StorageService
from app.services.template_service import CertificateTemplateService


class GenerationWorker:
    def __init__(self, db: Session):
        self.db = db

    def process_job(self, job_id: str) -> None:
        db = self.db
        job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
        if job is None:
            return

        job.started_at = job.started_at or datetime.utcnow()
        if job.status == JobStatus.CANCELLED.value:
            _refresh_job_progress(db, job)
            return

        job.status = JobStatus.PROCESSING.value
        db.add(job)
        db.commit()

        storage_service = StorageService(settings.STORAGE_DIR)
        for certificate in job.certificates:
            if job.status == JobStatus.CANCELLED.value:
                break
            if certificate.status != CertificateStatus.PENDING.value:
                continue
            try:
                if not _claim_certificate(db, certificate):
                    continue
                logger.info(
                    "CERTIFICATE_GENERATION_STARTED",
                    extra={
                        "job_id": job.id,
                        "certificate_id": certificate.id,
                        "certificate_number": certificate.certificate_number,
                    },
                )
                _process_single_certificate(db, certificate, storage_service)
                logger.info(
                    "CERTIFICATE_GENERATION_COMPLETED",
                    extra={
                        "job_id": job.id,
                        "certificate_id": certificate.id,
                        "certificate_number": certificate.certificate_number,
                    },
                )
            except Exception as exc:  # Per-certificate failure isolation
                certificate_id = certificate.id
                db.rollback()
                certificate = db.get(Certificate, certificate_id)
                if certificate is None:
                    raise
                certificate.status = CertificateStatus.FAILED.value
                certificate.failure_reason = str(exc)
                certificate.generated_at = datetime.utcnow()
                db.add(certificate)
                db.commit()
                logger.exception(
                    "CERTIFICATE_GENERATION_FAILED",
                    extra={
                        "job_id": job.id,
                        "certificate_id": certificate.id,
                        "certificate_number": certificate.certificate_number,
                        "failure_reason": str(exc),
                    },
                )
            finally:
                _refresh_job_progress(db, job)

        final_status = _job_summary_for_status(job)
        if final_status in {
            JobStatus.COMPLETED.value,
            JobStatus.COMPLETED_WITH_ERRORS.value,
            JobStatus.FAILED.value,
            JobStatus.CANCELLED.value,
        }:
            job.status = final_status
            if job.completed_at is None:
                job.completed_at = datetime.utcnow()
        db.add(job)
        db.commit()


def _job_summary_for_status(job: GenerationJob) -> str:
    cancelled = sum(1 for certificate in job.certificates if certificate.status == CertificateStatus.CANCELLED.value)
    if job.status == JobStatus.CANCELLED.value:
        return JobStatus.CANCELLED.value
    if job.total_count == 0:
        return JobStatus.COMPLETED.value
    if cancelled == job.total_count:
        return JobStatus.CANCELLED.value
    if cancelled > 0 and job.pending_count == 0 and job.processing_count == 0:
        return JobStatus.CANCELLED.value
    if job.failed_count == job.total_count:
        return JobStatus.FAILED.value
    if job.completed_count == job.total_count:
        return JobStatus.COMPLETED.value
    if job.failed_count > 0 and job.completed_count > 0:
        return JobStatus.COMPLETED_WITH_ERRORS.value
    if job.processing_count > 0:
        return JobStatus.PROCESSING.value
    if job.pending_count > 0:
        return JobStatus.PENDING.value
    return JobStatus.PENDING.value


def _refresh_job_progress(db: Session, job: GenerationJob) -> None:
    certs = job.certificates
    job.pending_count = sum(1 for cert in certs if cert.status == CertificateStatus.PENDING.value)
    job.processing_count = sum(1 for cert in certs if cert.status == CertificateStatus.PROCESSING.value)
    job.completed_count = sum(1 for cert in certs if cert.status == CertificateStatus.COMPLETED.value)
    job.failed_count = sum(1 for cert in certs if cert.status == CertificateStatus.FAILED.value)
    job.total_count = len(certs)

    if job.status == JobStatus.CANCELLED.value and job.completed_at is None:
        job.completed_at = datetime.utcnow()

    job.status = _job_summary_for_status(job)
    if job.status in {
        JobStatus.COMPLETED.value,
        JobStatus.COMPLETED_WITH_ERRORS.value,
        JobStatus.FAILED.value,
        JobStatus.CANCELLED.value,
    } and job.completed_at is None:
        job.completed_at = datetime.utcnow()
    if job.status in {JobStatus.PROCESSING.value, JobStatus.PENDING.value} and job.started_at is None:
        job.started_at = datetime.utcnow()
    db.commit()


def _claim_certificate(db: Session, certificate: Certificate) -> bool:
    result = db.execute(
        update(Certificate)
        .where(
            Certificate.id == certificate.id,
            Certificate.status == CertificateStatus.PENDING.value,
        )
        .values(status=CertificateStatus.PROCESSING.value)
    )
    db.commit()
    if result.rowcount != 1:
        db.refresh(certificate)
        return False
    db.refresh(certificate)
    return True


def _process_single_certificate(db: Session, certificate: Certificate, storage_service: StorageService) -> None:
    if settings.ENVIRONMENT.lower() != "production" and certificate.recipient_email.lower() == "failure.test@example.com":
        raise RuntimeError("simulated certificate generation failure")

    pdf_bytes = CertificateTemplateService.render_certificate_pdf(
        recipient_name=certificate.recipient_name,
        event_name=certificate.event_name,
        certificate_title=certificate.certificate_title,
        certificate_number=certificate.certificate_number,
        completion_date=certificate.completion_date,
    )
    certificate.file_path = storage_service.save_pdf(
        job_id=certificate.job_id,
        certificate_id=certificate.id,
        pdf_bytes=pdf_bytes,
        certificate_number=certificate.certificate_number,
    )
    certificate.status = CertificateStatus.COMPLETED.value
    certificate.failure_reason = None
    certificate.generated_at = datetime.utcnow()
    db.add(certificate)
    db.commit()
