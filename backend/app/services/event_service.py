from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import desc, select

from app.db.database import PROJECT_ROOT, session_scope
from app.db.models import Event
from app.services.detection_service import DetectionResult, VEHICLE_CLASSES

logger = logging.getLogger(__name__)

EVENT_TYPES = {
    "person_detected",
    "vehicle_detected",
    "camera_snapshot_error",
    "detection_error",
    "tracked_person_detected",
    "tracked_vehicle_detected",
    "person_entered_zone",
    "vehicle_entered_zone",
    "person_entered_restricted_zone",
    "person_loitering",
    "vehicle_stopped_in_zone",
    "suspicious_event_candidate",
    "zone_activity",
}
EVENT_STATUSES = {"new", "acknowledged", "resolved", "ignored"}


def _load_env() -> None:
    load_dotenv(PROJECT_ROOT / ".env")


def event_enabled() -> bool:
    _load_env()
    return os.getenv("EVENT_ENABLED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


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
    person_detections = [
        detection for detection in detections if detection.class_name == "person"
    ]
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
                str(annotated_snapshot_path)
                if annotated_snapshot_path is not None
                else None
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

    telegram_alert = _send_telegram_alert(event)
    setattr(event, "telegram_alert", telegram_alert)
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


def process_tracking_result(
    channel: str | int,
    objects: list[object],
    snapshot_path: str | Path | None,
    annotated_snapshot_path: str | Path | None,
    zones: list[dict[str, object]] | None = None,
) -> dict[str, list[dict[str, object]]]:
    created_events: list[dict[str, object]] = []
    skipped_events: list[dict[str, object]] = []

    for candidate in build_event_candidates_from_tracks(channel, objects, zones=zones):
        event_type = str(candidate["event_type"])
        event_key = str(candidate["event_key"])
        if should_create_event(event_key):
            event = create_event_from_tracking(
                channel=channel,
                event_type=event_type,
                objects=objects,
                snapshot_path=snapshot_path,
                annotated_snapshot_path=annotated_snapshot_path,
                event_key=event_key,
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


def build_event_candidates_from_tracks(
    channel: str | int,
    objects: list[object],
    zones: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    active_objects = [
        obj for obj in objects if getattr(obj, "status", None) == "active"
    ]
    candidates: list[dict[str, object]] = []
    zones_by_id = {
        str(zone["id"]): zone
        for zone in (zones or [])
        if isinstance(zone, dict) and isinstance(zone.get("id"), str)
    }

    if any(getattr(obj, "class_name", None) == "person" for obj in active_objects):
        candidates.append(
            {
                "event_type": "tracked_person_detected",
                "event_key": build_event_key(channel, "tracked_person_detected"),
            }
        )
    if any(
        getattr(obj, "class_name", None) in VEHICLE_CLASSES for obj in active_objects
    ):
        candidates.append(
            {
                "event_type": "tracked_vehicle_detected",
                "event_key": build_event_key(channel, "tracked_vehicle_detected"),
            }
        )

    zone_activity: set[tuple[str, str]] = set()
    for obj in active_objects:
        class_name = getattr(obj, "class_name", "")
        track_id = getattr(obj, "track_id", "unknown")
        dwell = getattr(obj, "dwell", {}) or {}
        zone_ids = getattr(obj, "zone_ids", []) or []
        for zone_id in zone_ids:
            zone_type = str(zones_by_id.get(str(zone_id), {}).get("type") or "")
            if class_name == "person":
                zone_activity.add(("person_entered_zone", str(zone_id)))
                if zone_type == "restricted":
                    zone_activity.add(("person_entered_restricted_zone", str(zone_id)))
                if float(dwell.get(zone_id, 0.0)) >= _loitering_threshold_seconds():
                    candidates.append(
                        {
                            "event_type": "person_loitering",
                            "event_key": build_event_key(
                                channel,
                                f"person_loitering:{track_id}:{zone_id}",
                            ),
                        }
                    )
            if class_name in VEHICLE_CLASSES:
                zone_activity.add(("vehicle_entered_zone", str(zone_id)))
                if float(dwell.get(zone_id, 0.0)) >= _loitering_threshold_seconds():
                    candidates.append(
                        {
                            "event_type": "vehicle_stopped_in_zone",
                            "event_key": build_event_key(
                                channel,
                                f"vehicle_stopped_in_zone:{track_id}:{zone_id}",
                            ),
                        }
                    )

    for event_type, zone_id in sorted(zone_activity):
        candidates.append(
            {
                "event_type": event_type,
                "event_key": build_event_key(channel, f"{event_type}:{zone_id}"),
            }
        )
    return candidates


def create_event_from_tracking(
    channel: str | int,
    event_type: str,
    objects: list[object],
    snapshot_path: str | Path | None,
    annotated_snapshot_path: str | Path | None,
    event_key: str | None = None,
) -> Event:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unsupported event type: {event_type}")

    related_objects = _filter_tracks_for_event(event_type, objects)
    confidence = _max_track_confidence(related_objects)
    with session_scope() as session:
        event = Event(
            event_type=event_type,
            status="new",
            channel=str(channel),
            source="hikvision_live_vision_tracking",
            title=_tracking_event_title(event_type, related_objects),
            description=_tracking_event_description(event_type, related_objects),
            confidence=confidence,
            snapshot_path=str(snapshot_path) if snapshot_path is not None else None,
            annotated_snapshot_path=(
                str(annotated_snapshot_path)
                if annotated_snapshot_path is not None
                else None
            ),
            detections_json=json.dumps(
                [_track_to_payload(obj) for obj in related_objects],
                ensure_ascii=True,
            ),
            event_key=event_key or build_event_key(channel, event_type),
        )
        session.add(event)
        session.flush()
        session.refresh(event)

    telegram_alert = _send_telegram_alert(event)
    setattr(event, "telegram_alert", telegram_alert)
    return event


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
        "telegram_alert": getattr(event, "telegram_alert", None),
    }


def _filter_detections_for_event(
    event_type: str,
    detections: list[DetectionResult],
) -> list[DetectionResult]:
    if event_type == "person_detected":
        return [
            detection for detection in detections if detection.class_name == "person"
        ]
    if event_type == "vehicle_detected":
        return [
            detection
            for detection in detections
            if detection.class_name in VEHICLE_CLASSES
        ]
    return detections


def _filter_tracks_for_event(event_type: str, objects: list[object]) -> list[object]:
    active_objects = [
        obj for obj in objects if getattr(obj, "status", None) == "active"
    ]
    if event_type in {
        "tracked_person_detected",
        "person_entered_zone",
        "person_entered_restricted_zone",
        "person_loitering",
    }:
        return [
            obj
            for obj in active_objects
            if getattr(obj, "class_name", None) == "person"
        ]
    if event_type in {
        "tracked_vehicle_detected",
        "vehicle_entered_zone",
        "vehicle_stopped_in_zone",
    }:
        return [
            obj
            for obj in active_objects
            if getattr(obj, "class_name", None) in VEHICLE_CLASSES
        ]
    return active_objects


def _max_confidence(detections: list[DetectionResult]) -> float | None:
    if not detections:
        return None
    return max(float(detection.confidence) for detection in detections)


def _max_track_confidence(objects: list[object]) -> float | None:
    if not objects:
        return None
    return max(float(getattr(obj, "confidence", 0.0)) for obj in objects)


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


def _tracking_event_title(event_type: str, objects: list[object]) -> str:
    count = len(objects)
    if event_type == "tracked_person_detected":
        return f"Tracked person detected ({count})"
    if event_type == "tracked_vehicle_detected":
        return f"Tracked vehicle detected ({count})"
    if event_type == "person_entered_zone":
        return f"Person entered zone ({count})"
    if event_type == "vehicle_entered_zone":
        return f"Vehicle entered zone ({count})"
    if event_type == "person_entered_restricted_zone":
        return f"Person entered restricted zone ({count})"
    if event_type == "person_loitering":
        return "Person loitering in zone"
    if event_type == "vehicle_stopped_in_zone":
        return "Vehicle stopped in zone"
    if event_type == "zone_activity":
        return f"Zone activity ({count})"
    if event_type == "suspicious_event_candidate":
        return f"Suspicious event candidate ({count})"
    return event_type


def _tracking_event_description(event_type: str, objects: list[object]) -> str:
    classes = ", ".join(
        sorted({str(getattr(obj, "class_name", "unknown")) for obj in objects})
    )
    zone_ids = sorted(
        {
            str(zone_id)
            for obj in objects
            for zone_id in (getattr(obj, "zone_ids", []) or [])
        }
    )
    zone_text = f"; zones: {', '.join(zone_ids)}" if zone_ids else ""
    return f"Tracked {len(objects)} object(s): {classes}{zone_text}"


def _track_to_payload(obj: object) -> dict[str, object]:
    if hasattr(obj, "to_api_dict"):
        return obj.to_api_dict()
    return {
        "track_id": getattr(obj, "track_id", None),
        "class_name": getattr(obj, "class_name", None),
        "confidence": getattr(obj, "confidence", None),
        "bbox": getattr(obj, "bbox", None),
        "center": getattr(obj, "center", None),
        "path": getattr(obj, "path", None),
        "status": getattr(obj, "status", None),
        "zone_ids": getattr(obj, "zone_ids", None),
        "dwell": getattr(obj, "dwell", None),
    }


def _loitering_threshold_seconds() -> float:
    try:
        from app.services import dwell_service

        return dwell_service.loitering_threshold_seconds()
    except Exception:
        return 30.0


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _send_telegram_alert(event: Event) -> dict[str, object]:
    try:
        from app.services import telegram_alert_service

        return telegram_alert_service.send_event_alert(event)
    except Exception as exc:
        logger.warning(
            "Telegram alert integration failed for event_id=%s error=%s", event.id, exc
        )
        return {"sent": False, "reason": f"telegram_error: {exc}"}
