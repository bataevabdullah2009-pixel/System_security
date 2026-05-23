from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.db.database import init_db, reset_database_engine_cache
from app.main import app
from app.services import camera_service, detection_service, event_service


def configure_db(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "events_routes.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("EVENT_ENABLED", "true")
    monkeypatch.setenv("EVENT_COOLDOWN_SECONDS", "60")
    reset_database_engine_cache()
    init_db()


def jpeg_bytes() -> bytes:
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    image[:] = (20, 120, 20)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    return encoded.tobytes()


def test_events_list_get_and_status_update(monkeypatch, tmp_path) -> None:
    configure_db(monkeypatch, tmp_path)
    event = event_service.create_event_from_detection(
        channel="101",
        event_type="person_detected",
        detections=[],
        snapshot_path="snapshot.jpg",
        annotated_snapshot_path="annotated.jpg",
    )

    client = TestClient(app)
    list_response = client.get("/api/events")
    get_response = client.get(f"/api/events/{event.id}")
    patch_response = client.patch(
        f"/api/events/{event.id}/status",
        json={"status": "acknowledged"},
    )

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == event.id
    assert get_response.status_code == 200
    assert get_response.json()["event_type"] == "person_detected"
    assert patch_response.status_code == 200
    assert patch_response.json()["status"] == "acknowledged"


def test_process_hikvision_channel_with_mock_backend(monkeypatch, tmp_path) -> None:
    configure_db(monkeypatch, tmp_path)
    image_bytes = jpeg_bytes()
    snapshot_path = tmp_path / "snapshot.jpg"
    latest_path = tmp_path / "latest.jpg"
    annotated_path = tmp_path / "annotated.jpg"

    monkeypatch.setenv("DETECTION_ENABLED", "true")
    monkeypatch.setenv("DETECTION_BACKEND", "mock")
    monkeypatch.setenv("DETECTION_ALLOWED_CLASSES", "person,car")
    monkeypatch.setenv("DETECTION_CONFIDENCE_THRESHOLD", "0.45")
    detection_service.reset_detection_backend_cache()
    monkeypatch.setattr(
        camera_service,
        "capture_fresh_snapshot",
        lambda channel: (image_bytes, snapshot_path, latest_path),
    )
    monkeypatch.setattr(
        detection_service,
        "save_annotated_snapshot",
        lambda channel, image_bytes, detections: annotated_path,
    )

    client = TestClient(app)
    response = client.post("/api/events/process/hikvision/101")

    assert response.status_code == 200
    body = response.json()
    assert body["channel"] == "101"
    assert [event["event_type"] for event in body["created_events"]] == [
        "person_detected",
        "vehicle_detected",
    ]
    assert len(body["detections"]) == 2
    detection_service.reset_detection_backend_cache()


def test_events_diagnose_hikvision(monkeypatch, tmp_path) -> None:
    configure_db(monkeypatch, tmp_path)
    image_bytes = jpeg_bytes()
    snapshot_path = tmp_path / "snapshot.jpg"
    latest_path = tmp_path / "latest.jpg"

    monkeypatch.setenv("DETECTION_ENABLED", "true")
    monkeypatch.setenv("DETECTION_BACKEND", "mock")
    detection_service.reset_detection_backend_cache()
    monkeypatch.setattr(
        camera_service,
        "capture_fresh_snapshot",
        lambda channel: (image_bytes, snapshot_path, latest_path),
    )
    monkeypatch.setattr(
        detection_service,
        "save_annotated_snapshot",
        lambda channel, image_bytes, detections: Path("storage/detections/test.jpg"),
    )

    client = TestClient(app)
    response = client.get("/api/events/diagnose/hikvision")

    assert response.status_code == 200
    assert response.json()[0]["channel"] == "101"
    detection_service.reset_detection_backend_cache()
