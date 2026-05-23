from __future__ import annotations

import logging
import time
from collections.abc import Generator

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse

from app.services import (
    camera_service,
    detection_service,
    vision_loop_service,
    vision_worker_service,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/vision", tags=["vision"])


def _validate_channel(channel: str) -> str:
    if channel not in camera_service.HIKVISION_CHANNELS:
        allowed = ", ".join(camera_service.HIKVISION_CHANNELS)
        raise HTTPException(
            status_code=400, detail=f"Unsupported channel. Use one of: {allowed}"
        )
    return channel


@router.get("/hikvision/{channel}/state")
def get_hikvision_vision_state(channel: str) -> dict[str, object]:
    _validate_channel(channel)
    return vision_loop_service.get_state(channel)


@router.post("/hikvision/{channel}/update")
def update_hikvision_vision_state(channel: str) -> dict[str, object]:
    _validate_channel(channel)
    try:
        return vision_loop_service.update_once(channel)
    except detection_service.DetectionModelError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/hikvision/{channel}/worker/start")
def start_hikvision_vision_worker(channel: str) -> dict[str, object]:
    _validate_channel(channel)
    return vision_worker_service.start_worker(channel)


@router.post("/hikvision/{channel}/worker/stop")
def stop_hikvision_vision_worker(channel: str) -> dict[str, object]:
    _validate_channel(channel)
    return vision_worker_service.stop_worker(channel)


@router.get("/hikvision/{channel}/worker/status")
def get_hikvision_vision_worker_status(channel: str) -> dict[str, object]:
    _validate_channel(channel)
    return vision_worker_service.get_worker_status(channel)


@router.get("/hikvision/{channel}/annotated")
def get_hikvision_vision_annotated(channel: str) -> Response:
    _validate_channel(channel)
    image_bytes = vision_loop_service.latest_annotated_frame(channel)
    if image_bytes is None:
        try:
            vision_loop_service.update_once(channel)
            image_bytes = vision_loop_service.latest_annotated_frame(channel)
        except detection_service.DetectionModelError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
    if image_bytes is None:
        raise HTTPException(
            status_code=404, detail="No annotated vision frame saved yet"
        )
    return Response(content=image_bytes, media_type="image/jpeg")


def _mjpeg_generator(channel: str) -> Generator[bytes, None, None]:
    boundary = b"--frame\r\n"
    while True:
        try:
            vision_loop_service.update_once(channel)
            image_bytes = vision_loop_service.latest_annotated_frame(channel)
            if image_bytes is not None:
                yield (
                    boundary
                    + b"Content-Type: image/jpeg\r\n"
                    + f"Content-Length: {len(image_bytes)}\r\n\r\n".encode("ascii")
                    + image_bytes
                    + b"\r\n"
                )
        except Exception as exc:
            logger.warning(
                "Vision MJPEG update failed for channel %s: %s", channel, exc
            )
        time.sleep(1)


@router.get("/hikvision/{channel}/stream.mjpg")
def stream_hikvision_vision_mjpeg(channel: str) -> StreamingResponse:
    _validate_channel(channel)
    return StreamingResponse(
        _mjpeg_generator(channel),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
