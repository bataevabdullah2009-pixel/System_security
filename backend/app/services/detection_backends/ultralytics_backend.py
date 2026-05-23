from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from typing import Callable

import cv2
import numpy as np

from app.services.detection_backends.base import (
    BoundingBox,
    DetectionModelError,
    DetectionResult,
)


class UltralyticsYoloBackend:
    name = "ultralytics_yolo"

    def __init__(
        self,
        model_name: Callable[[], str],
        confidence_threshold: Callable[[], float],
        image_size: Callable[[], int],
        filter_detections: Callable[[list[DetectionResult]], list[DetectionResult]],
    ) -> None:
        self._model_name = model_name
        self._confidence_threshold = confidence_threshold
        self._image_size = image_size
        self._filter_detections = filter_detections

    def load(self) -> None:
        self._load_model()

    @lru_cache(maxsize=1)
    def _load_model(self):
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise DetectionModelError(
                "Ultralytics YOLO is not installed. "
                "Run: pip install -r backend/requirements-ai-dev.txt"
            ) from exc

        model_name = self._model_name()
        try:
            return YOLO(model_name)
        except Exception as exc:
            raise DetectionModelError(
                f"Could not load detection model {model_name!r}: {exc}"
            ) from exc

    def detect(
        self,
        image_bytes: bytes,
        channel: str,
        snapshot_path: str | None = None,
    ) -> list[DetectionResult]:
        image = self._decode_image(image_bytes)
        model = self._load_model()
        timestamp = datetime.now().isoformat(timespec="seconds")

        try:
            raw_results = model.predict(
                source=image,
                imgsz=self._image_size(),
                conf=self._confidence_threshold(),
                verbose=False,
            )
        except Exception as exc:
            raise DetectionModelError(
                f"Object detection inference failed: {exc}"
            ) from exc

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
                        class_name=self._result_class_name(model, class_id),
                        confidence=confidence,
                        bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                        channel=str(channel),
                        timestamp=timestamp,
                        snapshot_path=snapshot_path,
                    )
                )

        return self._filter_detections(detections)

    @staticmethod
    def _decode_image(image_bytes: bytes):
        image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if image is None:
            raise DetectionModelError("Could not decode snapshot image")
        return image

    @staticmethod
    def _result_class_name(model, class_id: int) -> str:
        names = getattr(model, "names", {}) or {}
        if isinstance(names, dict):
            return str(names.get(class_id, class_id))
        if isinstance(names, list) and 0 <= class_id < len(names):
            return str(names[class_id])
        return str(class_id)
