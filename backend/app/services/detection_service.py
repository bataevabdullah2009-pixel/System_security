from __future__ import annotations

import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from dotenv import load_dotenv

from app.services.detection_backends.base import (
    BoundingBox,
    DetectionBackend,
    DetectionModelError,
    DetectionResult,
)
from app.services.detection_backends.camera_ai_backend import CameraAiBackend
from app.services.detection_backends.mock_backend import MockDetectionBackend
from app.services.detection_backends.ncnn_backend import NcnnBackend
from app.services.detection_backends.onnxruntime_backend import OnnxRuntimeBackend
from app.services.detection_backends.openvino_backend import OpenVinoBackend
from app.services.detection_backends.ultralytics_backend import UltralyticsYoloBackend


PROJECT_ROOT = Path(__file__).resolve().parents[3]
STORAGE_ROOT = PROJECT_ROOT / "storage"
DETECTIONS_DIR = STORAGE_ROOT / "detections"

DEFAULT_ALLOWED_CLASSES = ("person", "car", "truck", "motorcycle", "bicycle")
SUPPORTED_BACKENDS = {
    "ultralytics_yolo",
    "onnxruntime",
    "openvino",
    "ncnn",
    "camera_ai",
    "disabled",
    "mock",
}
VEHICLE_CLASSES = {"car", "truck", "motorcycle", "bicycle"}


class DisabledDetectionBackend:
    name = "disabled"

    def load(self) -> None:
        return None

    def detect(
        self,
        image_bytes: bytes,
        channel: str,
        snapshot_path: str | None = None,
    ) -> list[DetectionResult]:
        return []


def _load_env() -> None:
    load_dotenv(PROJECT_ROOT / ".env")


def detection_enabled() -> bool:
    _load_env()
    return os.getenv("DETECTION_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}


def detection_backend_name() -> str:
    _load_env()
    return os.getenv("DETECTION_BACKEND", "ultralytics_yolo").strip().lower() or "ultralytics_yolo"


def detection_model_name() -> str:
    _load_env()
    return os.getenv("DETECTION_MODEL", "yolo11n.pt").strip() or "yolo11n.pt"


def confidence_threshold() -> float:
    _load_env()
    raw = os.getenv("DETECTION_CONFIDENCE_THRESHOLD", "0.45").strip()
    try:
        return float(raw)
    except ValueError:
        return 0.45


def image_size() -> int:
    _load_env()
    raw = os.getenv("DETECTION_IMAGE_SIZE", "640").strip()
    try:
        return int(raw)
    except ValueError:
        return 640


def allowed_classes() -> set[str]:
    _load_env()
    raw = os.getenv("DETECTION_ALLOWED_CLASSES", ",".join(DEFAULT_ALLOWED_CLASSES))
    values = {item.strip() for item in raw.split(",") if item.strip()}
    return values or set(DEFAULT_ALLOWED_CLASSES)


@lru_cache(maxsize=1)
def get_detection_backend() -> DetectionBackend:
    if not detection_enabled():
        return DisabledDetectionBackend()

    backend_name = detection_backend_name()
    if backend_name == "ultralytics_yolo":
        return UltralyticsYoloBackend(
            model_name=detection_model_name,
            confidence_threshold=confidence_threshold,
            image_size=image_size,
            filter_detections=filter_detections,
        )
    if backend_name == "mock":
        return MockDetectionBackend(filter_detections=filter_detections)
    if backend_name == "onnxruntime":
        return OnnxRuntimeBackend()
    if backend_name == "openvino":
        return OpenVinoBackend()
    if backend_name == "ncnn":
        return NcnnBackend()
    if backend_name == "camera_ai":
        return CameraAiBackend()
    if backend_name == "disabled":
        return DisabledDetectionBackend()

    allowed = ", ".join(sorted(SUPPORTED_BACKENDS))
    raise DetectionModelError(
        f"Unknown detection backend {backend_name!r}. Supported backends: {allowed}"
    )


@lru_cache(maxsize=1)
def load_detection_model():
    backend = get_detection_backend()
    backend.load()
    return backend


def reset_detection_backend_cache() -> None:
    get_detection_backend.cache_clear()
    load_detection_model.cache_clear()


def _decode_image(image_bytes: bytes):
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if image is None:
        raise DetectionModelError("Could not decode snapshot image")
    return image


def detect_objects(
    image_bytes: bytes,
    channel: int | str,
    snapshot_path: str | None = None,
) -> list[DetectionResult]:
    backend = get_detection_backend()
    return backend.detect(image_bytes=image_bytes, channel=str(channel), snapshot_path=snapshot_path)


def filter_detections(results: list[DetectionResult]) -> list[DetectionResult]:
    allowed = allowed_classes()
    threshold = confidence_threshold()
    return [
        detection
        for detection in results
        if detection.class_name in allowed and detection.confidence >= threshold
    ]


def draw_detections(image_bytes: bytes, detections: list[DetectionResult]) -> bytes:
    image = _decode_image(image_bytes)
    for detection in detections:
        bbox = detection.bbox
        color = (0, 180, 0) if detection.class_name == "person" else (255, 130, 0)
        cv2.rectangle(image, (bbox.x1, bbox.y1), (bbox.x2, bbox.y2), color, 2)
        label = f"{detection.class_name} {detection.confidence:.2f}"
        cv2.putText(
            image,
            label,
            (bbox.x1, max(20, bbox.y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
            cv2.LINE_AA,
        )

    ok, encoded = cv2.imencode(".jpg", image)
    if not ok:
        raise DetectionModelError("Could not encode annotated JPEG")
    return encoded.tobytes()


def save_annotated_snapshot(
    channel: int | str,
    image_bytes: bytes,
    detections: list[DetectionResult],
) -> Path:
    annotated_bytes = draw_detections(image_bytes, detections)
    DETECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = DETECTIONS_DIR / f"hikvision_ch{channel}_detections_{timestamp}.jpg"
    path.write_bytes(annotated_bytes)
    return path
