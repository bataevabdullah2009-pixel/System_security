from __future__ import annotations

from datetime import datetime
from typing import Callable

from app.services.detection_backends.base import BoundingBox, DetectionResult


class MockDetectionBackend:
    name = "mock"

    def __init__(
        self,
        filter_detections: Callable[[list[DetectionResult]], list[DetectionResult]],
    ) -> None:
        self._filter_detections = filter_detections

    def load(self) -> None:
        return None

    def detect(
        self,
        image_bytes: bytes,
        channel: str,
        snapshot_path: str | None = None,
    ) -> list[DetectionResult]:
        timestamp = datetime.now().isoformat(timespec="seconds")
        detections = [
            DetectionResult(
                class_name="person",
                confidence=0.91,
                bbox=BoundingBox(x1=20, y1=20, x2=120, y2=220),
                channel=str(channel),
                timestamp=timestamp,
                snapshot_path=snapshot_path,
            ),
            DetectionResult(
                class_name="car",
                confidence=0.88,
                bbox=BoundingBox(x1=150, y1=80, x2=360, y2=220),
                channel=str(channel),
                timestamp=timestamp,
                snapshot_path=snapshot_path,
            ),
        ]
        return self._filter_detections(detections)
