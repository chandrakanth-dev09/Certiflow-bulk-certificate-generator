from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.certificate import Certificate


class CertificateRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_number(self, certificate_number: str):
        return self.db.query(Certificate).filter(Certificate.certificate_number == certificate_number).first()

    def list(self, *, page: int = 1, page_size: int = 20, status: str | None = None, job_id: int | None = None, certificate_number: str | None = None, recipient_name: str | None = None, recipient_email: str | None = None):
        query = self.db.query(Certificate)
        if status:
            query = query.filter(Certificate.status == status)
        if job_id is not None:
            query = query.filter(Certificate.job_id == job_id)
        if certificate_number:
            query = query.filter(Certificate.certificate_number.ilike(f"%{certificate_number}%"))
        if recipient_name:
            query = query.filter(Certificate.recipient_name.ilike(f"%{recipient_name}%"))
        if recipient_email:
            query = query.filter(Certificate.recipient_email.ilike(f"%{recipient_email}%"))
        query = query.order_by(Certificate.created_at.desc())
        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return items, total
