from __future__ import annotations

from app.services.detection_backends.base import DetectionModelError, DetectionResult


class NcnnBackend:
    name = "ncnn"

    def load(self) -> None:
        raise DetectionModelError("NCNN backend is not implemented yet")

    def detect(
        self,
        image_bytes: bytes,
        channel: str,
        snapshot_path: str | None = None,
    ) -> list[DetectionResult]:
        raise DetectionModelError("NCNN backend is not implemented yet")
