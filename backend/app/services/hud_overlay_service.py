from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from dotenv import load_dotenv

from app.db.database import PROJECT_ROOT
from app.services import zone_service

logger = logging.getLogger(__name__)


def _load_env() -> None:
    load_dotenv(PROJECT_ROOT / ".env")


_HUD_STYLE: dict[str, str] = {}


def get_overlay_style(channel: str | None = None) -> str:
    _load_env()
    if channel is not None:
        style = _HUD_STYLE.get(str(channel))
        if style:
            return style
    return os.getenv("OVERLAY_STYLE", "clean_hud").strip().lower()


def set_hud_style(channel: str, style: str) -> None:
    _HUD_STYLE[str(channel)] = style.strip().lower()


def show_raw_boxes() -> bool:
    _load_env()
    return os.getenv("SHOW_RAW_BOXES", "false").strip().lower() in {"1", "true", "yes", "on"}


def show_zones_on_overlay() -> bool:
    _load_env()
    return os.getenv("SHOW_ZONES_ON_OVERLAY", "false").strip().lower() in {"1", "true", "yes", "on"}


def show_path_trail() -> bool:
    _load_env()
    return os.getenv("SHOW_PATH_TRAIL", "true").strip().lower() in {"1", "true", "yes", "on"}


def show_target_lock() -> bool:
    _load_env()
    return os.getenv("SHOW_TARGET_LOCK", "true").strip().lower() in {"1", "true", "yes", "on"}


