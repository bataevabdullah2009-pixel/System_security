from __future__ import annotations

from app.services.detection_backends.base import DetectionModelError, DetectionResult


class OnnxRuntimeBackend:
    name = "onnxruntime"

    def load(self) -> None:
        raise DetectionModelError("ONNX backend is not implemented yet")

    def detect(
        self,
        image_bytes: bytes,
        channel: str,
        snapshot_path: str | None = None,
    ) -> list[DetectionResult]:
        raise DetectionModelError("ONNX backend is not implemented yet")
