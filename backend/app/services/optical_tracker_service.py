from __future__ import annotations

import logging
import os
from typing import Any

import cv2
import numpy as np
from dotenv import load_dotenv

from app.db.database import PROJECT_ROOT

logger = logging.getLogger(__name__)

# Key: (channel, track_id), Value: OpenCV Tracker object
_TRACKERS: dict[tuple[str, int], Any] = {}


def _load_env() -> None:
    load_dotenv(PROJECT_ROOT / ".env")


def get_tracker_type() -> str:
    _load_env()
    return os.getenv("OPTICAL_TRACKER_TYPE", "KCF").strip().upper()


def _create_raw_tracker(tracker_type: str) -> Any:
    """Attempts to create OpenCV tracker based on type. Falls back to MIL or None."""
    # First, try requested type if available
    try:
        if tracker_type == "KCF" and hasattr(cv2, "TrackerKCF_create"):
            return cv2.TrackerKCF_create()
        elif tracker_type == "CSRT" and hasattr(cv2, "TrackerCSRT_create"):
            return cv2.TrackerCSRT_create()
        elif tracker_type == "MIL" and hasattr(cv2, "TrackerMIL_create"):
            return cv2.TrackerMIL_create()
    except Exception as exc:
        logger.warning("Failed to create requested tracker type %s: %s", tracker_type, exc)

    # Secondary fallback to MIL, which is usually built-in
    try:
        if hasattr(cv2, "TrackerMIL_create"):
            return cv2.TrackerMIL_create()
    except Exception as exc:
        logger.warning("Fallback TrackerMIL_create failed: %s", exc)

    return None


def init_tracker(channel: str, track_id: int, frame: np.ndarray, bbox: list[int]) -> bool:
    """Initializes an optical tracker for a given track on a channel."""
    channel_key = str(channel)
    x1, y1, x2, y2 = bbox
    w = max(1, x2 - x1)
    h = max(1, y2 - y1)
    opencv_bbox = (int(x1), int(y1), int(w), int(h))

    tracker_type = get_tracker_type()
    tracker = _create_raw_tracker(tracker_type)

    if tracker is None:
        # Fallback to manual bbox tracking (just keep box static or estimate)
        logger.debug(
            "No OpenCV tracker available. Fallback to manual bbox tracking for track #%d",
            track_id,
        )
        _TRACKERS[(channel_key, track_id)] = {"manual_bbox": [x1, y1, x2, y2]}
        return True

    try:
        # Some OpenCV builds require BGR, ensure correct shape
        if len(frame.shape) == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        ok = tracker.init(frame, opencv_bbox)
        if ok:
            _TRACKERS[(channel_key, track_id)] = tracker
            logger.debug("Successfully initialized OpenCV tracker for track #%d", track_id)
            return True
        else:
            logger.warning("OpenCV tracker init failed for track #%d", track_id)
    except Exception as exc:
        logger.warning("Error initializing OpenCV tracker for track #%d: %s", track_id, exc)

    # If tracker failed, still save manual bbox fallback
    _TRACKERS[(channel_key, track_id)] = {"manual_bbox": [x1, y1, x2, y2]}
    return True


def update_tracker(channel: str, track_id: int, frame: np.ndarray) -> list[int] | None:
    """Updates an optical tracker on a new frame and returns the new [x1, y1, x2, y2] bbox."""
    channel_key = str(channel)
    tracker = _TRACKERS.get((channel_key, track_id))
    if tracker is None:
        return None

    # Handle manual fallback
    if isinstance(tracker, dict) and "manual_bbox" in tracker:
        return tracker["manual_bbox"]

    try:
        if len(frame.shape) == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        ok, opencv_bbox = tracker.update(frame)
        if ok:
            x, y, w, h = opencv_bbox
            x1 = int(round(x))
            y1 = int(round(y))
            x2 = int(round(x + w))
            y2 = int(round(y + h))
            # Keep manual_bbox updated in case tracker gets replaced or for fallback
            # Bound check or sanity check
            return [x1, y1, x2, y2]
        else:
            logger.debug("OpenCV tracker update failed for track #%d, using manual fallback", track_id)
    except Exception as exc:
        logger.warning("Error updating OpenCV tracker for track #%d: %s", track_id, exc)

    return None


def remove_tracker(channel: str, track_id: int) -> None:
    """Removes an active tracker."""
    _TRACKERS.pop((str(channel), track_id), None)


def clear_channel_trackers(channel: str) -> None:
    """Clears all trackers associated with a specific channel."""
    channel_key = str(channel)
    keys_to_remove = [k for k in _TRACKERS if k[0] == channel_key]
    for k in keys_to_remove:
        _TRACKERS.pop(k, None)


def reset_tracker_service() -> None:
    """Clears all trackers across all channels."""
    _TRACKERS.clear()
