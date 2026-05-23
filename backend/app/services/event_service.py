from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import desc, select

from app.db.database import PROJECT_ROOT, session_scope
from app.db.models import Event
from app.services.detection_service import DetectionResult, VEHICLE_CLASSES


EVENT_TYPES = {
    "person_detected",
    "vehicle_detected",
    "camera_snapshot_error",
    "detection_error",
}
EVENT_STATUSES = {"new", "acknowledged", "resolved", "ignored"}


def _load_env() -> None:
    load_dotenv(PROJECT_ROOT / ".env")


def event_enabled() -> bool:
    _load_env()
    return os.getenv("EVENT_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}


def event_cooldown_seconds() -> float:
    _load_env()
    raw = os.getenv("EVENT_COOLDOWN_SECONDS", "60").strip()
    try:
        return float(raw)
    except ValueError:
        return 60.0


def build_event_key(channel: str | int, event_type: str) -> str:
    return f"{channel}:{event_type}"


def build_event_candidates_from_detections(
    channel: str | int,
    detections: list[DetectionResult],
) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    person_detections = [detection for detection in detections if detection.class_name == "person"]
    vehicle_detections = [
        detection for detection in detections if detection.class_name in VEHICLE_CLASSES
    ]

    if person_detections:
        candidates.append(
            {
                "event_type": "person_detected",
                "event_key": build_event_key(channel, "person_detected"),
                "count": len(person_detections),
            }
        )
    if vehicle_detections:
        candidates.append(
            {
                "event_type": "vehicle_detected",
                "event_key": build_event_key(channel, "vehicle_detected"),
                "count": len(vehicle_detections),
            }
        )
    return candidates


def should_create_event(event_key: str) -> bool:
    if not event_enabled():
        return False

    cooldown = timedelta(seconds=event_cooldown_seconds())
    with session_scope() as session:
        latest_event = session.scalar(
            select(Event)
            .where(Event.event_key == event_key)
            .order_by(desc(Event.created_at))
            .limit(1)
        )
        if latest_event is None:
            return True

        created_at = _as_utc(latest_event.created_at)
        return datetime.now(timezone.utc) - created_at >= cooldown


def create_event_from_detection(
    channel: str | int,
    event_type: str,
    detections: list[DetectionResult],
    snapshot_path: str | Path | None,
    annotated_snapshot_path: str | Path | None,
) -> Event:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unsupported event type: {event_type}")

    related_detections = _filter_detections_for_event(event_type, detections)
    event_key = build_event_key(channel, event_type)
    confidence = _max_confidence(related_detections)
    with session_scope() as session:
        event = Event(
            event_type=event_type,
            status="new",
            channel=str(channel),
            source="hikvision_isapi_snapshot",
            title=_event_title(event_type, related_detections),
            description=_event_description(event_type, related_detections),
            confidence=confidence,
            snapshot_path=str(snapshot_path) if snapshot_path is not None else None,
            annotated_snapshot_path=(
                str(annotated_snapshot_path) if annotated_snapshot_path is not None else None
            ),
            detections_json=json.dumps(
                [detection.to_api_dict() for detection in related_detections],
                ensure_ascii=True,
            ),
            event_key=event_key,
        )
        session.add(event)
        session.flush()
        session.refresh(event)
        return event


def process_detection_result(
    channel: str | int,
    detections: list[DetectionResult],
    snapshot_path: str | Path | None,
    annotated_snapshot_path: str | Path | None,
) -> dict[str, list[dict[str, object]]]:
    created_events: list[dict[str, object]] = []
    skipped_events: list[dict[str, object]] = []

    for candidate in build_event_candidates_from_detections(channel, detections):
        event_type = str(candidate["event_type"])
        event_key = str(candidate["event_key"])
        if should_create_event(event_key):
            event = create_event_from_detection(
                channel=channel,
                event_type=event_type,
                detections=detections,
                snapshot_path=snapshot_path,
                annotated_snapshot_path=annotated_snapshot_path,
            )
            created_events.append(event_to_dict(event))
        else:
            skipped_events.append(
                {
                    "event_type": event_type,
                    "event_key": event_key,
                    "reason": "cooldown",
                }
            )

    return {"created_events": created_events, "skipped_events": skipped_events}


def list_events(
    limit: int,
    status: str | None = None,
    event_type: str | None = None,
    channel: str | None = None,
) -> list[dict[str, object]]:
    safe_limit = max(1, min(int(limit), 200))
    statement = select(Event)
    if status is not None:
        statement = statement.where(Event.status == status)
    if event_type is not None:
        statement = statement.where(Event.event_type == event_type)
    if channel is not None:
        statement = statement.where(Event.channel == str(channel))
    statement = statement.order_by(desc(Event.created_at)).limit(safe_limit)

    with session_scope() as session:
        return [event_to_dict(event) for event in session.scalars(statement).all()]


def get_event(event_id: int) -> dict[str, object] | None:
    with session_scope() as session:
        event = session.get(Event, event_id)
        return event_to_dict(event) if event is not None else None


def update_event_status(event_id: int, status: str) -> dict[str, object] | None:
    if status not in EVENT_STATUSES:
        raise ValueError(f"Unsupported event status: {status}")

    now = datetime.now(timezone.utc)
    with session_scope() as session:
        event = session.get(Event, event_id)
        if event is None:
            return None

        event.status = status
        event.updated_at = now
        if status == "acknowledged":
            event.acknowledged_at = now
        if status == "resolved":
            event.resolved_at = now
        session.flush()
        session.refresh(event)
        return event_to_dict(event)


def event_to_dict(event: Event) -> dict[str, object]:
    return {
        "id": event.id,
        "event_type": event.event_type,
        "status": event.status,
        "channel": event.channel,
        "source": event.source,
        "title": event.title,
        "description": event.description,
        "confidence": event.confidence,
        "snapshot_path": event.snapshot_path,
        "annotated_snapshot_path": event.annotated_snapshot_path,
        "detections": json.loads(event.detections_json or "[]"),
        "event_key": event.event_key,
        "created_at": event.created_at,
        "updated_at": event.updated_at,
        "acknowledged_at": event.acknowledged_at,
        "resolved_at": event.resolved_at,
    }


def _filter_detections_for_event(
    event_type: str,
    detections: list[DetectionResult],
) -> list[DetectionResult]:
    if event_type == "person_detected":
        return [detection for detection in detections if detection.class_name == "person"]
    if event_type == "vehicle_detected":
        return [detection for detection in detections if detection.class_name in VEHICLE_CLASSES]
    return detections


def _max_confidence(detections: list[DetectionResult]) -> float | None:
    if not detections:
        return None
    return max(float(detection.confidence) for detection in detections)


def _event_title(event_type: str, detections: list[DetectionResult]) -> str:
    count = len(detections)
    if event_type == "person_detected":
        return f"Person detected ({count})"
    if event_type == "vehicle_detected":
        return f"Vehicle detected ({count})"
    if event_type == "camera_snapshot_error":
        return "Camera snapshot error"
    if event_type == "detection_error":
        return "Detection error"
    return event_type


def _event_description(event_type: str, detections: list[DetectionResult]) -> str:
    if event_type in {"camera_snapshot_error", "detection_error"}:
        return _event_title(event_type, detections)
    classes = ", ".join(sorted({detection.class_name for detection in detections}))
    return f"Detected {len(detections)} object(s): {classes}"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
