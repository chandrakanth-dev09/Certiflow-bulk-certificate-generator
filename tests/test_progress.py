import time


def test_job_progress_updates_after_generation(client):
    payload = {
        "event_name": "Advanced Python Workshop",
        "certificate_title": "Certificate of Completion",
        "completion_date": "2026-10-07",
        "recipients": [{"name": "Alice Example", "email": "alice@example.com"}, {"name": "Bob Example", "email": "bob@example.com"}],
    }
    response = client.post("/api/v1/generation-jobs", json=payload)
    job_id = response.json()["job_id"]
    deadline = time.time() + 15
    while time.time() < deadline:
        res = client.get(f"/api/v1/generation-jobs/{job_id}")
        if res.status_code == 200 and res.json()["status"] == "COMPLETED":
            break
        time.sleep(0.1)
    status = client.get(f"/api/v1/generation-jobs/{job_id}").json()
    assert status["progress"]["total"] == 2
    assert status["progress"]["completed"] >= 1
    assert status["progress"]["percentage"] >= 0
