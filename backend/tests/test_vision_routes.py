from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.db.database import init_db, reset_database_engine_cache
from app.main import app
from app.services import camera_service, detection_service, vision_loop_service
from app.services.detection_service import BoundingBox, DetectionResult


def jpeg_bytes() -> bytes:
    image = np.zeros((120, 160, 3), dtype=np.uint8)
    image[:] = (40, 40, 40)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    return encoded.tobytes()


def fake_detection() -> DetectionResult:
    return DetectionResult(
        class_name="person",
        confidence=0.91,
        bbox=BoundingBox(x1=10, y1=10, x2=70, y2=90),
        channel="101",
        timestamp="2026-05-23T18:00:00",
        snapshot_path="storage/snapshots/test.jpg",
    )


def setup_function() -> None:
    vision_loop_service.reset_vision_state()


def configure_db(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "vision_events.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("EVENT_ENABLED", "true")
    monkeypatch.setenv("EVENT_COOLDOWN_SECONDS", "60")
    monkeypatch.setenv("TELEGRAM_ALERTS_ENABLED", "false")
    reset_database_engine_cache()
    init_db()


def test_vision_state_route_works() -> None:
    client = TestClient(app)

    response = client.get("/api/vision/hikvision/101/state")

    assert response.status_code == 200
    assert response.json()["channel"] == "101"
    assert response.json()["objects"] == []


def test_vision_update_works_with_mock_detection(monkeypatch, tmp_path) -> None:
    configure_db(monkeypatch, tmp_path)
    image_bytes = jpeg_bytes()
    snapshot_path = tmp_path / "snapshot.jpg"
    latest_path = tmp_path / "latest.jpg"

    monkeypatch.setattr(
        camera_service,
        "capture_fresh_snapshot",
        lambda channel: (image_bytes, snapshot_path, latest_path),
    )
    monkeypatch.setattr(
        detection_service,
        "detect_objects",
        lambda image_bytes, channel, snapshot_path=None: [fake_detection()],
    )

    client = TestClient(app)
    response = client.post("/api/vision/hikvision/101/update")

    assert response.status_code == 200
    body = response.json()
    assert body["objects"][0]["track_id"] == 1
    assert body["objects"][0]["zone_ids"] == ["entrance"]


def test_vision_annotated_endpoint_returns_jpeg(monkeypatch, tmp_path) -> None:
    configure_db(monkeypatch, tmp_path)
    image_bytes = jpeg_bytes()
    snapshot_path = tmp_path / "snapshot.jpg"
    latest_path = tmp_path / "latest.jpg"

    monkeypatch.setattr(
        camera_service,
        "capture_fresh_snapshot",
        lambda channel: (image_bytes, snapshot_path, latest_path),
    )
    monkeypatch.setattr(
        detection_service,
        "detect_objects",
        lambda image_bytes, channel, snapshot_path=None: [fake_detection()],
    )

    client = TestClient(app)
    response = client.get("/api/vision/hikvision/101/annotated")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content.startswith(b"\xff\xd8")
