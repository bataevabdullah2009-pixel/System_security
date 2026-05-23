from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.db.schemas import EventStatusUpdate
from app.services import camera_service, detection_service, event_service

router = APIRouter(prefix="/api/events", tags=["events"])


def _validate_channel(channel: str) -> str:
    if channel not in camera_service.HIKVISION_CHANNELS:
        allowed = ", ".join(camera_service.HIKVISION_CHANNELS)
        raise HTTPException(
            status_code=400, detail=f"Unsupported channel. Use one of: {allowed}"
        )
    return channel


def _process_hikvision_channel(channel: str) -> dict[str, object]:
    image_bytes, snapshot_path, _latest_path = camera_service.capture_fresh_snapshot(
        channel
    )
    detections = detection_service.detect_objects(
        image_bytes=image_bytes,
        channel=channel,
        snapshot_path=str(snapshot_path),
    )
    annotated_path = detection_service.save_annotated_snapshot(
        channel, image_bytes, detections
    )
    result = event_service.process_detection_result(
        channel=channel,
        detections=detections,
        snapshot_path=str(snapshot_path),
        annotated_snapshot_path=str(annotated_path),
    )
    return {
        "channel": channel,
        "created_events": result["created_events"],
        "skipped_events": result["skipped_events"],
        "detections": [detection.to_api_dict() for detection in detections],
    }


@router.get("")
def list_events(
    limit: int = 50,
    status: str | None = None,
    event_type: str | None = None,
    channel: str | None = None,
) -> list[dict[str, object]]:
    return event_service.list_events(
        limit=limit,
        status=status,
        event_type=event_type,
        channel=channel,
    )


@router.post("/process/hikvision/{channel}")
def process_hikvision_channel(channel: str) -> dict[str, object]:
    _validate_channel(channel)
    try:
        return _process_hikvision_channel(channel)
    except detection_service.DetectionModelError as exc:
        _create_error_event(channel, "detection_error")
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        _create_error_event(channel, "camera_snapshot_error")
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/diagnose/hikvision")
def diagnose_hikvision_events() -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for channel in camera_service.HIKVISION_CHANNELS:
        try:
            process_result = _process_hikvision_channel(channel)
            results.append(
                {
                    "channel": channel,
                    "status": "online",
                    "created_count": len(process_result["created_events"]),
                    "skipped_count": len(process_result["skipped_events"]),
                    "detection_count": len(process_result["detections"]),
                    "error": None,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "channel": channel,
                    "status": "offline",
                    "created_count": 0,
                    "skipped_count": 0,
                    "detection_count": 0,
                    "error": str(exc),
                }
            )
    return results


@router.get("/{event_id}")
def get_event(event_id: int) -> dict[str, object]:
    event = event_service.get_event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.patch("/{event_id}/status")
def update_event_status(event_id: int, payload: EventStatusUpdate) -> dict[str, object]:
    try:
        event = event_service.update_event_status(event_id, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


def _create_error_event(channel: str, event_type: str) -> None:
    event_key = event_service.build_event_key(channel, event_type)
    if event_service.should_create_event(event_key):
        event_service.create_event_from_detection(
            channel=channel,
            event_type=event_type,
            detections=[],
            snapshot_path=None,
            annotated_snapshot_path=None,
        )
