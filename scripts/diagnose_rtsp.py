from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = PROJECT_ROOT / "storage" / "snapshots"
CHANNELS = ("101", "102", "201", "202")
MAX_SECONDS_PER_URL = 10.0
MAX_FRAMES_PER_URL = 20


@dataclass(frozen=True)
class HikvisionConfig:
    host: str
    user: str
    password: str
    port: int


def load_config() -> HikvisionConfig | None:
    load_dotenv(PROJECT_ROOT / ".env")

    host = os.getenv("HIKVISION_HOST", "").strip()
    user = os.getenv("HIKVISION_USER", "").strip()
    password = os.getenv("HIKVISION_PASSWORD", "")
    port_raw = os.getenv("HIKVISION_RTSP_PORT", "554").strip()

    missing = []
    if not host:
        missing.append("HIKVISION_HOST")
    if not user:
        missing.append("HIKVISION_USER")
    if not password:
        missing.append("HIKVISION_PASSWORD")

    if missing:
        print(f"ERROR: Missing required .env values: {', '.join(missing)}")
        print_env_example()
        return None

    try:
        port = int(port_raw)
    except ValueError:
        print(f"ERROR: HIKVISION_RTSP_PORT must be an integer, got: {port_raw!r}")
        return None

    return HikvisionConfig(host=host, user=user, password=password, port=port)


def print_env_example() -> None:
    print(
        "\nAdd these values to .env:\n"
        "HIKVISION_HOST=192.168.0.102\n"
        "HIKVISION_USER=admin\n"
        "HIKVISION_PASSWORD=your_password_here\n"
        "HIKVISION_RTSP_PORT=554\n"
    )


def build_rtsp_url(config: HikvisionConfig, channel: str, mask_password: bool = False) -> str:
    user = quote(config.user, safe="")
    password = "***" if mask_password else quote(config.password, safe="")
    return (
        f"rtsp://{user}:{password}@{config.host}:{config.port}"
        f"/Streaming/Channels/{channel}"
    )


def print_codec_hint() -> None:
    print(
        "Hint: if frame is None or looks gray, check camera/NVR encoding settings. "
        "Use H.264 instead of H.265, H.265+, or Smart Codec for Main Stream and Sub Stream."
    )


def frame_looks_gray(frame) -> bool:
    if frame is None:
        return True
    if len(frame.shape) < 3 or frame.shape[2] < 3:
        return True

    import cv2

    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    saturation_mean = float(hsv[:, :, 1].mean())

    blue = frame[:, :, 0].astype("int16")
    green = frame[:, :, 1].astype("int16")
    red = frame[:, :, 2].astype("int16")
    channel_delta = float(
        (
            abs(blue - green).mean()
            + abs(blue - red).mean()
            + abs(green - red).mean()
        )
        / 3.0
    )

    return saturation_mean < 5.0 and channel_delta < 3.0


def open_capture(cv2, rtsp_url: str):
    params = []
    if hasattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC"):
        params.extend([cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(MAX_SECONDS_PER_URL * 1000)])
    if hasattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC"):
        params.extend([cv2.CAP_PROP_READ_TIMEOUT_MSEC, int(MAX_SECONDS_PER_URL * 1000)])

    if params:
        return cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG, params)

    return cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)


def diagnose_channel(cv2, config: HikvisionConfig, channel: str) -> bool:
    rtsp_url = build_rtsp_url(config, channel)
    masked_url = build_rtsp_url(config, channel, mask_password=True)

    print(f"\nChecking channel {channel}")
    print(f"URL: {masked_url}")

    started_at = time.monotonic()
    capture = open_capture(cv2, rtsp_url)

    if not capture.isOpened():
        print("FAILED: OpenCV CAP_FFMPEG could not open the stream.")
        print_codec_hint()
        capture.release()
        return False

    frame = None
    attempts = 0
    while attempts < MAX_FRAMES_PER_URL and time.monotonic() - started_at <= MAX_SECONDS_PER_URL:
        attempts += 1
        ok, candidate = capture.read()
        if ok and candidate is not None:
            frame = candidate
            break
        time.sleep(0.2)

    capture.release()

    elapsed = time.monotonic() - started_at

    if frame is None:
        print(
            f"FAILED: no frame received after {attempts}/{MAX_FRAMES_PER_URL} "
            f"read attempts in {elapsed:.1f}s."
        )
        print_codec_hint()
        return False

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_path = SNAPSHOT_DIR / f"hikvision_ch{channel}_{timestamp}.jpg"

    if not cv2.imwrite(str(snapshot_path), frame):
        print(f"FAILED: frame received but snapshot could not be saved: {snapshot_path}")
        return False

    if frame_looks_gray(frame):
        print(
            f"OK: frame received and snapshot saved, but the frame looks gray: {snapshot_path}"
        )
        print_codec_hint()
        return True

    print(f"OK: frame received and snapshot saved: {snapshot_path}")
    return True


def main() -> int:
    config = load_config()
    if config is None:
        return 2

    try:
        import cv2
    except ImportError:
        print("ERROR: OpenCV is not installed. Run: pip install -r backend/requirements.txt")
        return 2

    print("SmartGuard AI RTSP diagnostics")
    print(f"NVR: {config.host}:{config.port}")
    print(f"User: {config.user}")
    print("Backend: OpenCV CAP_FFMPEG")

    results = []
    for channel in CHANNELS:
        results.append(diagnose_channel(cv2, config, channel))

    ok_count = sum(1 for result in results if result)
    print(f"\nSummary: {ok_count}/{len(CHANNELS)} channels returned a frame.")
    return 0 if ok_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
