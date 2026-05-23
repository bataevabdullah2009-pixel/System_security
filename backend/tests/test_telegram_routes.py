from __future__ import annotations

from fastapi.testclient import TestClient

from app.db.database import init_db, reset_database_engine_cache
from app.main import app
from app.services import event_service, telegram_alert_service


def configure_db(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "telegram_routes.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("EVENT_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_ALERTS_ENABLED", "false")
    reset_database_engine_cache()
    init_db()


def test_telegram_diagnose(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_ALERTS_ENABLED", "false")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:abcdef")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")

    client = TestClient(app)
    response = client.get("/api/telegram/diagnose")

    assert response.status_code == 200
    assert response.json() == {
        "enabled": False,
        "bot_configured": True,
        "chat_configured": True,
        "token_masked": "123456:***",
        "webhook_supported": True,
        "callback_endpoint": "/api/telegram/webhook",
    }


def test_telegram_test_disabled(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_ALERTS_ENABLED", "false")

    client = TestClient(app)
    response = client.post("/api/telegram/test")

    assert response.status_code == 200
    assert response.json() == {"sent": False, "reason": "telegram_disabled"}


def test_telegram_test_enabled_uses_mocked_sender(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_ALERTS_ENABLED", "true")
    monkeypatch.setattr(
        telegram_alert_service,
        "send_text_message",
        lambda text: {"sent": True, "reason": None, "text": text},
    )

    client = TestClient(app)
    response = client.post("/api/telegram/test")

    assert response.status_code == 200
    assert response.json()["sent"] is True


def test_telegram_callback_route_updates_status(monkeypatch, tmp_path) -> None:
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
        "/api/telegram/callback",
        json={"callback_data": f"event:{event.id}:ignored"},
    )

    assert response.status_code == 200
    assert response.json()["event"]["status"] == "ignored"
