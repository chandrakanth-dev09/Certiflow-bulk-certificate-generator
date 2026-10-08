from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.job import GenerationJob


class JobRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, job_id: int) -> GenerationJob | None:
        return self.db.query(GenerationJob).filter(GenerationJob.id == job_id).first()

    def get_by_public_job_id(self, public_job_id: str) -> GenerationJob | None:
        return self.db.query(GenerationJob).filter(GenerationJob.public_job_id == public_job_id).first()

    def get_by_idempotency_key(self, key: str) -> GenerationJob | None:
        return self.db.query(GenerationJob).filter(GenerationJob.idempotency_key == key).first()

    def list(self, page: int = 1, page_size: int = 20):
        query = self.db.query(GenerationJob).order_by(GenerationJob.created_at.desc())
        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()
        return items, total
