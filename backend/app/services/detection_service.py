from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]
STORAGE_ROOT = PROJECT_ROOT / "storage"
DETECTIONS_DIR = STORAGE_ROOT / "detections"

DEFAULT_ALLOWED_CLASSES = ("person", "car", "truck", "motorcycle", "bicycle")
VEHICLE_CLASSES = {"car", "truck", "motorcycle", "bicycle"}


class DetectionModelError(RuntimeError):
    pass


@dataclass(frozen=True)
class BoundingBox:
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass(frozen=True)
class DetectionResult:
    class_name: str
    confidence: float
    bbox: BoundingBox
    channel: str
    timestamp: str
    snapshot_path: str | None = None
    annotated_snapshot_path: str | None = None

    def to_api_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["confidence"] = round(float(self.confidence), 4)
        return data


def _load_env() -> None:
    load_dotenv(PROJECT_ROOT / ".env")


def detection_enabled() -> bool:
    _load_env()
    return os.getenv("DETECTION_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}


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
def load_detection_model():
    if not detection_enabled():
        raise DetectionModelError("Object detection is disabled by DETECTION_ENABLED=false")

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise DetectionModelError(
            "Ultralytics YOLO is not installed. Run: pip install -r backend/requirements.txt"
        ) from exc

    model_name = detection_model_name()
    try:
        return YOLO(model_name)
    except Exception as exc:
        raise DetectionModelError(f"Could not load detection model {model_name!r}: {exc}") from exc


def _decode_image(image_bytes: bytes):
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if image is None:
        raise DetectionModelError("Could not decode snapshot image")
    return image


def _result_class_name(model, class_id: int) -> str:
    names = getattr(model, "names", {}) or {}
    if isinstance(names, dict):
        return str(names.get(class_id, class_id))
    if isinstance(names, list) and 0 <= class_id < len(names):
        return str(names[class_id])
    return str(class_id)


def detect_objects(
    image_bytes: bytes,
    channel: int | str,
    snapshot_path: str | None = None,
) -> list[DetectionResult]:
    image = _decode_image(image_bytes)
    model = load_detection_model()
    timestamp = datetime.now().isoformat(timespec="seconds")

    try:
        raw_results = model.predict(
            source=image,
            imgsz=image_size(),
            conf=confidence_threshold(),
            verbose=False,
        )
    except Exception as exc:
        raise DetectionModelError(f"Object detection inference failed: {exc}") from exc

    detections: list[DetectionResult] = []
    for result in raw_results:
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            continue

        for box in boxes:
            class_id = int(box.cls[0].item())
            confidence = float(box.conf[0].item())
            x1, y1, x2, y2 = [int(round(value)) for value in box.xyxy[0].tolist()]
            detections.append(
                DetectionResult(
                    class_name=_result_class_name(model, class_id),
                    confidence=confidence,
                    bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                    channel=str(channel),
                    timestamp=timestamp,
                    snapshot_path=snapshot_path,
                )
            )

    return filter_detections(detections)


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
