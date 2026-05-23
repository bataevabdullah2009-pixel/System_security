from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol


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


class DetectionBackend(Protocol):
    name: str

    def load(self) -> None:
        ...

    def detect(
        self,
        image_bytes: bytes,
        channel: str,
        snapshot_path: str | None = None,
    ) -> list[DetectionResult]:
        ...
