from __future__ import annotations

from datetime import datetime, timezone

from app.services import (
    camera_service,
    detection_service,
    dwell_service,
    event_service,
    tracking_service,
    vision_overlay_service,
    vision_persistence_service,
    zone_service,
)

_STATE_BY_CHANNEL: dict[str, dict[str, object]] = {}


def update_once(channel: int | str) -> dict[str, object]:
    channel_key = str(channel)
    updated_at = datetime.now(timezone.utc)

    image_bytes, snapshot_path, _latest_path = camera_service.capture_fresh_snapshot(
        channel_key
    )
    detections = detection_service.detect_objects(
        image_bytes=image_bytes,
        channel=channel_key,
        snapshot_path=str(snapshot_path),
    )
    objects = tracking_service.update_tracks(channel_key, detections, now=updated_at)

    zones = zone_service.load_zones(channel_key)
    zones_by_track_id = {
        obj.track_id: zone_service.get_object_zones(channel_key, obj.center)
        for obj in objects
    }
    tracking_service.set_track_zones(channel_key, zones_by_track_id)
    objects = tracking_service.get_tracks(channel_key, now=updated_at)

    for obj in objects:
        if obj.status == "active":
            obj.dwell = dwell_service.update_zone_presence(
                track=obj,
                zone_ids=obj.zone_ids,
                now=updated_at,
            )

    event_result = event_service.process_tracking_result(
        channel=channel_key,
        objects=objects,
        snapshot_path=str(snapshot_path),
        annotated_snapshot_path=None,
        zones=zones,
    )
    event_count = len(event_result["created_events"])
    worker_status = _worker_status(channel_key)

    annotated_bytes = vision_overlay_service.draw_premium_overlay(
        image_bytes=image_bytes,
        channel=channel_key,
        objects=objects,
        zones=zones,
        updated_at=updated_at,
        worker_status=worker_status,
        event_count=event_count,
    )
    annotated_path = vision_overlay_service.save_latest_annotated_frame(
        channel_key, annotated_bytes
    )
    vision_persistence_service.save_tracks(channel_key, objects)

    state = {
        "channel": channel_key,
        "updated_at": updated_at.isoformat(),
        "worker": worker_status,
        "objects": [obj.to_api_dict() for obj in objects],
        "snapshot_path": str(snapshot_path),
        "annotated_frame_path": str(annotated_path),
        "events": event_result,
    }
    _STATE_BY_CHANNEL[channel_key] = state
    return state


def get_state(channel: int | str) -> dict[str, object]:
    channel_key = str(channel)
    state = _STATE_BY_CHANNEL.get(channel_key)
    if state is not None:
        return state

    objects = tracking_service.get_tracks(channel_key)
    return {
        "channel": channel_key,
        "updated_at": None,
        "worker": _worker_status(channel_key),
        "objects": [obj.to_api_dict() for obj in objects],
    }


def latest_annotated_frame(channel: int | str) -> bytes | None:
    path = vision_overlay_service.latest_annotated_frame_path(channel)
    if path is None:
        return None
    return path.read_bytes()


def reset_vision_state() -> None:
    _STATE_BY_CHANNEL.clear()
    tracking_service.reset_tracker_state()


def _worker_status(channel: str) -> dict[str, object]:
    try:
        from app.services import vision_worker_service

        status = vision_worker_service.get_worker_status(channel)
        return {
            "running": status["running"],
            "updates_count": status["updates_count"],
            "last_error": status["last_error"],
        }
    except Exception:
        return {"running": False, "updates_count": 0, "last_error": None}
