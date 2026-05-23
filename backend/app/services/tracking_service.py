from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import count

from dotenv import load_dotenv

from app.db.database import PROJECT_ROOT
from app.services.detection_service import DetectionResult


@dataclass
class TrackedObject:
    track_id: int
    channel: str
    class_name: str
    confidence: float
    bbox: list[int]
    center: list[int]
    path: list[list[int]]
    first_seen_at: datetime
    last_seen_at: datetime
    status: str = "active"
    zone_ids: list[str] = field(default_factory=list)
    dwell: dict[str, float] = field(default_factory=dict)

    def to_api_dict(self) -> dict[str, object]:
        return {
            "track_id": self.track_id,
            "channel": self.channel,
            "class_name": self.class_name,
            "confidence": round(float(self.confidence), 4),
            "bbox": self.bbox,
            "center": self.center,
            "path": self.path,
            "first_seen_at": self.first_seen_at.isoformat(),
            "last_seen_at": self.last_seen_at.isoformat(),
            "status": self.status,
            "zone_ids": self.zone_ids,
            "dwell": {
                zone_id: round(seconds, 2) for zone_id, seconds in self.dwell.items()
            },
        }


_TRACKS_BY_CHANNEL: dict[str, list[TrackedObject]] = {}
_TRACK_ID_SEQUENCE = count(1)


def _load_env() -> None:
    load_dotenv(PROJECT_ROOT / ".env")


def tracking_enabled() -> bool:
    _load_env()
    return os.getenv("TRACKING_ENABLED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def track_ttl_seconds() -> float:
    return _float_env("TRACK_TTL_SECONDS", 10.0)


def track_max_path_points() -> int:
    return max(1, int(_float_env("TRACK_MAX_PATH_POINTS", 30.0)))


def track_iou_threshold() -> float:
    return _float_env("TRACK_IOU_THRESHOLD", 0.3)


def track_distance_threshold() -> float:
    return _float_env("TRACK_DISTANCE_THRESHOLD", 120.0)


def reset_tracker_state() -> None:
    global _TRACK_ID_SEQUENCE
    _TRACKS_BY_CHANNEL.clear()
    _TRACK_ID_SEQUENCE = count(1)


def update_tracks(
    channel: int | str,
    detections: list[DetectionResult],
    now: datetime | None = None,
) -> list[TrackedObject]:
    now = now or datetime.now(timezone.utc)
    channel_key = str(channel)

    if not tracking_enabled():
        _TRACKS_BY_CHANNEL[channel_key] = []
        return []

    tracks = _TRACKS_BY_CHANNEL.setdefault(channel_key, [])
    _mark_lost_tracks(tracks, now)
    matched_track_ids: set[int] = set()

    for detection in detections:
        bbox = _bbox_to_list(detection)
        center = _bbox_center(bbox)
        match = _find_best_match(
            tracks, detection.class_name, bbox, center, matched_track_ids
        )

        if match is None:
            tracks.append(_new_track(channel_key, detection, bbox, center, now))
            continue

        match.class_name = detection.class_name
        match.confidence = float(detection.confidence)
        match.bbox = bbox
        match.center = center
        match.path.append(center)
        match.path = match.path[-track_max_path_points() :]
        match.last_seen_at = now
        match.status = "active"
        matched_track_ids.add(match.track_id)

    _mark_lost_tracks(tracks, now)
    return list(tracks)


def get_tracks(channel: int | str, now: datetime | None = None) -> list[TrackedObject]:
    now = now or datetime.now(timezone.utc)
    tracks = _TRACKS_BY_CHANNEL.get(str(channel), [])
    _mark_lost_tracks(tracks, now)
    return list(tracks)


def set_track_zones(
    channel: int | str, zones_by_track_id: dict[int, list[str]]
) -> None:
    for track in _TRACKS_BY_CHANNEL.get(str(channel), []):
        if track.track_id in zones_by_track_id:
            track.zone_ids = zones_by_track_id[track.track_id]


def _new_track(
    channel: str,
    detection: DetectionResult,
    bbox: list[int],
    center: list[int],
    now: datetime,
) -> TrackedObject:
    return TrackedObject(
        track_id=next(_TRACK_ID_SEQUENCE),
        channel=channel,
        class_name=detection.class_name,
        confidence=float(detection.confidence),
        bbox=bbox,
        center=center,
        path=[center],
        first_seen_at=now,
        last_seen_at=now,
        status="active",
    )


def _find_best_match(
    tracks: list[TrackedObject],
    class_name: str,
    bbox: list[int],
    center: list[int],
    matched_track_ids: set[int],
) -> TrackedObject | None:
    best_track: TrackedObject | None = None
    best_score = -1.0

    for track in tracks:
        if track.status != "active":
            continue
        if track.track_id in matched_track_ids:
            continue
        if track.class_name != class_name:
            continue

        iou = bbox_iou(track.bbox, bbox)
        distance = center_distance(track.center, center)
        if iou >= track_iou_threshold():
            score = 1.0 + iou
        elif distance <= track_distance_threshold():
            score = 1.0 - (distance / max(track_distance_threshold(), 1.0))
        else:
            continue

        if score > best_score:
            best_score = score
            best_track = track

    return best_track


def _mark_lost_tracks(tracks: list[TrackedObject], now: datetime) -> None:
    ttl = track_ttl_seconds()
    for track in tracks:
        if (
            track.status == "active"
            and (now - track.last_seen_at).total_seconds() > ttl
        ):
            track.status = "lost"


def _bbox_to_list(detection: DetectionResult) -> list[int]:
    bbox = detection.bbox
    return [int(bbox.x1), int(bbox.y1), int(bbox.x2), int(bbox.y2)]


def _bbox_center(bbox: list[int]) -> list[int]:
    return [int(round((bbox[0] + bbox[2]) / 2)), int(round((bbox[1] + bbox[3]) / 2))]


def bbox_iou(first: list[int], second: list[int]) -> float:
    x1 = max(first[0], second[0])
    y1 = max(first[1], second[1])
    x2 = min(first[2], second[2])
    y2 = min(first[3], second[3])
    inter_width = max(0, x2 - x1)
    inter_height = max(0, y2 - y1)
    intersection = inter_width * inter_height
    first_area = max(0, first[2] - first[0]) * max(0, first[3] - first[1])
    second_area = max(0, second[2] - second[0]) * max(0, second[3] - second[1])
    union = first_area + second_area - intersection
    if union <= 0:
        return 0.0
    return intersection / union


def center_distance(first: list[int], second: list[int]) -> float:
    return ((first[0] - second[0]) ** 2 + (first[1] - second[1]) ** 2) ** 0.5


def _float_env(name: str, default: float) -> float:
    _load_env()
    raw = os.getenv(name, str(default)).strip()
    try:
        return float(raw)
    except ValueError:
        return default
