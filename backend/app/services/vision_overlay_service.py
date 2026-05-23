from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from app.db.database import PROJECT_ROOT
from app.services.tracking_service import TrackedObject
from app.services import zone_service

STORAGE_ROOT = PROJECT_ROOT / "storage"
VISION_LATEST_DIR = STORAGE_ROOT / "vision" / "latest"


def draw_premium_overlay(
    image_bytes: bytes,
    channel: int | str,
    objects: list[TrackedObject],
    zones: list[dict[str, object]],
    updated_at: datetime | None = None,
    worker_status: dict[str, object] | None = None,
    event_count: int = 0,
) -> bytes:
    image = _decode_image(image_bytes)
    overlay = image.copy()

    for zone in zones:
        polygon = zone.get("polygon", [])
        if not isinstance(polygon, list) or len(polygon) < 3:
            continue
        points = np.array(polygon, dtype=np.int32)
        cv2.fillPoly(overlay, [points], (50, 180, 255))
        cv2.polylines(image, [points], True, (30, 160, 255), 2, cv2.LINE_AA)
        name = str(zone.get("name") or zone.get("id") or "zone")
        cv2.putText(
            image,
            name,
            tuple(points[0]),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (30, 160, 255),
            2,
            cv2.LINE_AA,
        )

    image = cv2.addWeighted(overlay, 0.18, image, 0.82, 0)

    for obj in objects:
        color = (50, 220, 80) if obj.class_name == "person" else (255, 170, 40)
        x1, y1, x2, y2 = obj.bbox
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        zone_names = [
            zone_service.get_zone_name(channel, zone_id) for zone_id in obj.zone_ids
        ]
        zone_text = f" | {', '.join(zone_names)}" if zone_names else ""
        dwell_text = _format_dwell(obj.dwell)
        label = (
            f"{obj.class_name} #{obj.track_id} {obj.confidence:.2f} "
            f"{obj.status}{zone_text}{dwell_text}"
        )
        _draw_label(image, label, x1, max(18, y1 - 8), color)

        if len(obj.path) >= 2:
            points = np.array(obj.path, dtype=np.int32)
            cv2.polylines(image, [points], False, color, 2, cv2.LINE_AA)
        cv2.circle(image, tuple(obj.center), 4, color, -1, cv2.LINE_AA)

    timestamp = (updated_at or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    worker_running = bool((worker_status or {}).get("running"))
    updates_count = int((worker_status or {}).get("updates_count") or 0)
    worker_text = "worker:on" if worker_running else "worker:off"
    header = (
        f"Channel {channel} | {timestamp} | {worker_text} "
        f"updates:{updates_count} events:{event_count}"
    )
    _draw_label(image, header, 12, 26, (255, 255, 255), background=(30, 30, 30))

    ok, encoded = cv2.imencode(".jpg", image)
    if not ok:
        raise RuntimeError("Could not encode vision annotated JPEG")
    return encoded.tobytes()


def save_latest_annotated_frame(channel: int | str, image_bytes: bytes) -> Path:
    VISION_LATEST_DIR.mkdir(parents=True, exist_ok=True)
    path = VISION_LATEST_DIR / f"channel_{channel}.jpg"
    path.write_bytes(image_bytes)
    return path


def latest_annotated_frame_path(channel: int | str) -> Path | None:
    path = VISION_LATEST_DIR / f"channel_{channel}.jpg"
    if path.exists():
        return path
    return None


def _decode_image(image_bytes: bytes):
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError("Could not decode image for vision overlay")
    return image


def _draw_label(
    image,
    text: str,
    x: int,
    y: int,
    color: tuple[int, int, int],
    background: tuple[int, int, int] = (20, 20, 20),
) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.55
    thickness = 2
    (width, height), baseline = cv2.getTextSize(text, font, scale, thickness)
    top_left = (x, max(0, y - height - baseline - 4))
    bottom_right = (x + width + 8, y + baseline)
    cv2.rectangle(image, top_left, bottom_right, background, -1)
    cv2.putText(image, text, (x + 4, y - 4), font, scale, color, thickness, cv2.LINE_AA)


def _format_dwell(dwell: dict[str, float]) -> str:
    if not dwell:
        return ""
    max_seconds = max(dwell.values())
    return f" dwell:{max_seconds:.1f}s"
