import time


def _payload(**overrides):
    payload = {
        "event_name": "Advanced Python Workshop",
        "certificate_title": "Certificate of Completion",
        "completion_date": "2026-10-07",
        "recipients": [
            {"name": "Alice Example", "email": "alice@example.com"},
            {"name": "Bob Example", "email": "bob@example.com"},
        ],
    }
    payload.update(overrides)
    return payload


def test_invalid_recipient_data(client):
    response = client.post("/api/v1/generation-jobs", json=_payload(recipients=[{"name": "", "email": "not-an-email"}]))
    assert response.status_code == 422
    assert "error" in response.json()


def test_empty_recipient_list(client):
    response = client.post("/api/v1/generation-jobs", json=_payload(recipients=[]))
    assert response.status_code == 422


def test_duplicate_recipients_are_rejected(client):
    response = client.post(
        "/api/v1/generation-jobs",
        json=_payload(recipients=[{"name": "Alice", "email": "duplicate@example.com"}, {"name": "Alice 2", "email": "duplicate@example.com"}]),
    )
    assert response.status_code == 422
