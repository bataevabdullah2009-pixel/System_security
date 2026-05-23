from __future__ import annotations

from app.services.detection_service import DetectionResult, VEHICLE_CLASSES


def build_event_candidates(detections: list[DetectionResult]) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []

    person_count = sum(1 for detection in detections if detection.class_name == "person")
    vehicle_count = sum(1 for detection in detections if detection.class_name in VEHICLE_CLASSES)

    if person_count:
        candidates.append({"event_type": "person_detected", "count": person_count})
    if vehicle_count:
        candidates.append({"event_type": "vehicle_detected", "count": vehicle_count})

    return candidates
