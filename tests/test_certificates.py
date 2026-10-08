def test_missing_certificate_returns_404(client):
    response = client.get("/api/v1/certificates/does-not-exist")
    assert response.status_code == 404


def test_certificate_verification_endpoint(client):
    payload = {
        "event_name": "Advanced Python Workshop",
        "certificate_title": "Certificate of Completion",
        "completion_date": "2026-10-07",
        "recipients": [{"name": "Alice Example", "email": "alice@example.com"}],
    }
    response = client.post("/api/v1/generation-jobs", json=payload)
    job_id = response.json()["job_id"]
    import time

    for _ in range(200):
        job = client.get(f"/api/v1/generation-jobs/{job_id}")
        if job.json()["status"] in {"COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"}:
            break
        time.sleep(0.1)
    cert = client.get(f"/api/v1/generation-jobs/{job_id}/certificates").json()["certificates"][0]
    verify = client.get(f"/api/v1/certificates/verify/{cert['certificate_number']}")
    assert verify.status_code == 200
    assert verify.json()["valid"] is True
