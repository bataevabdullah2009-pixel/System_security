from __future__ import annotations

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.db.database import init_db, reset_database_engine_cache, session_scope
from app.db.models import VisionTrack, VisionTrackPoint
from app.main import app
from app.services import (
    camera_service,
    detection_service,
    vision_loop_service,
    vision_worker_service,
    zone_service,
)
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
    vision_worker_service.reset_worker_state()


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
    assert "dwell" in body["objects"][0]
    assert body["worker"]["running"] is False


def test_vision_update_persists_live_state(monkeypatch, tmp_path) -> None:
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
    with session_scope() as session:
        assert session.query(VisionTrack).count() == 1
        assert session.query(VisionTrackPoint).count() == 1


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


def test_vision_worker_routes(monkeypatch) -> None:
    monkeypatch.setenv("VISION_WORKER_INTERVAL_SECONDS", "0.1")
    monkeypatch.setattr(
        vision_loop_service,
        "update_once",
        lambda channel: {"channel": str(channel), "objects": []},
    )

    client = TestClient(app)
    started = client.post("/api/vision/hikvision/101/worker/start")
    status = client.get("/api/vision/hikvision/101/worker/status")
    stopped = client.post("/api/vision/hikvision/101/worker/stop")

    assert started.status_code == 200
    assert status.status_code == 200
    assert stopped.status_code == 200
    assert started.json()["running"] is True
    assert "updates_count" in status.json()
    assert stopped.json()["running"] is False


def test_restricted_zone_event_is_created(monkeypatch, tmp_path) -> None:
    configure_db(monkeypatch, tmp_path)
    image_bytes = jpeg_bytes()
    snapshot_path = tmp_path / "snapshot.jpg"
    latest_path = tmp_path / "latest.jpg"
    zones_path = tmp_path / "zones.json"
    zones_path.write_text(
        """
        {
          "101": [
            {
              "id": "restricted",
              "name": "Restricted zone",
              "type": "restricted",
              "polygon": [[0, 0], [120, 0], [120, 120], [0, 120]]
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    monkeypatch.setattr(zone_service, "ZONES_CONFIG_PATH", zones_path)
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
    created_types = {
        event["event_type"] for event in response.json()["events"]["created_events"]
    }
    assert "person_entered_restricted_zone" in created_types
