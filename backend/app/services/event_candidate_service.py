from __future__ import annotations

from app.services.detection_service import DetectionResult
from app.services.event_service import build_event_candidates_from_detections


def build_event_candidates(detections: list[DetectionResult]) -> list[dict[str, object]]:
    channel = detections[0].channel if detections else ""
    return build_event_candidates_from_detections(channel, detections)
