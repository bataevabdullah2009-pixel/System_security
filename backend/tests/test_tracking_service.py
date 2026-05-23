from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services import tracking_service
from app.services.detection_service import BoundingBox, DetectionResult


def detection(x1: int, y1: int, x2: int, y2: int, class_name: str = "person") -> DetectionResult:
    return DetectionResult(
        class_name=class_name,
        confidence=0.91,
        bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
        channel="101",
        timestamp="2026-05-23T18:00:00",
    )


def setup_function() -> None:
    tracking_service.reset_tracker_state()


def test_new_detection_creates_new_track_id(monkeypatch) -> None:
    monkeypatch.setenv("TRACKING_ENABLED", "true")
    now = datetime.now(timezone.utc)

    tracks = tracking_service.update_tracks("101", [detection(10, 10, 50, 80)], now=now)

    assert len(tracks) == 1
    assert tracks[0].track_id == 1
    assert tracks[0].status == "active"


def test_similar_bbox_updates_same_track_id(monkeypatch) -> None:
    monkeypatch.setenv("TRACKING_ENABLED", "true")
    now = datetime.now(timezone.utc)

    first = tracking_service.update_tracks("101", [detection(10, 10, 50, 80)], now=now)[0]
    first_track_id = first.track_id
    first_center = list(first.center)
    second = tracking_service.update_tracks(
        "101",
        [detection(13, 12, 53, 82)],
        now=now + timedelta(seconds=1),
    )[0]

    assert second.track_id == first_track_id
    assert second.center != first_center


def test_track_gets_path(monkeypatch) -> None:
    monkeypatch.setenv("TRACKING_ENABLED", "true")
    now = datetime.now(timezone.utc)

    tracking_service.update_tracks("101", [detection(10, 10, 50, 80)], now=now)
    tracks = tracking_service.update_tracks(
        "101",
        [detection(20, 20, 60, 90)],
        now=now + timedelta(seconds=1),
    )

    assert len(tracks[0].path) == 2


def test_track_becomes_lost_after_ttl(monkeypatch) -> None:
    monkeypatch.setenv("TRACKING_ENABLED", "true")
    monkeypatch.setenv("TRACK_TTL_SECONDS", "1")
    now = datetime.now(timezone.utc)

    tracking_service.update_tracks("101", [detection(10, 10, 50, 80)], now=now)
    tracks = tracking_service.get_tracks("101", now=now + timedelta(seconds=2))

    assert tracks[0].status == "lost"
