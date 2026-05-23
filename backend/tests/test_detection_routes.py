from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.services import camera_service, detection_service
from app.services.detection_service import BoundingBox, DetectionResult


def jpeg_bytes() -> bytes:
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    image[:] = (20, 120, 20)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    return encoded.tobytes()


def fake_detection() -> DetectionResult:
    return DetectionResult(
        class_name="person",
        confidence=0.91,
        bbox=BoundingBox(x1=1, y1=2, x2=30, y2=40),
        channel="101",
        timestamp="2026-05-23T18:00:00",
        snapshot_path="storage/snapshots/test.jpg",
    )


def test_detection_api_route_exists(monkeypatch, tmp_path) -> None:
    image_bytes = jpeg_bytes()
    snapshot_path = tmp_path / "snapshot.jpg"
    latest_path = tmp_path / "latest.jpg"
    annotated_path = tmp_path / "annotated.jpg"

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
    monkeypatch.setattr(
        detection_service,
        "save_annotated_snapshot",
        lambda channel, image_bytes, detections: annotated_path,
    )

    client = TestClient(app)
    response = client.get("/api/detection/hikvision/101")

    assert response.status_code == 200
    body = response.json()
    assert body["channel"] == "101"
    assert body["detections"][0]["class_name"] == "person"
    assert body["detections"][0]["bbox"] == {"x1": 1, "y1": 2, "x2": 30, "y2": 40}


def test_detection_annotated_route_returns_jpeg(monkeypatch, tmp_path) -> None:
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
    monkeypatch.setattr(detection_service, "draw_detections", lambda image_bytes, detections: image_bytes)
    monkeypatch.setattr(
        detection_service,
        "save_annotated_snapshot",
        lambda channel, image_bytes, detections: Path("storage/detections/test.jpg"),
    )

    client = TestClient(app)
    response = client.get("/api/detection/hikvision/101/annotated")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"


def test_detection_model_error_returns_503(monkeypatch, tmp_path) -> None:
    image_bytes = jpeg_bytes()
    snapshot_path = tmp_path / "snapshot.jpg"
    latest_path = tmp_path / "latest.jpg"

    monkeypatch.setattr(
        camera_service,
        "capture_fresh_snapshot",
        lambda channel: (image_bytes, snapshot_path, latest_path),
    )

    def raise_model_error(*args, **kwargs):
        raise detection_service.DetectionModelError("model missing")

    monkeypatch.setattr(detection_service, "detect_objects", raise_model_error)

    client = TestClient(app)
    response = client.get("/api/detection/hikvision/101")

    assert response.status_code == 503
    assert response.json()["detail"] == "model missing"


def test_camera_endpoints_still_exist(monkeypatch) -> None:
    monkeypatch.setattr(
        camera_service,
        "diagnose_all_channels",
        lambda: [
            {
                "channel": 101,
                "status": "online",
                "source_type": "hikvision_isapi_snapshot",
                "snapshot_path": "storage/snapshots/test.jpg",
                "error": None,
            }
        ],
    )

    client = TestClient(app)
    response = client.get("/api/cameras/hikvision/diagnose")

    assert response.status_code == 200
    assert response.json()[0]["status"] == "online"
