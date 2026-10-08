from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "certiflow",
    broker=settings.CELERY_BROKER_URL or settings.REDIS_URL,
    backend=settings.CELERY_RESULT_BACKEND or settings.REDIS_URL,
    include=["app.workers.certificate_worker"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

__all__ = ["celery_app"]
