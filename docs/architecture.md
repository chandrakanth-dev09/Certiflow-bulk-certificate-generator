# CertiFlow architecture

## Request lifecycle

1. The client submits a generation request to FastAPI.
2. The route validates the payload and the generation service performs idempotency checks.
3. The service creates the job and its pending certificate records in one database transaction and commits.
4. Only after the commit, the API publishes a Celery task containing the job ID to Redis.
5. The API responds with HTTP 202 after the broker accepts the task. If publication fails, it logs the failure, attempts to mark the committed job failed, and returns HTTP 503.

```text
Client
  -> FastAPI
  -> Generation Service
  -> PostgreSQL (committed job and certificate rows)
  -> Celery client
  -> Redis broker
  -> Celery Worker
  -> GenerationWorker
  -> Certificate Generator
  -> Shared Storage
```

SQLite remains supported for local development and migration tests. Docker Compose uses PostgreSQL.

## Job lifecycle

Jobs are persisted before task dispatch. The worker moves a job to `PROCESSING` and derives progress from its certificate records. Finished jobs are `COMPLETED`, `COMPLETED_WITH_ERRORS`, `FAILED`, or `CANCELLED`.

## Certificate lifecycle

Each certificate begins as `PENDING`. A worker claims it with a conditional database update from `PENDING` to `PROCESSING`, then renders and stores the PDF. It becomes `COMPLETED` or, on an isolated generation error, `FAILED`. Cancellation can change unclaimed pending records to `CANCELLED`.

## Celery architecture

The Celery task `app.workers.certificate_worker.generate_certificate_job` accepts only a job ID. It opens and closes its own SQLAlchemy session and delegates processing to `GenerationWorker`; request sessions and ORM objects are never serialized into messages. Celery is used instead of production threads because it provides a separate worker process, broker-backed dispatch, and independent scaling for bulk jobs.

FastAPI background tasks or threads can be appropriate for simple local workloads, but they do not provide the same distributed execution boundary or broker-based work handoff.

## Redis role

Redis is the Celery broker and, by default, the result backend. `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` can override `REDIS_URL`. Queueing fails explicitly when the broker cannot accept a task; no success-shaped fallback is returned.

## Database role

The database stores job state, idempotency data, recipient/certificate state, certificate numbers, and generated file paths. Alembic migrations are the production schema authority. The API does not call `Base.metadata.create_all()` at startup.

## Storage role

Generated PDFs and job ZIPs are written under `STORAGE_DIR`. Compose mounts the same named volume at `/app/storage/certificates` in both API and worker containers so API downloads resolve worker-generated files.

## Failure isolation

Each certificate is processed independently. A rendering/storage exception marks that certificate failed and processing continues for other pending certificates. A single failed certificate does not automatically retry or fail the entire Celery task.

## Idempotency

The idempotency key is unique in the database and the normalized request hash is compared on reuse. Identical requests return the existing job; reusing a key with a changed request returns HTTP 409. Task execution is not exactly-once: duplicate task messages may occur, so the worker relies on persisted certificate state.

## Retry

The retry endpoint resets only failed certificates to pending, commits those transitions, and dispatches the job ID through Celery. The worker processes pending records and leaves completed records unchanged.

## Cancellation

Cancellation is cooperative. Pending certificates are marked cancelled. A certificate already in `PROCESSING` is not killed and may finish; subsequent work is not claimed because certificate claims only succeed for records still pending. The job becomes cancelled after no active/pending certificate work remains.

## Scaling strategy

Run additional Celery worker processes/containers against the same broker, database, and shared storage. Database conditional state transitions prevent two workers from claiming the same pending certificate concurrently. Workers still share job-level work and can process different certificates from the same job.

## Failure scenarios and limits

- **API crashes after creating a job:** if the crash occurs after commit but before publishing the task, the job can remain pending. This project does not implement a transactional outbox or automatic pending-job dispatcher.
- **Worker crashes:** an already claimed certificate can remain `PROCESSING`; no lease/stale-processing recovery is implemented. It is not automatically regenerated because a second worker will not claim a processing record.
- **Redis temporarily goes down:** a dispatch attempt that raises is logged, the API attempts to mark the committed job failed, and the request receives HTTP 503. A broker failure after accepting a message but before the sender receives confirmation can have an uncertain delivery outcome.
- **Certificate #50 fails:** that certificate is marked failed; other pending certificates continue. The final job is completed with errors if it also has successful certificates.
- **Two workers receive the same job:** both may load the job, but the conditional `PENDING` to `PROCESSING` update means only one can claim a given certificate. Duplicate task delivery is therefore tolerated at certificate state-transition boundaries, but task execution is not exactly-once.
