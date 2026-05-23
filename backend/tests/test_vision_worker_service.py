from __future__ import annotations

import time

from app.services import vision_loop_service, vision_worker_service


def setup_function() -> None:
    vision_worker_service.reset_worker_state()


def teardown_function() -> None:
    vision_worker_service.reset_worker_state()


def test_worker_start_stop_status(monkeypatch) -> None:
    monkeypatch.setenv("VISION_WORKER_INTERVAL_SECONDS", "0.1")
    monkeypatch.setattr(
        vision_loop_service,
        "update_once",
        lambda channel: {"channel": str(channel), "objects": []},
    )

    started = vision_worker_service.start_worker("101")
    time.sleep(0.25)
    status = vision_worker_service.get_worker_status("101")
    stopped = vision_worker_service.stop_worker("101")

    assert started["running"] is True
    assert status["updates_count"] >= 1
    assert status["last_error"] is None
    assert stopped["running"] is False


def test_worker_keeps_backend_alive_on_camera_error(monkeypatch) -> None:
    monkeypatch.setenv("VISION_WORKER_INTERVAL_SECONDS", "0.1")

    def fail_update(channel):
        raise RuntimeError("camera unavailable")

    monkeypatch.setattr(vision_loop_service, "update_once", fail_update)

    vision_worker_service.start_worker("101")
    time.sleep(0.25)
    status = vision_worker_service.get_worker_status("101")
    stopped = vision_worker_service.stop_worker("101")

    assert status["running"] is True
    assert "camera unavailable" in str(status["last_error"])
    assert stopped["running"] is False
