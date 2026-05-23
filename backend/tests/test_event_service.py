from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db.database import (
    Base,
    get_engine,
    init_db,
    reset_database_engine_cache,
    session_scope,
)
from app.db.models import Event
from app.services import event_service
from app.services.tracking_service import TrackedObject
from app.services.detection_service import BoundingBox, DetectionResult


def configure_db(monkeypatch, tmp_path):
    db_path = tmp_path / "events.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("EVENT_ENABLED", "true")
    monkeypatch.setenv("EVENT_COOLDOWN_SECONDS", "60")
    monkeypatch.setenv("TELEGRAM_ALERTS_ENABLED", "false")
    reset_database_engine_cache()
    init_db()
    return db_path


def make_detection(class_name: str, confidence: float = 0.9) -> DetectionResult:
    return DetectionResult(
        class_name=class_name,
        confidence=confidence,
        bbox=BoundingBox(x1=1, y1=2, x2=30, y2=40),
        channel="101",
        timestamp="2026-05-23T18:00:00",
        snapshot_path="storage/snapshots/test.jpg",
    )


def make_track(class_name: str = "person", dwell_seconds: float = 0.0) -> TrackedObject:
    now = datetime.now(timezone.utc)
    return TrackedObject(
        track_id=1,
        channel="101",
        class_name=class_name,
        confidence=0.91,
        bbox=[1, 2, 30, 40],
        center=[15, 20],
        path=[[15, 20]],
        first_seen_at=now,
        last_seen_at=now,
        status="active",
        zone_ids=["cashier"],
        dwell={"cashier": dwell_seconds},
    )


def test_build_event_key() -> None:
    assert (
        event_service.build_event_key("101", "vehicle_detected")
        == "101:vehicle_detected"
    )


def test_person_detection_creates_person_event(monkeypatch, tmp_path) -> None:
    configure_db(monkeypatch, tmp_path)

    result = event_service.process_detection_result(
        channel="101",
        detections=[make_detection("person")],
        snapshot_path="snapshot.jpg",
        annotated_snapshot_path="annotated.jpg",
    )

    assert result["created_events"][0]["event_type"] == "person_detected"
    assert result["created_events"][0]["status"] == "new"


def test_vehicle_classes_create_vehicle_event(monkeypatch, tmp_path) -> None:
    configure_db(monkeypatch, tmp_path)

    for class_name in ["car", "truck", "motorcycle", "bicycle"]:
        Base.metadata.drop_all(bind=get_engine())
        init_db()
        result = event_service.process_detection_result(
            channel="101",
            detections=[make_detection(class_name)],
            snapshot_path="snapshot.jpg",
            annotated_snapshot_path="annotated.jpg",
        )
        assert result["created_events"][0]["event_type"] == "vehicle_detected"


def test_cooldown_blocks_repeated_event(monkeypatch, tmp_path) -> None:
    configure_db(monkeypatch, tmp_path)

    first = event_service.process_detection_result(
        channel="101",
        detections=[make_detection("car")],
        snapshot_path="snapshot.jpg",
        annotated_snapshot_path="annotated.jpg",
    )
    second = event_service.process_detection_result(
        channel="101",
        detections=[make_detection("car")],
        snapshot_path="snapshot.jpg",
        annotated_snapshot_path="annotated.jpg",
    )

    assert len(first["created_events"]) == 1
    assert len(second["created_events"]) == 0
    assert second["skipped_events"][0]["reason"] == "cooldown"


def test_event_created_after_cooldown(monkeypatch, tmp_path) -> None:
    configure_db(monkeypatch, tmp_path)
    old_time = datetime.now(timezone.utc) - timedelta(seconds=120)
    with session_scope() as session:
        session.add(
            Event(
                event_type="vehicle_detected",
                status="new",
                channel="101",
                source="hikvision_isapi_snapshot",
                title="Vehicle detected (1)",
                description="old",
                confidence=0.8,
                detections_json="[]",
                event_key="101:vehicle_detected",
                created_at=old_time,
                updated_at=old_time,
            )
        )

    result = event_service.process_detection_result(
        channel="101",
        detections=[make_detection("car")],
        snapshot_path="snapshot.jpg",
        annotated_snapshot_path="annotated.jpg",
    )

    assert len(result["created_events"]) == 1


def test_update_event_status(monkeypatch, tmp_path) -> None:
    configure_db(monkeypatch, tmp_path)
    event = event_service.create_event_from_detection(
        channel="101",
        event_type="person_detected",
        detections=[make_detection("person")],
        snapshot_path="snapshot.jpg",
        annotated_snapshot_path="annotated.jpg",
    )

    updated = event_service.update_event_status(event.id, "acknowledged")

    assert updated is not None
    assert updated["status"] == "acknowledged"
    assert updated["acknowledged_at"] is not None


def test_event_engine_survives_telegram_failure(monkeypatch, tmp_path) -> None:
    configure_db(monkeypatch, tmp_path)

    def fail_alert(event):
        raise RuntimeError("network failed")

    from app.services import telegram_alert_service

    monkeypatch.setattr(telegram_alert_service, "send_event_alert", fail_alert)
    result = event_service.process_detection_result(
        channel="101",
        detections=[make_detection("person")],
        snapshot_path="snapshot.jpg",
        annotated_snapshot_path="annotated.jpg",
    )

    assert result["created_events"][0]["event_type"] == "person_detected"
    assert result["created_events"][0]["telegram_alert"]["sent"] is False


def test_loitering_event_created_after_threshold(monkeypatch, tmp_path) -> None:
    configure_db(monkeypatch, tmp_path)
    monkeypatch.setenv("LOITERING_THRESHOLD_SECONDS", "1")

    result = event_service.process_tracking_result(
        channel="101",
        objects=[make_track(dwell_seconds=2.0)],
        snapshot_path="snapshot.jpg",
        annotated_snapshot_path="annotated.jpg",
        zones=[
            {
                "id": "cashier",
                "name": "Cashier",
                "type": "cashier",
                "polygon": [[0, 0], [100, 0], [100, 100], [0, 100]],
            }
        ],
    )

    created_types = {event["event_type"] for event in result["created_events"]}
    assert "person_loitering" in created_types
