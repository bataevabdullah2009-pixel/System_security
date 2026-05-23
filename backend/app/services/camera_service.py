from __future__ import annotations

from pathlib import Path

from app.services import hikvision_snapshot_service


HIKVISION_CHANNELS = ("101", "102", "201", "202")


def capture_fresh_snapshot(channel: int | str) -> tuple[bytes, Path, Path]:
    image_bytes = hikvision_snapshot_service.fetch_snapshot(channel)
    snapshot_path = hikvision_snapshot_service.save_snapshot_bytes(channel, image_bytes)
    latest_path = hikvision_snapshot_service.save_latest_snapshot(channel, image_bytes)
    return image_bytes, snapshot_path, latest_path


def get_latest_snapshot(channel: int | str) -> tuple[bytes, Path]:
    image_bytes, snapshot_path, latest_path = capture_fresh_snapshot(channel)
    return image_bytes, latest_path if latest_path.exists() else snapshot_path


def latest_snapshot_path(channel: int | str) -> Path | None:
    path = hikvision_snapshot_service.LATEST_DIR / f"hikvision_ch{channel}_latest.jpg"
    if path.exists():
        return path
    return None


def test_camera_channel(channel: int | str) -> dict[str, object]:
    try:
        snapshot_path = hikvision_snapshot_service.save_snapshot(channel)
        image_bytes = snapshot_path.read_bytes()
        hikvision_snapshot_service.save_latest_snapshot(channel, image_bytes)
        return {
            "channel": int(channel),
            "status": "online",
            "source_type": "hikvision_isapi_snapshot",
            "snapshot_path": str(snapshot_path),
            "error": None,
        }
    except Exception as exc:
        return {
            "channel": int(channel),
            "status": "offline",
            "source_type": "hikvision_isapi_snapshot",
            "snapshot_path": None,
            "error": str(exc),
        }


def diagnose_all_channels() -> list[dict[str, object]]:
    return [test_camera_channel(channel) for channel in HIKVISION_CHANNELS]
