from __future__ import annotations

from app.db.database import init_db, reset_database_engine_cache
from app.services import event_service, telegram_alert_service


def configure_db(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "telegram_service.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("EVENT_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_ALERTS_ENABLED", "false")
    reset_database_engine_cache()
    init_db()


def test_telegram_disabled_does_not_send(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_ALERTS_ENABLED", "false")

    result = telegram_alert_service.send_event_alert(
        {
            "id": 1,
            "event_type": "person_detected",
            "channel": "101",
            "title": "Person detected (1)",
            "confidence": 0.91,
            "created_at": "2026-05-23T18:00:00",
        }
    )

    assert result == {"sent": False, "reason": "telegram_disabled"}


def test_mask_token() -> None:
    assert telegram_alert_service.mask_token("123456:abcdef") == "123456:***"
    assert telegram_alert_service.mask_token("abcdefghi") == "abcdef***"
    assert telegram_alert_service.mask_token("CHANGE_ME") == ""


def test_build_event_message_contains_key_fields() -> None:
    message = telegram_alert_service.build_event_message(
        {
            "id": 7,
            "event_type": "vehicle_detected",
            "channel": "101",
            "title": "Vehicle detected (1)",
            "confidence": 0.88,
            "created_at": "2026-05-23T18:00:00",
        }
    )

    assert "event_id: 7" in message
    assert "event_type: vehicle_detected" in message
    assert "channel: 101" in message


def test_callback_data_updates_event_status(monkeypatch, tmp_path) -> None:
    configure_db(monkeypatch, tmp_path)
    event = event_service.create_event_from_detection(
        channel="101",
        event_type="person_detected",
        detections=[],
        snapshot_path="snapshot.jpg",
        annotated_snapshot_path="annotated.jpg",
    )

    result = telegram_alert_service.handle_callback_update(f"event:{event.id}:acknowledged")

    assert result["ok"] is True
    assert result["event"]["status"] == "acknowledged"


def test_build_event_keyboard_callback_data() -> None:
    keyboard = telegram_alert_service.build_event_keyboard(1)
    buttons = keyboard["inline_keyboard"][0]

    assert buttons[0]["callback_data"] == "event:1:acknowledged"
    assert buttons[1]["callback_data"] == "event:1:ignored"
    assert buttons[2]["callback_data"] == "event:1:resolved"


def test_telegram_error_does_not_expose_token(monkeypatch) -> None:
    token = "123456:secret-token"
    monkeypatch.setenv("TELEGRAM_ALERTS_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", token)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")

    def fail_text(*args, **kwargs):
        raise RuntimeError(f"https://api.telegram.org/bot{token}/sendMessage failed")

    monkeypatch.setattr(telegram_alert_service, "send_text_message", fail_text)
    result = telegram_alert_service.send_event_alert(
        {
            "id": 10,
            "event_type": "person_detected",
            "channel": "101",
            "title": "Person detected (1)",
            "confidence": 0.9,
            "created_at": "2026-05-23T18:00:00",
            "annotated_snapshot_path": None,
        }
    )

    assert result["sent"] is False
    assert token not in result["reason"]
    assert "123456:***" in result["reason"]
