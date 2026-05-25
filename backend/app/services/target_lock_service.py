from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Format per channel:
# {
#     "locked": bool,
#     "track_id": int | None,
#     "class_name": str | None,
#     "status": str | None
# }
_TARGET_LOCKS: dict[str, dict[str, Any]] = {}


def get_default_lock_state() -> dict[str, Any]:
    return {
        "locked": False,
        "track_id": None,
        "class_name": None,
        "status": None,
    }


def get_target_status(channel: str) -> dict[str, Any]:
    """Returns the current target lock status for a channel."""
    channel_key = str(channel)
    return _TARGET_LOCKS.setdefault(channel_key, get_default_lock_state())


def lock_target_by_id(
    channel: str, track_id: int, class_name: str | None = None, status: str = "active"
) -> dict[str, Any]:
    """Locks a target on a channel by its track ID."""
    channel_key = str(channel)
    lock_state = {
        "locked": True,
        "track_id": int(track_id),
        "class_name": class_name,
        "status": status,
    }
    _TARGET_LOCKS[channel_key] = lock_state
    logger.info("Locked target by ID #%d on channel %s", track_id, channel_key)
    return lock_state


def lock_target_by_coordinates(
    channel: str, x: int, y: int, active_objects: list[Any]
) -> dict[str, Any]:
    """Locks the closest active object to the clicked coordinates (x, y)."""
    channel_key = str(channel)
    if not active_objects:
        logger.debug("No active objects to lock by coordinates (%d, %d)", x, y)
        return get_target_status(channel_key)

    closest_obj = None
    min_dist = float("inf")

    for obj in active_objects:
        # Check center [cx, cy]
        if hasattr(obj, "center") and obj.center:
            cx, cy = obj.center
        elif isinstance(obj, dict) and "center" in obj:
            cx, cy = obj["center"]
        elif hasattr(obj, "bbox") and obj.bbox:
            x1, y1, x2, y2 = obj.bbox
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
        elif isinstance(obj, dict) and "bbox" in obj:
            x1, y1, x2, y2 = obj["bbox"]
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
        else:
            continue

        dist = ((cx - x) ** 2 + (cy - y) ** 2) ** 0.5
        if dist < min_dist:
            min_dist = dist
            closest_obj = obj

    # We can set a maximum radius to lock, e.g., 200 pixels, or just closest
    if closest_obj is not None:
        track_id = (
            closest_obj.track_id
            if hasattr(closest_obj, "track_id")
            else closest_obj.get("track_id")
        )
        class_name = (
            closest_obj.class_name
            if hasattr(closest_obj, "class_name")
            else closest_obj.get("class_name")
        )
        status = (
            closest_obj.status
            if hasattr(closest_obj, "status")
            else closest_obj.get("status", "active")
        )
        return lock_target_by_id(channel_key, track_id, class_name, status)

    return get_target_status(channel_key)


def clear_target(channel: str) -> dict[str, Any]:
    """Clears the locked target for a channel."""
    channel_key = str(channel)
    lock_state = get_default_lock_state()
    _TARGET_LOCKS[channel_key] = lock_state
    logger.info("Cleared target lock on channel %s", channel_key)
    return lock_state


def sync_target_with_tracks(channel: str, active_objects: list[Any]) -> None:
    """Updates status/metadata of the locked target based on active tracks."""
    channel_key = str(channel)
    status = get_target_status(channel_key)
    if not status["locked"]:
        return

    track_id = status["track_id"]
    # Find this track in the active objects list
    matching_obj = None
    for obj in active_objects:
        obj_id = obj.track_id if hasattr(obj, "track_id") else obj.get("track_id")
        if obj_id == track_id:
            matching_obj = obj
            break

    if matching_obj is not None:
        # Track is active, update status and class name
        obj_status = (
            matching_obj.status
            if hasattr(matching_obj, "status")
            else matching_obj.get("status", "active")
        )
        obj_class = (
            matching_obj.class_name
            if hasattr(matching_obj, "class_name")
            else matching_obj.get("class_name")
        )
        status["status"] = obj_status
        status["class_name"] = obj_class
    else:
        # Track is not in the active objects list, it is lost/expired
        status["status"] = "lost"


def reset_target_lock_service() -> None:
    """Resets all target locks."""
    _TARGET_LOCKS.clear()
