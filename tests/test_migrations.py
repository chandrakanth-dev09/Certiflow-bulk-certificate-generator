import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run_alembic(*arguments: str, database_url: str, env: dict[str, str]) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=PROJECT_ROOT,
        env={**env, "DATABASE_URL": database_url},
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout + result.stderr


def test_initial_migration_creates_current_schema_and_valid_history(tmp_path):
    database_url = f"sqlite:///{(tmp_path / 'fresh.db').as_posix()}"
    environment = os.environ.copy()

    _run_alembic("upgrade", "head", database_url=database_url, env=environment)
    current = _run_alembic("current", database_url=database_url, env=environment)
    history = _run_alembic("history", database_url=database_url, env=environment)
    check = _run_alembic("check", database_url=database_url, env=environment)

    assert "20261008_0001" in current
    assert "20261008_0001" in history
    assert "No new upgrade operations detected" in check

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        assert set(inspector.get_table_names()) == {"alembic_version", "generation_jobs", "certificates"}
        assert {item["name"] for item in inspector.get_columns("generation_jobs")} == {
            "id", "idempotency_key", "idempotency_fingerprint", "request_hash", "status",
            "total_count", "pending_count", "processing_count", "completed_count", "failed_count",
            "created_at", "started_at", "completed_at", "error_message",
        }
        assert {item["name"] for item in inspector.get_columns("certificates")} == {
            "id", "job_id", "recipient_name", "recipient_email", "certificate_title", "event_name",
            "completion_date", "certificate_number", "status", "file_path", "failure_reason",
            "created_at", "generated_at",
        }
        assert {index["name"] for index in inspector.get_indexes("generation_jobs")} == {
            "ix_generation_jobs_idempotency_fingerprint",
            "ix_generation_jobs_request_hash",
            "ix_generation_jobs_status",
        }
        assert {index["name"] for index in inspector.get_indexes("certificates")} == {
            "ix_certificates_job_id",
            "ix_certificates_recipient_email",
            "ix_certificates_status",
        }
        assert inspector.get_pk_constraint("generation_jobs")["constrained_columns"] == ["id"]
        assert inspector.get_pk_constraint("certificates")["constrained_columns"] == ["id"]
        assert inspector.get_foreign_keys("certificates")[0]["referred_table"] == "generation_jobs"
        assert {tuple(item["column_names"]) for item in inspector.get_unique_constraints("generation_jobs")} == {
            ("idempotency_key",),
        }
        assert {tuple(item["column_names"]) for item in inspector.get_unique_constraints("certificates")} == {
            ("certificate_number",),
        }
    finally:
        engine.dispose()
