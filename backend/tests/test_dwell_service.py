from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db.database import init_db, reset_database_engine_cache
from app.services import dwell_service, tracking_service


def configure_db(monkeypatch, tmp_path) -> None:
    db_path = tmp_path / "dwell.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DWELL_ENABLED", "true")
    monkeypatch.setenv("LOITERING_THRESHOLD_SECONDS", "1")
    reset_database_engine_cache()
    init_db()


def make_track() -> tracking_service.TrackedObject:
    now = datetime.now(timezone.utc)
    return tracking_service.TrackedObject(
        track_id=1,
        channel="101",
        class_name="person",
        confidence=0.91,
        bbox=[10, 10, 50, 80],
        center=[30, 45],
        path=[[30, 45]],
        first_seen_at=now,
        last_seen_at=now,
        status="active",
        zone_ids=["cashier"],
    )


def test_dwell_time_is_counted(monkeypatch, tmp_path) -> None:
    configure_db(monkeypatch, tmp_path)
    track = make_track()
    now = datetime.now(timezone.utc)

    dwell_service.update_zone_presence(track, ["cashier"], now=now)
    dwell = dwell_service.update_zone_presence(
        track,
        ["cashier"],
        now=now + timedelta(seconds=2),
    )

    assert dwell["cashier"] >= 2
    assert dwell_service.get_dwell_seconds(track.track_id, "cashier") >= 2


def test_detect_loitering_after_threshold(monkeypatch, tmp_path) -> None:
    configure_db(monkeypatch, tmp_path)
    track = make_track()
    now = datetime.now(timezone.utc)

    dwell_service.update_zone_presence(track, ["cashier"], now=now)
    dwell_service.update_zone_presence(
        track, ["cashier"], now=now + timedelta(seconds=2)
    )

    assert dwell_service.detect_loitering(track, "cashier") is True