def draw_premium_hud(
    image_bytes: bytes,
    channel: str,
    objects: list[Any],
    zones: list[dict[str, Any]],
    updated_at: datetime | None = None,
    worker_status: dict[str, Any] | None = None,
    event_count: int = 0,
    focus_target_id: int | None = None,
    hud_style_override: str | None = None,
) -> bytes:
    """Renders a premium Cyber-HUD security overlay on the camera frame."""
    # Decode image
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError("Could not decode image for HUD overlay")

    overlay = image.copy()
    h_img, w_img = image.shape[:2]

    # 1. Draw Zones (if enabled)
    draw_zones = show_zones_on_overlay()
    if draw_zones and zones:
        for zone in zones:
            polygon = zone.get("polygon", [])
            if not isinstance(polygon, list) or len(polygon) < 3:
                continue
            points = np.array(polygon, dtype=np.int32)
            cv2.fillPoly(overlay, [points], (150, 100, 30))  # Semi-transparent dark cyan/blue fill
            cv2.polylines(image, [points], True, (250, 160, 30), 1, cv2.LINE_AA)
            name = str(zone.get("name") or zone.get("id") or "zone")
            cv2.putText(
                image,
                f" ZONE: {name.upper()} ",
                tuple(points[0]),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (250, 160, 30),
                1,
                cv2.LINE_AA,
            )

        # Apply zones transparency
        image = cv2.addWeighted(overlay, 0.12, image, 0.88, 0)

    # 2. Draw Tracked Objects
    style = hud_style_override or get_overlay_style(channel)
    raw_boxes = show_raw_boxes()
    draw_trail = show_path_trail()


    for obj in objects:
        status = getattr(obj, "status", "active")
        if status in ("lost", "expired"):
            # Never draw lost/expired tracks in live HUD
            continue

        track_id = getattr(obj, "track_id", 0)
        class_name = getattr(obj, "class_name", "object")
        confidence = getattr(obj, "confidence", 0.0)
        bbox = getattr(obj, "bbox", [0, 0, 0, 0])
        center = getattr(obj, "center", [0, 0])
        path = getattr(obj, "path", [])
        zone_ids = getattr(obj, "zone_ids", [])
        dwell = getattr(obj, "dwell", {})

        is_locked = (focus_target_id is not None) and (track_id == focus_target_id)

        # Color Schemes (BGR)
        # Locked Target: Cyan (255, 235, 50)
        # Normal targets: Green (80, 220, 50) or Orange (50, 130, 240) depending on class
        if is_locked:
            color = (255, 235, 50)  # Bright Cyan
        elif class_name == "person":
            color = (80, 220, 50)  # Clean tech green
        else:
            color = (50, 130, 240)  # Vibrant orange/blue blend

        x1, y1, x2, y2 = [int(round(c)) for c in bbox]
        # Keep inside image bounds
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w_img - 1, x2), min(h_img - 1, y2)
        w, h = x2 - x1, y2 - y1

        # Skip drawing collapsed boxes
        if w <= 0 or h <= 0:
            continue

        # Draw box or corner brackets
        if raw_boxes or style == "basic":
            # Simple rectangle
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 1, cv2.LINE_AA)
        else:
            # Corner brackets (Tactical / Minimal style)
            # Bracket line length
            len_b = min(12, int(min(w, h) * 0.25))
            len_b = max(4, len_b)
            thick = 2 if is_locked else 1

            # Top-Left
            cv2.line(image, (x1, y1), (x1 + len_b, y1), color, thick, cv2.LINE_AA)
            cv2.line(image, (x1, y1), (x1, y1 + len_b), color, thick, cv2.LINE_AA)
            # Top-Right
            cv2.line(image, (x2, y1), (x2 - len_b, y1), color, thick, cv2.LINE_AA)
            cv2.line(image, (x2, y1), (x2, y1 + len_b), color, thick, cv2.LINE_AA)
            # Bottom-Left
            cv2.line(image, (x1, y2), (x1 + len_b, y2), color, thick, cv2.LINE_AA)
            cv2.line(image, (x1, y2), (x1, y2 - len_b), color, thick, cv2.LINE_AA)
            # Bottom-Right
            cv2.line(image, (x2, y2), (x2 - len_b, y2), color, thick, cv2.LINE_AA)
            cv2.line(image, (x2, y2), (x2, y2 - len_b), color, thick, cv2.LINE_AA)

            if is_locked:
                # Add outer lock indicators (corners slightly separated)
                offset = 3
                # Top-Left Outer
                cv2.line(image, (x1 - offset, y1 - offset), (x1 - offset + 6, y1 - offset), color, 1, cv2.LINE_AA)
                cv2.line(image, (x1 - offset, y1 - offset), (x1 - offset, y1 - offset + 6), color, 1, cv2.LINE_AA)
                # Bottom-Right Outer
                cv2.line(image, (x2 + offset, y2 + offset), (x2 + offset - 6, y2 + offset), color, 1, cv2.LINE_AA)
                cv2.line(image, (x2 + offset, y2 + offset), (x2 + offset, y2 + offset - 6), color, 1, cv2.LINE_AA)

        # Draw Center Reticle / Crosshair (Tactical/Minimal style)
        if style in ("tactical", "clean_hud") and len(center) == 2:
            cx, cy = int(center[0]), int(center[1])
            if 0 <= cx < w_img and 0 <= cy < h_img:
                # Small core circle
                cv2.circle(image, (cx, cy), 2, color, -1, cv2.LINE_AA)
                # Outer ticks
                t_sz = 6
                cv2.line(image, (cx - t_sz, cy), (cx + t_sz, cy), color, 1, cv2.LINE_AA)
                cv2.line(image, (cx, cy - t_sz), (cx, cy + t_sz), color, 1, cv2.LINE_AA)

        # Draw Path Trail (if enabled)
        if draw_trail and len(path) >= 2:
            pts = np.array(path, dtype=np.int32)
            # Draw gradient or thin trail
            cv2.polylines(image, [pts], False, color, 1, cv2.LINE_AA)

        # Labels
        zone_names = [zone_service.get_zone_name(channel, z_id) for z_id in zone_ids]
        zone_text = f" | {', '.join(zone_names)}" if zone_names else ""
        dwell_text = ""
        if dwell:
            max_dwell = max(dwell.values())
            dwell_text = f" dwell:{max_dwell:.1f}s"

        label = (
            f"{class_name.upper()} #{track_id} {confidence:.2f} "
            f"[{status.upper()}]{zone_text}{dwell_text}"
        )

        label_y = max(12, y1 - 6)
        if is_locked:
            # Draw double headers
            _draw_hud_label(image, "TARGET ACQUIRED (LOCKED)", x1, max(12, y1 - 22), color)
            _draw_hud_label(image, label, x1, label_y, color, alpha=0.95)
        else:
            _draw_hud_label(image, label, x1, label_y, color)

    # 3. Draw Header Dashboard HUD Strip
    timestamp = (updated_at or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    worker_running = bool((worker_status or {}).get("running"))
    updates_count = int((worker_status or {}).get("updates_count") or 0)
    measured_fps = (worker_status or {}).get("measured_fps")
    
    fps_text = f"fps:{measured_fps:.1f}" if isinstance(measured_fps, (int, float)) else "fps:--"
    worker_text = "worker:LIVE" if worker_running else "worker:STOP"
    
    header = (
        f"SMARTGUARD CAMERA {channel} | {timestamp} | {worker_text} | "
        f"{fps_text} | updates:{updates_count} | events:{event_count}"
    )
    _draw_hud_label(image, header, 10, 22, (255, 255, 255), background=(20, 20, 20), scale=0.45)

    # Encode to JPEG
    ok, encoded = cv2.imencode(".jpg", image)
    if not ok:
        raise RuntimeError("Could not encode vision annotated JPEG")
    return encoded.tobytes()


def _draw_hud_label(
    image: np.ndarray,
    text: str,
    x: int,
    y: int,
    color: tuple[int, int, int],
    background: tuple[int, int, int] = (15, 15, 15),
    scale: float = 0.45,
    alpha: float = 0.85,
) -> None:
    """Draws a clean modern cyber-hud text label with semi-transparent background."""
    font = cv2.FONT_HERSHEY_SIMPLEX
    thickness = 1
    (width, height), baseline = cv2.getTextSize(text, font, scale, thickness)
    
    top_left = (x, max(0, y - height - baseline - 4))
    bottom_right = (x + width + 6, y + baseline)
    
    # Overlay background transparency
    sub_img = image[top_left[1]:bottom_right[1], top_left[0]:bottom_right[0]]
    if sub_img.size > 0:
        rect_img = np.zeros_like(sub_img)
        rect_img[:] = background
        blend = cv2.addWeighted(rect_img, alpha, sub_img, 1.0 - alpha, 0)
        image[top_left[1]:bottom_right[1], top_left[0]:bottom_right[0]] = blend

    # Text outline
    cv2.putText(
        image,
        text,
        (x + 3, y - 2),
        font,
        scale,
        (10, 10, 10),
        thickness + 1,
        cv2.LINE_AA,
    )
    # Main text
    cv2.putText(
        image,
        text,
        (x + 3, y - 2),
        font,
        scale,
        color,
        thickness,
        cv2.LINE_AA,
    )
