import time


def _payload():
    return {
        "event_name": "Advanced Python Workshop",
        "certificate_title": "Certificate of Completion",
        "completion_date": "2026-10-07",
        "recipients": [
            {"name": "Alice Example", "email": "alice@example.com"},
            {"name": "Bob Example", "email": "bob@example.com"},
        ],
    }


def _wait_for_completion(client, job_id, timeout_seconds=15):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get(f"/api/v1/generation-jobs/{job_id}")
        if response.status_code == 200:
            status = response.json()["status"]
            if status in {"COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"}:
                return response.json()
        time.sleep(0.1)
    raise AssertionError("timed out waiting for job completion")


def test_certificate_generation_creates_pdf_and_tracks_status(client):
    response = client.post("/api/v1/generation-jobs", json=_payload())
    job_id = response.json()["job_id"]
    job = _wait_for_completion(client, job_id)
    assert job["status"] == "COMPLETED"
    certs = client.get(f"/api/v1/generation-jobs/{job_id}/certificates")
    assert certs.status_code == 200
    certificates = certs.json()["certificates"]
    assert len(certificates) == 2
    cert_id = certificates[0]["id"]
    pdf = client.get(f"/api/v1/certificates/{cert_id}")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content.startswith(b"%PDF")
