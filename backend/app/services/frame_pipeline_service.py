from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import cv2
import numpy as np

from app.services import (
    camera_service,
    detection_service,
    dwell_service,
    event_service,
    hud_overlay_service,
    optical_tracker_service,
    target_lock_service,
    tracking_service,
    vision_persistence_service,
    zone_service,
)

logger = logging.getLogger(__name__)

# State trackers
_FRAME_COUNTER: dict[str, int] = {}
_SMOOTHED_BBOXES: dict[tuple[str, int], list[float]] = {}
_TRACK_HITS: dict[tuple[str, int], int] = {}
_TRACK_MISSES: dict[tuple[str, int], int] = {}


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        return float(raw)
    except ValueError:
        return default


def get_detection_interval() -> int:
    return int(_float_env("DETECTION_EVERY_N_FRAMES", 10.0))


def get_bbox_smoothing_alpha() -> float:
    return _float_env("BBOX_SMOOTHING_ALPHA", 0.35)


def get_track_ttl_seconds() -> float:
    return _float_env("TRACK_TTL_SECONDS", 10.0)


def get_track_max_misses() -> int:
    return int(_float_env("TRACK_MAX_MISSES", 2.0))


def get_track_min_hits() -> int:
    return int(_float_env("TRACK_MIN_HITS", 1.0))



def get_show_lost_tracks() -> bool:
    return os.getenv("SHOW_LOST_TRACKS", "false").strip().lower() in {"1", "true", "yes", "on"}


