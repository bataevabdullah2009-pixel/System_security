from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
import pytest
import cv2
import numpy as np

from app.services import (
    target_lock_service,
    optical_tracker_service,
    hud_overlay_service,
    frame_pipeline_service,
    tracking_service,
    vision_worker_service,
    vision_loop_service,
)
from app.services.tracking_service import TrackedObject
from app.services.detection_service import BoundingBox, DetectionResult


@pytest.fixture(autouse=True)
def setup_teardown():
    # Setup before each test
    target_lock_service.reset_target_lock_service()
    optical_tracker_service.reset_tracker_service()
    frame_pipeline_service.reset_frame_pipeline_state()
    tracking_service.reset_tracker_state()
    vision_loop_service.reset_vision_state()
    vision_worker_service.reset_worker_state()
    yield
    # Cleanup after each test
    target_lock_service.reset_target_lock_service()
    optical_tracker_service.reset_tracker_service()
    frame_pipeline_service.reset_frame_pipeline_state()
    tracking_service.reset_tracker_state()
    vision_loop_service.reset_vision_state()
    vision_worker_service.reset_worker_state()


def test_target_lock_by_id():
    """Verify target can be locked by specific track ID."""
    state = target_lock_service.lock_target_by_id(
        channel="101", track_id=42, class_name="person", status="active"
    )
    assert state["locked"] is True
    assert state["track_id"] == 42
    assert state["class_name"] == "person"
    assert state["status"] == "active"

    status = target_lock_service.get_target_status("101")
    assert status["locked"] is True
    assert status["track_id"] == 42


def test_target_lock_by_click_coordinates():
    """Verify that coordinate click locks onto the nearest active track center."""
    now = datetime.now(timezone.utc)
    # Track 1: center at [100, 100]
    track1 = TrackedObject(
        track_id=1,
        channel="101",
        class_name="person",
        confidence=0.88,
        bbox=[80, 80, 120, 120],
        center=[100, 100],
        path=[[100, 100]],
        first_seen_at=now,
        last_seen_at=now,
        status="active",
    )
    # Track 2: center at [300, 300]
    track2 = TrackedObject(
        track_id=2,
        channel="101",
        class_name="car",
        confidence=0.92,
        bbox=[280, 280, 320, 320],
        center=[300, 300],
        path=[[300, 300]],
        first_seen_at=now,
        last_seen_at=now,
        status="active",
    )

    active_tracks = [track1, track2]

    # Click close to Track 1
    state = target_lock_service.lock_target_by_coordinates(
        channel="101", x=105, y=95, active_objects=active_tracks
    )
    assert state["locked"] is True
    assert state["track_id"] == 1
    assert state["class_name"] == "person"

    # Click close to Track 2
    state2 = target_lock_service.lock_target_by_coordinates(
        channel="101", x=290, y=310, active_objects=active_tracks
    )
    assert state2["locked"] is True
    assert state2["track_id"] == 2
    assert state2["class_name"] == "car"


def test_clear_target():
    """Verify that target lock can be successfully cleared."""
    target_lock_service.lock_target_by_id("101", 5, "dog")
    statusBefore = target_lock_service.get_target_status("101")
    assert statusBefore["locked"] is True

    cleared = target_lock_service.clear_target("101")
    assert cleared["locked"] is False
    assert cleared["track_id"] is None

    statusAfter = target_lock_service.get_target_status("101")
    assert statusAfter["locked"] is False


