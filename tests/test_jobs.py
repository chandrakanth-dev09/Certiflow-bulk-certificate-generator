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


def test_create_job_returns_accepted_status(client):
    response = client.post("/api/v1/generation-jobs", json=_payload())
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "PENDING"
    assert data["total_count"] == 2
    assert data["job_id"]


def test_idempotency_key_reuses_existing_job(client):
    payload = _payload()
    headers = {"Idempotency-Key": "workshop-2026-batch-001"}
    first = client.post("/api/v1/generation-jobs", json=payload, headers=headers)
    second = client.post("/api/v1/generation-jobs", json=payload, headers=headers)
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["job_id"] == second.json()["job_id"]


def test_idempotency_conflict_for_changed_payload(client):
    first = client.post(
        "/api/v1/generation-jobs",
        json=_payload(),
        headers={"Idempotency-Key": "workshop-conflict"},
    )
    assert first.status_code == 202
    second = client.post(
        "/api/v1/generation-jobs",
        json={**_payload(), "recipients": [{"name": "Charlie", "email": "charlie@example.com"}]},
        headers={"Idempotency-Key": "workshop-conflict"},
    )
    assert second.status_code == 409
