import sys

from app.services import detection_service
from app.services.detection_service import BoundingBox, DetectionResult


def make_detection(class_name: str, confidence: float) -> DetectionResult:
    return DetectionResult(
        class_name=class_name,
        confidence=confidence,
        bbox=BoundingBox(x1=10, y1=20, x2=100, y2=200),
        channel="101",
        timestamp="2026-05-23T18:00:00",
    )


def test_filter_detections_keeps_allowed_classes(monkeypatch) -> None:
    monkeypatch.setenv("DETECTION_ALLOWED_CLASSES", "person,car")
    monkeypatch.setenv("DETECTION_CONFIDENCE_THRESHOLD", "0.45")

    results = detection_service.filter_detections(
        [
            make_detection("person", 0.9),
            make_detection("car", 0.8),
            make_detection("dog", 0.99),
        ]
    )

    assert [result.class_name for result in results] == ["person", "car"]


def test_filter_detections_applies_confidence_threshold(monkeypatch) -> None:
    monkeypatch.setenv("DETECTION_ALLOWED_CLASSES", "person,car")
    monkeypatch.setenv("DETECTION_CONFIDENCE_THRESHOLD", "0.7")

    results = detection_service.filter_detections(
        [
            make_detection("person", 0.69),
            make_detection("car", 0.7),
        ]
    )

    assert [result.class_name for result in results] == ["car"]


def test_detection_result_bbox_format() -> None:
    result = make_detection("person", 0.95).to_api_dict()

    assert result["bbox"] == {"x1": 10, "y1": 20, "x2": 100, "y2": 200}
    assert result["channel"] == "101"


def test_load_detection_model_missing_ultralytics_is_clear(monkeypatch) -> None:
    detection_service.reset_detection_backend_cache()
    monkeypatch.setenv("DETECTION_ENABLED", "true")
    monkeypatch.setenv("DETECTION_BACKEND", "ultralytics_yolo")
    monkeypatch.setitem(sys.modules, "ultralytics", None)

    try:
        detection_service.load_detection_model()
    except detection_service.DetectionModelError as exc:
        assert "Ultralytics YOLO is not installed" in str(exc)
    else:
        raise AssertionError("Expected DetectionModelError")
    finally:
        detection_service.reset_detection_backend_cache()


def test_mock_backend_returns_detections(monkeypatch) -> None:
    monkeypatch.setenv("DETECTION_ENABLED", "true")
    monkeypatch.setenv("DETECTION_BACKEND", "mock")
    monkeypatch.setenv("DETECTION_ALLOWED_CLASSES", "person,car")
    monkeypatch.setenv("DETECTION_CONFIDENCE_THRESHOLD", "0.45")
    detection_service.reset_detection_backend_cache()

    results = detection_service.detect_objects(b"not-used-by-mock", channel="101")

    assert [result.class_name for result in results] == ["person", "car"]
    assert all(result.channel == "101" for result in results)
    detection_service.reset_detection_backend_cache()


def test_unknown_backend_returns_clear_error(monkeypatch) -> None:
    monkeypatch.setenv("DETECTION_ENABLED", "true")
    monkeypatch.setenv("DETECTION_BACKEND", "quantum_detector")
    detection_service.reset_detection_backend_cache()

    try:
        detection_service.detect_objects(b"not-used", channel="101")
    except detection_service.DetectionModelError as exc:
        assert "Unknown detection backend 'quantum_detector'" in str(exc)
        assert "Supported backends" in str(exc)
    else:
        raise AssertionError("Expected DetectionModelError")
    finally:
        detection_service.reset_detection_backend_cache()
