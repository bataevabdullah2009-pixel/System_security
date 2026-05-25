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
    image_bytes, snapshot_path, _latest_path = camera_service.capture_fresh_snapshot(
        channel_key
    )
    from app.services import frame_pipeline_service
    return frame_pipeline_service.process_frame(
        channel=channel_key,
        image_bytes=image_bytes,
        snapshot_path=str(snapshot_path),
    )


def get_state(channel: int | str) -> dict[str, object]:
    channel_key = str(channel)
    state = _STATE_BY_CHANNEL.get(channel_key)
    if state is not None:
        return state

    objects = tracking_service.get_tracks(channel_key)
    from app.services import target_lock_service
    target_info = target_lock_service.get_target_status(channel_key)
    return {
        "channel": channel_key,
        "updated_at": None,
        "worker": _worker_status(channel_key),
        "target": target_info,
        "objects": [obj.to_api_dict() for obj in objects if obj.status == "active"],
    }


def latest_annotated_frame(channel: int | str) -> bytes | None:
    path = vision_overlay_service.latest_annotated_frame_path(channel)
    if path is None:
        return None
    return path.read_bytes()


def reset_vision_state() -> None:
    _STATE_BY_CHANNEL.clear()
    tracking_service.reset_tracker_state()
    from app.services import frame_pipeline_service
    frame_pipeline_service.reset_frame_pipeline_state()


def _worker_status(channel: str) -> dict[str, object]:
    try:
        from app.services import vision_worker_service

        status = vision_worker_service.get_worker_status(channel)
        return {
            "running": status["running"],
            "updates_count": status["updates_count"],
            "last_error": status["last_error"],
            "measured_fps": status.get("measured_fps"),
        }
    except Exception:
        return {"running": False, "updates_count": 0, "last_error": None, "measured_fps": None}

