from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.certificate import Certificate


def get_certificate_by_id(db: Session, certificate_id: str) -> Certificate | None:
    return db.query(Certificate).filter(Certificate.id == certificate_id).first()


def get_certificate_by_number(db: Session, certificate_number: str) -> Certificate | None:
    return db.query(Certificate).filter(Certificate.certificate_number == certificate_number).first()


def list_certificates(db: Session, *, page: int = 1, page_size: int = 20, status: str | None = None, job_id: str | None = None):
    query = db.query(Certificate)
    if status:
        query = query.filter(Certificate.status == status)
    if job_id is not None:
        query = query.filter(Certificate.job_id == job_id)
    total = query.count()
    items = query.order_by(Certificate.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return items, total
