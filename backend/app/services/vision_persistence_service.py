from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.database import session_scope
from app.db.models import VisionTrack, VisionTrackPoint
from app.services.tracking_service import TrackedObject


def save_tracks(channel: int | str, objects: list[TrackedObject]) -> None:
    channel_key = str(channel)
    now = datetime.now(timezone.utc)
    with session_scope() as session:
        for obj in objects:
            track = session.scalar(
                select(VisionTrack)
                .where(VisionTrack.channel == channel_key)
                .where(VisionTrack.track_id == obj.track_id)
                .limit(1)
            )
            if track is None:
                track = VisionTrack(
                    track_id=obj.track_id,
                    channel=channel_key,
                    class_name=obj.class_name,
                    status=obj.status,
                    confidence=float(obj.confidence),
                    bbox_json=json.dumps(obj.bbox),
                    center_json=json.dumps(obj.center),
                    zone_ids_json=json.dumps(obj.zone_ids),
                    first_seen_at=obj.first_seen_at,
                    last_seen_at=obj.last_seen_at,
                    created_at=now,
                    updated_at=now,
                )
                session.add(track)
            else:
                track.class_name = obj.class_name
                track.status = obj.status
                track.confidence = float(obj.confidence)
                track.bbox_json = json.dumps(obj.bbox)
                track.center_json = json.dumps(obj.center)
                track.zone_ids_json = json.dumps(obj.zone_ids)
                track.first_seen_at = obj.first_seen_at
                track.last_seen_at = obj.last_seen_at
                track.updated_at = now

            session.add(
                VisionTrackPoint(
                    track_id=obj.track_id,
                    channel=channel_key,
                    x=int(obj.center[0]),
                    y=int(obj.center[1]),
                    created_at=obj.last_seen_at,
                )
            )


def list_saved_tracks(channel: int | str) -> list[dict[str, object]]:
    with session_scope() as session:
        tracks = session.scalars(
            select(VisionTrack)
            .where(VisionTrack.channel == str(channel))
            .order_by(VisionTrack.track_id)
        ).all()
        return [
            {
                "track_id": track.track_id,
                "channel": track.channel,
                "class_name": track.class_name,
                "status": track.status,
                "confidence": track.confidence,
                "bbox": json.loads(track.bbox_json or "[]"),
                "center": json.loads(track.center_json or "[]"),
                "zone_ids": json.loads(track.zone_ids_json or "[]"),
                "first_seen_at": track.first_seen_at,
                "last_seen_at": track.last_seen_at,
            }
            for track in tracks
        ]