def test_lost_target_disappears_from_overlay_and_expired_tracks(monkeypatch):
    """Verify that tracks exceeding TTL or misses are marked as expired and disappear."""
    monkeypatch.setenv("TRACK_TTL_SECONDS", "1.5")
    now = datetime.now(timezone.utc)
    track = TrackedObject(
        track_id=1,
        channel="101",
        class_name="person",
        confidence=0.88,
        bbox=[10, 10, 50, 50],
        center=[30, 30],
        path=[[30, 30]],
        first_seen_at=now - timedelta(seconds=10),
        last_seen_at=now - timedelta(seconds=5),  # Last seen 5 seconds ago (TTL is 1.5s)
        status="active",
    )

    # Put in global tracker state
    tracking_service._TRACKS_BY_CHANNEL["101"] = [track]

    # Run frame pipeline processing (with force_detection=False to skip YOLO and run optical update)
    # Generate dummy image bytes (120x160 RGB encoded to JPEG)
    img = np.zeros((120, 160, 3), dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", img)
    assert ok
    image_bytes = encoded.tobytes()

    state = frame_pipeline_service.process_frame(
        channel="101",
        image_bytes=image_bytes,
        now=now,
        force_detection=False,
    )

    # The track should be marked expired/lost and NOT included in the returned objects
    assert len(state["objects"]) == 0
    assert track.status == "expired"



def test_overlay_does_not_draw_zones_by_default():
    """Verify zone drawing is disabled by default."""
    assert hud_overlay_service.show_zones_on_overlay() is False


def test_hud_overlay_returns_valid_jpeg():
    """Verify premium HUD overlay produces a valid JPEG image."""
    img = np.zeros((120, 160, 3), dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", img)
    assert ok
    image_bytes = encoded.tobytes()

    now = datetime.now(timezone.utc)
    track = TrackedObject(
        track_id=1,
        channel="101",
        class_name="person",
        confidence=0.88,
        bbox=[10, 10, 50, 50],
        center=[30, 30],
        path=[[30, 30]],
        first_seen_at=now,
        last_seen_at=now,
        status="active",
    )

    hud_bytes = hud_overlay_service.draw_premium_hud(
        image_bytes=image_bytes,
        channel="101",
        objects=[track],
        zones=[],
        updated_at=now,
    )

    assert hud_bytes.startswith(b"\xff\xd8")  # JPEG SOI
    assert len(hud_bytes) > 100


def test_worker_cannot_double_start():
    """Verify starting same worker twice returns existing running worker and does not double spawn."""
    vision_worker_service.start_worker("101")
    status1 = vision_worker_service.get_worker_status("101")
    assert status1["running"] is True

    # Start again
    status2 = vision_worker_service.start_worker("101")
    assert status2["running"] is True
    
    # Stop worker
    vision_worker_service.stop_worker("101")
    status3 = vision_worker_service.get_worker_status("101")
    assert status3["running"] is False


def test_state_includes_target_object():
    """Verify that process_frame returns target lock details in state dictionary."""
    img = np.zeros((120, 160, 3), dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", img)
    assert ok
    image_bytes = encoded.tobytes()

    target_lock_service.lock_target_by_id("101", 1, "car")

    state = frame_pipeline_service.process_frame(
        channel="101",
        image_bytes=image_bytes,
        now=datetime.now(timezone.utc),
        force_detection=True,
    )

    assert "target" in state
    assert state["target"]["locked"] is True
    assert state["target"]["track_id"] == 1
    assert state["target"]["class_name"] == "car"


def test_expired_tracks_are_deleted_from_global_state(monkeypatch):
    """Verify that expired tracks are completely deleted from tracking_service._TRACKS_BY_CHANNEL."""
    monkeypatch.setenv("TRACK_TTL_SECONDS", "1.5")
    now = datetime.now(timezone.utc)
    track = TrackedObject(
        track_id=42,
        channel="101",
        class_name="person",
        confidence=0.88,
        bbox=[10, 10, 50, 50],
        center=[30, 30],
        path=[[30, 30]],
        first_seen_at=now - timedelta(seconds=10),
        last_seen_at=now - timedelta(seconds=5),
        status="active",
    )
    tracking_service._TRACKS_BY_CHANNEL["101"] = [track]

    img = np.zeros((120, 160, 3), dtype=np.uint8)
    ok, encoded = cv2.imencode(".jpg", img)
    assert ok
    image_bytes = encoded.tobytes()

    frame_pipeline_service.process_frame(
        channel="101",
        image_bytes=image_bytes,
        now=now,
        force_detection=False,
    )

    # Verify cache purge
    tracks_in_cache = tracking_service._TRACKS_BY_CHANNEL.get("101", [])
    assert len(tracks_in_cache) == 0


def test_no_duplicate_tracks_for_same_object():
    """Verify that similar bounding boxes update the same track ID instead of duplicating."""
    now = datetime.now(timezone.utc)
    
    det1 = DetectionResult(
        class_name="person",
        confidence=0.91,
        bbox=BoundingBox(x1=10, y1=10, x2=50, y2=80),
        channel="101",
        timestamp=now.isoformat(),
    )
    tracks1 = tracking_service.update_tracks("101", [det1], now=now)
    assert len(tracks1) == 1
    track_id = tracks1[0].track_id

    det2 = DetectionResult(
        class_name="person",
        confidence=0.95,
        bbox=BoundingBox(x1=13, y1=12, x2=53, y2=82),
        channel="101",
        timestamp=(now + timedelta(seconds=1)).isoformat(),
    )
    tracks2 = tracking_service.update_tracks("101", [det2], now=now + timedelta(seconds=1))
    assert len(tracks2) == 1
    assert tracks2[0].track_id == track_id


