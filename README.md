# CertiFlow

Bulk Certificate Generation & Verification API.

This project provides a FastAPI backend for creating, tracking, and verifying bulk certificate generation jobs. It supports asynchronous generation through Celery and Redis, per-certificate failure isolation, CSV upload workflows, idempotent job creation, and PDF downloads.

## Features

- Create generation jobs with validation and optional `Idempotency-Key`
- Process certificates asynchronously through Celery workers and Redis
- Track total, pending, processing, completed, failed, and cancelled counts
- Store generated PDFs under `storage/certificates/<job_id>/<certificate_id>.pdf`
- Download a ZIP archive for a finished job
- Retry failed certificates without regenerating successful ones
- Cancel cooperative jobs while preventing new work from starting
- Verify certificates by certificate number
- Upload recipient lists using CSV
- Use SQLite by default for local development; PostgreSQL can be configured via `DATABASE_URL`

## Architecture

```text
Client -> FastAPI -> PostgreSQL -> Celery -> Redis -> Celery Worker
                                                  -> Certificate Generator
                                                  -> Shared Storage
```

FastAPI commits job and certificate rows before publishing a job-ID-only task. Celery and Redis are used to isolate bulk processing from API request processes and to allow worker processes to scale independently. Production job processing does not use `threading.Thread`; threads may suit simple local workloads, but do not provide this broker-backed process boundary.

## API overview

- `POST /api/v1/generation-jobs`
- `POST /api/v1/generation-jobs/csv`
- `GET /api/v1/generation-jobs/{job_id}`
- `GET /api/v1/generation-jobs/{job_id}/certificates`
- `GET /api/v1/generation-jobs/{job_id}/download`
- `POST /api/v1/generation-jobs/{job_id}/retry-failed`
- `POST /api/v1/generation-jobs/{job_id}/cancel`
- `GET /api/v1/certificates/{certificate_id}`
- `GET /api/v1/certificates/verify/{certificate_number}`
- `GET /health`
- `GET /health/ready`

## Local setup

1. Create a virtual environment and install dependencies from `requirements.txt`.
2. Copy `.env.example` to `.env` if needed and set `DATABASE_URL`, `REDIS_URL`, and storage settings. This example uses SQLite and assumes a local Redis server.
3. Start Redis using the URL configured by `REDIS_URL` (or specify `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` separately).
4. Apply the schema with `alembic upgrade head`.
5. In separate terminals, start the API with `uvicorn app.main:app --reload` and a worker with `celery -A app.workers.celery_app:celery_app worker --loglevel=INFO`.
6. Run tests with `python -m pytest -q`.

The API does not create or modify the database schema at startup; Alembic migrations are the schema authority.
The automated tests do not require Redis: they mock task publication or invoke the task body in-process. They verify dispatch and worker behavior, but do not substitute for a live Redis/Celery deployment test.

## Docker Compose

Copy `.env.docker.example` to `.env` and replace its placeholder password with a local secret. The sample `DATABASE_URL` resolves the environment values and points to the Compose `postgres` service. Run:

```powershell
docker compose build
docker compose up
docker compose exec api alembic upgrade head
docker compose logs api
docker compose logs worker
docker compose down
```

The API container applies migrations before starting; the explicit `exec` command is useful to confirm migration status or apply later migrations. PostgreSQL and Redis health checks gate API startup, and the worker starts after the API is healthy. API and worker share the certificate storage volume.

## Notes

- Validation failures return HTTP 422 before a job is created.
- Certificate generation failures do not stop the rest of the job; only the individual certificate is marked as failed.
- Idempotency conflicts return HTTP 409 when the same `Idempotency-Key` is reused with a different payload.
- The Celery task payload contains only the generation job ID; the worker opens its own database session and loads recipients and certificates from the database.
- Status values are stored as strings, matching the SQLAlchemy models; no native database enum type is used.
- If the broker rejects a dispatch after the job has committed, the API logs the failure, marks the job failed with an explanatory message when possible, and returns HTTP 503. A crash in the narrow interval after commit and before dispatch can still leave a pending job; no transactional outbox is implemented.
- Celery/Redis does not provide exactly-once execution. Workers use database state-aware certificate claims to avoid concurrently generating a certificate that is already processing.
- Cancellation is cooperative: pending certificates are cancelled; a certificate already processing may finish before the worker stops taking additional work.
