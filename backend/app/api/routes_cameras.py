from __future__ import annotations

import logging
import time
from collections.abc import Generator

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse, StreamingResponse

from app.services import camera_service


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cameras", tags=["cameras"])


def _validate_channel(channel: str) -> str:
    if channel not in camera_service.HIKVISION_CHANNELS:
        allowed = ", ".join(camera_service.HIKVISION_CHANNELS)
        raise HTTPException(status_code=400, detail=f"Unsupported channel. Use one of: {allowed}")
    return channel


@router.get("/hikvision/diagnose")
def diagnose_hikvision_channels() -> list[dict[str, object]]:
    return camera_service.diagnose_all_channels()


@router.get("/hikvision/{channel}/snapshot")
def get_hikvision_snapshot(channel: str) -> Response:
    _validate_channel(channel)
    try:
        image_bytes, _path = camera_service.get_latest_snapshot(channel)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return Response(content=image_bytes, media_type="image/jpeg")


@router.get("/hikvision/{channel}/latest")
def get_hikvision_latest(channel: str) -> FileResponse:
    _validate_channel(channel)
    latest_path = camera_service.latest_snapshot_path(channel)
    if latest_path is None:
        raise HTTPException(status_code=404, detail="No latest snapshot saved yet")
    return FileResponse(latest_path, media_type="image/jpeg")


def _mjpeg_generator(channel: str) -> Generator[bytes, None, None]:
    boundary = b"--frame\r\n"
    while True:
        try:
            image_bytes, _path = camera_service.get_latest_snapshot(channel)
            yield (
                boundary
                + b"Content-Type: image/jpeg\r\n"
                + f"Content-Length: {len(image_bytes)}\r\n\r\n".encode("ascii")
                + image_bytes
                + b"\r\n"
            )
        except Exception as exc:
            logger.warning("MJPEG snapshot fetch failed for channel %s: %s", channel, exc)
            time.sleep(1)
            continue

        time.sleep(1)


@router.get("/hikvision/{channel}/stream.mjpg")
def stream_hikvision_mjpeg(channel: str) -> StreamingResponse:
    _validate_channel(channel)
    return StreamingResponse(
        _mjpeg_generator(channel),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
