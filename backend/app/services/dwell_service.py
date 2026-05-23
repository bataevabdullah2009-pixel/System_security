from __future__ import annotations

import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import select

from app.db.database import PROJECT_ROOT, session_scope
from app.db.models import VisionZonePresence
from app.services.detection_service import VEHICLE_CLASSES
from app.services.tracking_service import TrackedObject


def _load_env() -> None:
    load_dotenv(PROJECT_ROOT / ".env")


def dwell_enabled() -> bool:
    _load_env()
    return os.getenv("DWELL_ENABLED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def loitering_threshold_seconds() -> float:
    _load_env()
    raw = os.getenv("LOITERING_THRESHOLD_SECONDS", "30").strip()
    try:
        return float(raw)
    except ValueError:
        return 30.0


def update_zone_presence(
    track: TrackedObject,
    zone_ids: list[str],
    now: datetime | None = None,
) -> dict[str, float]:
    if not dwell_enabled():
        return {}

    now = now or datetime.now(timezone.utc)
    active_zone_ids = set(zone_ids)
    dwell_by_zone: dict[str, float] = {}

    with session_scope() as session:
        existing = session.scalars(
            select(VisionZonePresence)
            .where(VisionZonePresence.channel == track.channel)
            .where(VisionZonePresence.track_id == track.track_id)
            .where(VisionZonePresence.active.is_(True))
        ).all()
        existing_by_zone = {presence.zone_id: presence for presence in existing}

        for zone_id in active_zone_ids:
            presence = existing_by_zone.get(zone_id)
            if presence is None:
                presence = VisionZonePresence(
                    track_id=track.track_id,
                    channel=track.channel,
                    class_name=track.class_name,
                    zone_id=zone_id,
                    entered_at=now,
                    last_seen_at=now,
                    dwell_seconds=0.0,
                    active=True,
                    created_at=now,
                    updated_at=now,
                )
                session.add(presence)
            else:
                presence.class_name = track.class_name
                presence.last_seen_at = now
                entered_at = _as_utc(presence.entered_at)
                presence.dwell_seconds = max(0.0, (now - entered_at).total_seconds())
                presence.updated_at = now
            dwell_by_zone[zone_id] = float(presence.dwell_seconds)

        for zone_id, presence in existing_by_zone.items():
            if zone_id not in active_zone_ids:
                presence.active = False
                presence.last_seen_at = now
                entered_at = _as_utc(presence.entered_at)
                presence.dwell_seconds = max(0.0, (now - entered_at).total_seconds())
                presence.updated_at = now

    return dwell_by_zone


def get_dwell_seconds(track_id: int, zone_id: str) -> float:
    with session_scope() as session:
        presence = session.scalar(
            select(VisionZonePresence)
            .where(VisionZonePresence.track_id == int(track_id))
            .where(VisionZonePresence.zone_id == zone_id)
            .where(VisionZonePresence.active.is_(True))
            .order_by(VisionZonePresence.updated_at.desc())
            .limit(1)
        )
        if presence is None:
            return 0.0
        return float(presence.dwell_seconds)


def detect_loitering(track: TrackedObject, zone_id: str) -> bool:
    if not dwell_enabled():
        return False
    if track.class_name == "person":
        return (
            get_dwell_seconds(track.track_id, zone_id) >= loitering_threshold_seconds()
        )
    if track.class_name in VEHICLE_CLASSES:
        return (
            get_dwell_seconds(track.track_id, zone_id) >= loitering_threshold_seconds()
        )
    return False


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
