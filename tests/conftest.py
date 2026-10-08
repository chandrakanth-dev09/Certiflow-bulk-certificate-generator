import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "certiflow.db"
    storage_dir = tmp_path / "storage" / "certificates"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("STORAGE_DIR", str(storage_dir))
    monkeypatch.setenv("ENVIRONMENT", "testing")

    import app.core.config as config
    import app.core.database as database
    import app.main as app_main

    monkeypatch.setattr(config.settings, "STORAGE_DIR", str(storage_dir))
    monkeypatch.setattr(config.settings, "ENVIRONMENT", "testing")
    test_engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False}, future=True)
    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(
        database,
        "SessionLocal",
        sessionmaker(autocommit=False, autoflush=False, bind=test_engine, future=True),
    )
    database.Base.metadata.drop_all(bind=test_engine)
    database.Base.metadata.create_all(bind=test_engine)

    from app.workers.certificate_worker import generate_certificate_job

    def enqueue_test_task(job_id: str) -> None:
        generate_certificate_job.run(job_id)

    monkeypatch.setattr(generate_certificate_job, "delay", enqueue_test_task)

    with TestClient(app_main.app) as test_client:
        yield test_client
