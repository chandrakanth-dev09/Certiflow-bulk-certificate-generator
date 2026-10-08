import io
import time
import zipfile


def test_failure_isolation_keeps_successful_certificates_running(client):
    payload = {
        "event_name": "Advanced Python Workshop",
        "certificate_title": "Certificate of Completion",
        "completion_date": "2026-10-07",
        "recipients": [
            {"name": "Alice Example", "email": "alice@example.com"},
            {"name": "Failure Tester", "email": "failure.test@example.com"},
            {"name": "Charlie Example", "email": "charlie@example.com"},
        ],
    }
    response = client.post("/api/v1/generation-jobs", json=payload)
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    deadline = time.time() + 15
    while time.time() < deadline:
        result = client.get(f"/api/v1/generation-jobs/{job_id}")
        if result.status_code == 200 and result.json()["status"] in {"COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"}:
            break
        time.sleep(0.1)
    job = client.get(f"/api/v1/generation-jobs/{job_id}").json()
    assert job["status"] in {"COMPLETED_WITH_ERRORS", "FAILED", "COMPLETED"}
    certs = client.get(f"/api/v1/generation-jobs/{job_id}/certificates").json()["certificates"]
    statuses = {cert["recipient_email"]: cert["status"] for cert in certs}
    assert statuses["alice@example.com"] == "COMPLETED"
    assert statuses["charlie@example.com"] == "COMPLETED"
    assert statuses["failure.test@example.com"] == "FAILED"


def test_five_certificate_failure_isolation_continues_after_third_failure(client):
    payload = {
        "event_name": "Five Certificate Isolation",
        "certificate_title": "Certificate of Completion",
        "completion_date": "2026-10-07",
        "recipients": [
            {"name": "Certificate 1", "email": "one@example.com"},
            {"name": "Certificate 2", "email": "two@example.com"},
            {"name": "Certificate 3", "email": "failure.test@example.com"},
            {"name": "Certificate 4", "email": "four@example.com"},
            {"name": "Certificate 5", "email": "five@example.com"},
        ],
    }

    response = client.post("/api/v1/generation-jobs", json=payload)
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    job = client.get(f"/api/v1/generation-jobs/{job_id}").json()
    certificates = client.get(f"/api/v1/generation-jobs/{job_id}/certificates").json()["certificates"]

    assert job["status"] == "COMPLETED_WITH_ERRORS"
    assert [certificate["status"] for certificate in certificates] == [
        "COMPLETED",
        "COMPLETED",
        "FAILED",
        "COMPLETED",
        "COMPLETED",
    ]


def test_completed_certificates_from_error_job_are_downloadable_as_zip(client):
    payload = {
        "event_name": "Partial ZIP",
        "certificate_title": "Certificate of Completion",
        "completion_date": "2026-10-07",
        "recipients": [
            {"name": "Included", "email": "zip-included@example.com"},
            {"name": "Failed", "email": "failure.test@example.com"},
        ],
    }
    created = client.post("/api/v1/generation-jobs", json=payload)
    job_id = created.json()["job_id"]

    response = client.get(f"/api/v1/generation-jobs/{job_id}/download")

    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = archive.namelist()
        assert len(names) == 1
        assert names[0].startswith("certificates/")
        assert all(not name.startswith("/") for name in names)
