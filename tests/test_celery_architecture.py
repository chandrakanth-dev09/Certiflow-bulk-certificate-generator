import threading
from datetime import date


def test_enqueue_sends_only_job_id_to_celery(client, monkeypatch):
    from app.services.generation_service import enqueue_generation_job
    from app.workers import certificate_worker

    dispatched = []
    monkeypatch.setattr(certificate_worker.generate_certificate_job, "delay", lambda *args: dispatched.append(args))

    enqueue_generation_job("job-123")

    assert dispatched == [("job-123",)]


def test_generation_api_dispatches_only_job_id_without_starting_a_thread(client, monkeypatch):
    from app.workers import certificate_worker

    dispatched = []

    def capture_dispatch(job_id):
        from app.core import database
        from app.models.certificate import Certificate
        from app.models.job import GenerationJob

        with database.SessionLocal() as db:
            job_exists = db.get(GenerationJob, job_id) is not None
            certificate_count = db.query(Certificate).filter(Certificate.job_id == job_id).count()
        dispatched.append((job_id, job_exists, certificate_count))

    monkeypatch.setattr(
        certificate_worker.generate_certificate_job,
        "delay",
        capture_dispatch,
    )
    def reject_thread_creation(*args, **kwargs):
        raise AssertionError("request tried to create a thread")

    monkeypatch.setattr(threading, "Thread", reject_thread_creation)
    payload = {
        "event_name": "Celery Dispatch Test",
        "certificate_title": "Certificate of Completion",
        "completion_date": "2026-10-07",
        "recipients": [{"name": "Queue User", "email": "queue@example.com"}],
    }

    response = client.post("/api/v1/generation-jobs", json=payload)

    assert response.status_code == 202
    assert response.json()["status"] == "PENDING"
    assert dispatched == [(response.json()["job_id"], True, 1)]


def test_enqueue_failure_is_reported_and_persisted(client, monkeypatch):
    from app.workers import certificate_worker

    def fail_dispatch(*args):
        raise ConnectionError("broker unavailable")

    monkeypatch.setattr(
        certificate_worker.generate_certificate_job,
        "delay",
        fail_dispatch,
    )
    payload = {
        "event_name": "Broker Failure Test",
        "certificate_title": "Certificate of Completion",
        "completion_date": "2026-10-07",
        "recipients": [{"name": "Queue User", "email": "queue-fail@example.com"}],
    }

    response = client.post("/api/v1/generation-jobs", json=payload)

    assert response.status_code == 503
    job_id = response.json()["error"]["details"]["job_id"]
    status = client.get(f"/api/v1/generation-jobs/{job_id}").json()
    assert status["status"] == "FAILED"
    assert status["error_message"] == "The generation job could not be queued for processing."


def test_retry_dispatches_only_failed_certificates(client, monkeypatch):
    from app.workers import certificate_worker

    payload = {
        "event_name": "Retry Dispatch",
        "certificate_title": "Certificate of Completion",
        "completion_date": "2026-10-07",
        "recipients": [
            {"name": "Completed", "email": "completed-retry@example.com"},
            {"name": "Failed", "email": "failure.test@example.com"},
        ],
    }
    created = client.post("/api/v1/generation-jobs", json=payload)
    job_id = created.json()["job_id"]
    dispatched = []
    monkeypatch.setattr(
        certificate_worker.generate_certificate_job,
        "delay",
        lambda job_arg: dispatched.append(job_arg),
    )

    retry = client.post(f"/api/v1/generation-jobs/{job_id}/retry-failed")
    certificates = client.get(f"/api/v1/generation-jobs/{job_id}/certificates").json()["certificates"]
    statuses = {certificate["recipient_email"]: certificate["status"] for certificate in certificates}

    assert retry.status_code == 200
    assert retry.json()["queued_count"] == 1
    assert dispatched == [job_id]
    assert statuses == {
        "completed-retry@example.com": "COMPLETED",
        "failure.test@example.com": "PENDING",
    }


def test_pending_cancellation_does_not_enqueue_or_run_work(client, monkeypatch):
    from app.workers import certificate_worker

    dispatched = []
    monkeypatch.setattr(
        certificate_worker.generate_certificate_job,
        "delay",
        lambda job_id: dispatched.append(job_id),
    )
    payload = {
        "event_name": "Cancellation",
        "certificate_title": "Certificate of Completion",
        "completion_date": "2026-10-07",
        "recipients": [{"name": "Cancelled", "email": "cancel@example.com"}],
    }
    created = client.post("/api/v1/generation-jobs", json=payload)
    job_id = created.json()["job_id"]
    cancelled = client.post(f"/api/v1/generation-jobs/{job_id}/cancel")
    job = client.get(f"/api/v1/generation-jobs/{job_id}").json()
    certificates = client.get(f"/api/v1/generation-jobs/{job_id}/certificates").json()["certificates"]

    assert cancelled.status_code == 200
    assert job["status"] == "CANCELLED"
    assert certificates[0]["status"] == "CANCELLED"
    assert dispatched == [job_id]


def test_celery_task_owns_and_closes_database_session(monkeypatch):
    from app.core import database
    from app.workers import certificate_worker

    session = type("SessionSpy", (), {"closed": False, "close": lambda self: setattr(self, "closed", True)})()
    worker_calls = []

    class WorkerSpy:
        def __init__(self, db):
            self.db = db

        def process_job(self, job_id):
            worker_calls.append((job_id, self.db))
            return None

    monkeypatch.setattr(database, "SessionLocal", lambda: session)
    monkeypatch.setattr(certificate_worker, "GenerationWorker", WorkerSpy)

    certificate_worker.generate_certificate_job.run("job-456")

    assert worker_calls == [("job-456", session)]
    assert session.closed is True


def test_certificate_claim_is_state_guarded(client):
    from app.core import database
    from app.models.certificate import Certificate, CertificateStatus
    from app.models.job import GenerationJob, JobStatus
    from app.workers.generation_worker import _claim_certificate

    db = database.SessionLocal()
    try:
        job = GenerationJob(
            status=JobStatus.PENDING.value,
            total_count=1,
            pending_count=1,
            processing_count=0,
            completed_count=0,
            failed_count=0,
        )
        db.add(job)
        db.flush()
        certificate = Certificate(
            job_id=job.id,
            recipient_name="Claim Test",
            recipient_email="claim@example.com",
            certificate_title="Certificate of Completion",
            event_name="Claim Test",
            completion_date=date(2026, 10, 7),
            certificate_number="CERT-2026-CLAIM",
            status=CertificateStatus.PENDING.value,
        )
        db.add(certificate)
        db.commit()

        assert _claim_certificate(db, certificate) is True
        assert _claim_certificate(db, certificate) is False
        assert certificate.status == CertificateStatus.PROCESSING.value
    finally:
        db.close()