def process_frame(
    channel: int | str,
    image_bytes: bytes,
    snapshot_path: str | None = None,
    now: datetime | None = None,
    force_detection: bool = False,
    hud_style_override: str | None = None,
) -> dict[str, Any]:
    """Processes a single camera frame through YOLO/Optical Tracking, smoothing, events and HUD overlay."""
    channel_key = str(channel)
    now = now or datetime.now(timezone.utc)

    # 1. Update Frame Counter
    _FRAME_COUNTER[channel_key] = _FRAME_COUNTER.get(channel_key, 0) + 1
    frame_count = _FRAME_COUNTER[channel_key]

    # Decode frame to numpy array for trackers
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    frame_np = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if frame_np is None:
        raise RuntimeError(f"Could not decode image bytes for channel {channel_key}")

    # Determine if we run full YOLO detection
    detection_every = get_detection_interval()
    all_tracks = tracking_service.get_tracks(channel_key, now=now)
    active_tracks = [t for t in all_tracks if t.status == "active"]

    run_yolo = (frame_count % detection_every == 0) or (not active_tracks) or force_detection

    if run_yolo:
        logger.debug("Pipeline: Channel %s running YOLO Detection at frame %d", channel_key, frame_count)
        # Run YOLO detection
        detections = detection_service.detect_objects(
            image_bytes=image_bytes,
            channel=channel_key,
            snapshot_path=snapshot_path,
        )
        # Update tracks in tracking service
        all_tracks = tracking_service.update_tracks(channel_key, detections, now=now)
        
        # Sync OpenCV trackers
        # Clear obsolete trackers first
        active_ids = {t.track_id for t in all_tracks if t.status == "active"}
        for k in list(optical_tracker_service._TRACKERS.keys()):
            if k[0] == channel_key and k[1] not in active_ids:
                optical_tracker_service.remove_tracker(channel_key, k[1])

        # Initialize/Re-initialize trackers for active objects
        for track in all_tracks:
            if track.status == "active":
                # Increment hits
                hit_key = (channel_key, track.track_id)
                _TRACK_HITS[hit_key] = _TRACK_HITS.get(hit_key, 0) + 1
                _TRACK_MISSES[hit_key] = 0  # reset misses
                
                # Re-initialize optical tracker to anchor the position
                optical_tracker_service.init_tracker(channel_key, track.track_id, frame_np, track.bbox)

    else:
        logger.debug("Pipeline: Channel %s running OpenCV Optical Tracking at frame %d", channel_key, frame_count)
        # intermediate frames - run optical trackers
        for track in all_tracks:
            if track.status == "active":
                hit_key = (channel_key, track.track_id)
                # Ensure it has been initialized
                new_bbox = optical_tracker_service.update_tracker(channel_key, track.track_id, frame_np)
                if new_bbox is not None:
                    # Successfully updated bbox
                    track.bbox = new_bbox
                    # Recalculate center
                    track.center = [
                        int(round((new_bbox[0] + new_bbox[2]) / 2)),
                        int(round((new_bbox[1] + new_bbox[3]) / 2)),
                    ]
                    track.path.append(track.center)
                    track.path = track.path[-tracking_service.track_max_path_points():]
                    track.last_seen_at = now
                    _TRACK_MISSES[hit_key] = 0
                else:
                    # Failed to update tracker on this frame
                    _TRACK_MISSES[hit_key] = _TRACK_MISSES.get(hit_key, 0) + 1
                    logger.debug(
                        "Optical tracker missed track #%d (misses: %d)",
                        track.track_id,
                        _TRACK_MISSES[hit_key],
                    )

    # 2. Strict Expired & Lost Track Cleanup
    ttl = get_track_ttl_seconds()
    max_misses = get_track_max_misses()
    min_hits = get_track_min_hits()
    show_lost = get_show_lost_tracks()

    valid_objects = []

    for track in all_tracks:
        hit_key = (channel_key, track.track_id)
        
        # Check TTL
        time_since_seen = (now - track.last_seen_at).total_seconds()
        misses = _TRACK_MISSES.get(hit_key, 0)
        hits = _TRACK_HITS.get(hit_key, 1)

        # Mark lost or expired
        if time_since_seen > ttl or misses > max_misses:
            track.status = "expired"
        elif track.status == "lost" and not show_lost:
            track.status = "expired"

        if track.status == "active" and hits < min_hits:
            # Skip returning tracks that haven't hit the minimum confirmation threshold
            continue

        if track.status != "expired":
            valid_objects.append(track)

    # Active cache purge: write back only non-expired tracks to tracking_service global state
    tracking_service._TRACKS_BY_CHANNEL[channel_key] = [
        t for t in valid_objects if t.status != "expired"
    ]


    # 3. Apply Exponential Moving Average (EMA) BBox Smoothing
    alpha = get_bbox_smoothing_alpha()
    for track in valid_objects:
        if track.status == "active":
            smooth_key = (channel_key, track.track_id)
            prev_bbox = _SMOOTHED_BBOXES.get(smooth_key)
            if prev_bbox is None:
                _SMOOTHED_BBOXES[smooth_key] = [float(x) for x in track.bbox]
            else:
                curr_bbox = track.bbox
                smoothed = [
                    alpha * curr_bbox[0] + (1 - alpha) * prev_bbox[0],
                    alpha * curr_bbox[1] + (1 - alpha) * prev_bbox[1],
                    alpha * curr_bbox[2] + (1 - alpha) * prev_bbox[2],
                    alpha * curr_bbox[3] + (1 - alpha) * prev_bbox[3],
                ]
                _SMOOTHED_BBOXES[smooth_key] = smoothed
                # Convert back to integers for rendering
                track.bbox = [int(round(x)) for x in smoothed]
                track.center = [
                    int(round((track.bbox[0] + track.bbox[2]) / 2)),
                    int(round((track.bbox[1] + track.bbox[3]) / 2)),
                ]

    # 4. Update Zones & Dwell times
    zones = zone_service.load_zones(channel_key)
    zones_by_track_id = {
        obj.track_id: zone_service.get_object_zones(channel_key, obj.center)
        for obj in valid_objects
    }
    tracking_service.set_track_zones(channel_key, zones_by_track_id)

    for obj in valid_objects:
        if obj.status == "active":
            obj.dwell = dwell_service.update_zone_presence(
                track=obj,
                zone_ids=obj.zone_ids,
                now=now,
            )

    # 5. Sync Target Lock Status
    target_lock_service.sync_target_with_tracks(channel_key, valid_objects)
    focus_target_id = target_lock_service.get_target_status(channel_key)["track_id"]

    # 6. Event Processing
    event_result = event_service.process_tracking_result(
        channel=channel_key,
        objects=valid_objects,
        snapshot_path=snapshot_path,
        annotated_snapshot_path=None,
        zones=zones,
    )
    event_count = len(event_result["created_events"])

    # 7. Draw HUD Overlay
    from app.services import vision_worker_service
    worker_status = vision_worker_service.get_worker_status(channel_key)
    
    annotated_bytes = hud_overlay_service.draw_premium_hud(
        image_bytes=image_bytes,
        channel=channel_key,
        objects=valid_objects,
        zones=zones,
        updated_at=now,
        worker_status=worker_status,
        event_count=event_count,
        focus_target_id=focus_target_id,
        hud_style_override=hud_style_override,
    )

    # 8. Save annotated frame & tracks persistence
    from app.services import vision_overlay_service
    annotated_path = vision_overlay_service.save_latest_annotated_frame(
        channel_key, annotated_bytes
    )
    vision_persistence_service.save_tracks(channel_key, valid_objects)


    # Clean up smoothed bboxes and tracking states for expired tracks
    all_active_ids = {t.track_id for t in valid_objects if t.status == "active"}
    for k in list(_SMOOTHED_BBOXES.keys()):
        if k[0] == channel_key and k[1] not in all_active_ids:
            _SMOOTHED_BBOXES.pop(k, None)
            _TRACK_HITS.pop(k, None)
            _TRACK_MISSES.pop(k, None)

    target_info = target_lock_service.get_target_status(channel_key)

    state = {
        "channel": channel_key,
        "updated_at": now.isoformat(),
        "worker": worker_status,
        "target": target_info,
        "objects": [obj.to_api_dict() for obj in valid_objects if obj.status == "active"],
        "snapshot_path": snapshot_path,
        "annotated_frame_path": str(annotated_path),
        "events": event_result,
    }

    # Cache last state in vision_loop_service to maintain compatibility
    from app.services import vision_loop_service
    vision_loop_service._STATE_BY_CHANNEL[channel_key] = state

    return state


def reset_frame_pipeline_state() -> None:
    """Resets all frame pipeline cached states."""
    _FRAME_COUNTER.clear()
    _SMOOTHED_BBOXES.clear()
    _TRACK_HITS.clear()
    _TRACK_MISSES.clear()
    optical_tracker_service.reset_tracker_service()
    target_lock_service.reset_target_lock_service()
