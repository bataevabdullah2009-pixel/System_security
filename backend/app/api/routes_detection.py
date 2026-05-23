from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from app.services import camera_service, detection_service, event_candidate_service


router = APIRouter(prefix="/api/detection", tags=["detection"])


def _validate_channel(channel: str) -> str:
    if channel not in camera_service.HIKVISION_CHANNELS:
        allowed = ", ".join(camera_service.HIKVISION_CHANNELS)
        raise HTTPException(status_code=400, detail=f"Unsupported channel. Use one of: {allowed}")
    return channel


def _run_detection(channel: str) -> dict[str, object]:
    image_bytes, snapshot_path, _latest_path = camera_service.capture_fresh_snapshot(channel)
    detections = detection_service.detect_objects(
        image_bytes=image_bytes,
        channel=channel,
        snapshot_path=str(snapshot_path),
    )
    annotated_path = detection_service.save_annotated_snapshot(channel, image_bytes, detections)
    detections_with_paths = [
        detection_service.DetectionResult(
            class_name=detection.class_name,
            confidence=detection.confidence,
            bbox=detection.bbox,
            channel=detection.channel,
            timestamp=detection.timestamp,
            snapshot_path=str(snapshot_path),
            annotated_snapshot_path=str(annotated_path),
        )
        for detection in detections
    ]
    return {
        "channel": channel,
        "source": "hikvision_isapi_snapshot",
        "snapshot_path": str(snapshot_path),
        "annotated_snapshot_path": str(annotated_path),
        "detections": [detection.to_api_dict() for detection in detections_with_paths],
        "event_candidates": event_candidate_service.build_event_candidates(detections),
    }


@router.get("/hikvision/diagnose")
def diagnose_detection_channels() -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for channel in camera_service.HIKVISION_CHANNELS:
        try:
            detection_response = _run_detection(channel)
            detections = detection_response["detections"]
            count_person = sum(1 for item in detections if item["class_name"] == "person")
            count_vehicle = sum(
                1
                for item in detections
                if item["class_name"] in detection_service.VEHICLE_CLASSES
            )
            results.append(
                {
                    "channel": channel,
                    "status": "online",
                    "count_person": count_person,
                    "count_vehicle": count_vehicle,
                    "annotated_snapshot_path": detection_response["annotated_snapshot_path"],
                    "error": None,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "channel": channel,
                    "status": "offline",
                    "count_person": 0,
                    "count_vehicle": 0,
                    "annotated_snapshot_path": None,
                    "error": str(exc),
                }
            )
    return results


@router.get("/hikvision/{channel}")
def detect_hikvision_channel(channel: str) -> dict[str, object]:
    _validate_channel(channel)
    try:
        return _run_detection(channel)
    except detection_service.DetectionModelError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/hikvision/{channel}/annotated")
def detect_hikvision_channel_annotated(channel: str) -> Response:
    _validate_channel(channel)
    try:
        image_bytes, snapshot_path, _latest_path = camera_service.capture_fresh_snapshot(channel)
        detections = detection_service.detect_objects(
            image_bytes=image_bytes,
            channel=channel,
            snapshot_path=str(snapshot_path),
        )
        annotated_bytes = detection_service.draw_detections(image_bytes, detections)
        detection_service.save_annotated_snapshot(channel, image_bytes, detections)
    except detection_service.DetectionModelError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return Response(content=annotated_bytes, media_type="image/jpeg")
