from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.database import init_db, reset_database_engine_cache
from app.main import app
from app.services import event_service


def configure_db(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "telegram_webhook.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("EVENT_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_ALERTS_ENABLED", "false")
    reset_database_engine_cache()
    init_db()


def test_webhook_ignores_update_without_callback() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/telegram/webhook", json={"update_id": 1, "message": {"text": "hi"}}
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "ignored": True}


def test_webhook_callback_updates_event_status(monkeypatch, tmp_path) -> None:
    configure_db(monkeypatch, tmp_path)
    event = event_service.create_event_from_detection(
        channel="101",
        event_type="person_detected",
        detections=[],
        snapshot_path="snapshot.jpg",
        annotated_snapshot_path="annotated.jpg",
    )

    client = TestClient(app)
    response = client.post(
        "/api/telegram/webhook",
        json={
            "update_id": 2,
            "callback_query": {
                "id": "callback-1",
                "data": f"event:{event.id}:acknowledged",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["event"]["status"] == "acknowledged"
    assert body["answer_callback_query"] == {
        "sent": False,
        "reason": "telegram_disabled",
    }


def test_webhook_invalid_callback_returns_clear_error() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/telegram/webhook",
        json={
            "update_id": 3,
            "callback_query": {
                "id": "callback-2",
                "data": "bad-data",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["reason"] == "invalid_callback_data"
    assert body["answer_callback_query"]["reason"] == "telegram_disabled"
