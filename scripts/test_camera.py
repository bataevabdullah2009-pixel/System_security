from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT_DIR = PROJECT_ROOT / "storage" / "events"


def load_project_env() -> None:
    load_dotenv(PROJECT_ROOT / ".env")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Test one RTSP camera and save a snapshot when a frame is received."
    )
    parser.add_argument(
        "--url",
        default=None,
        help="RTSP URL. Defaults to RTSP_URL from .env.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Maximum read attempts before exiting. Defaults to CAMERA_TEST_MAX_FRAMES or 30.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=None,
        help="Delay between frame read attempts. Defaults to CAMERA_TEST_READ_DELAY_SECONDS or 0.2.",
    )
    parser.add_argument(
        "--snapshot-dir",
        default=str(DEFAULT_SNAPSHOT_DIR),
        help="Directory for the saved snapshot.",
    )
    return parser


def print_rtsp_help() -> None:
    print(
        "\nRTSP troubleshooting:\n"
        "- Check camera IP, username, password, and RTSP path.\n"
        "- For Hikvision/HiWatch use examples like:\n"
        "  rtsp://user:password@192.168.0.102:554/Streaming/Channels/101\n"
        "  rtsp://user:password@192.168.0.102:554/Streaming/Channels/102\n"
        "- If VLC/OpenCV shows HEVC errors such as 'Waiting for VPS/SPS/PPS' or\n"
        "  'Failed decoding SPS', switch Main Stream and Sub Stream to H.264.\n"
        "- Disable H.265, H.265+, Smart Codec, or similar vendor codec features.\n"
    )


def main() -> int:
    load_project_env()
    args = build_parser().parse_args()

    rtsp_url = args.url or os.getenv("RTSP_URL")
    if not rtsp_url:
        print("ERROR: RTSP_URL is not set. Add it to .env or pass --url.")
        print_rtsp_help()
        return 2

    max_frames = args.max_frames or int(os.getenv("CAMERA_TEST_MAX_FRAMES", "30"))
    delay = args.delay if args.delay is not None else float(
        os.getenv("CAMERA_TEST_READ_DELAY_SECONDS", "0.2")
    )
    snapshot_dir = Path(args.snapshot_dir)

    try:
        import cv2
    except ImportError:
        print("ERROR: OpenCV is not installed. Run: pip install -r backend/requirements.txt")
        return 2

    print("Opening RTSP stream with OpenCV CAP_FFMPEG...")
    print(f"URL: {rtsp_url}")

    capture = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
    if hasattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC"):
        capture.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
    if hasattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC"):
        capture.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)

    if not capture.isOpened():
        print("ERROR: OpenCV could not open the RTSP stream.")
        print_rtsp_help()
        capture.release()
        return 1

    frame = None
    last_error = "No frame read yet."
    for attempt in range(1, max_frames + 1):
        ok, candidate = capture.read()
        if ok and candidate is not None:
            frame = candidate
            print(f"Frame received on attempt {attempt}/{max_frames}.")
            break

        last_error = f"Attempt {attempt}/{max_frames}: frame was not received."
        print(last_error)
        time.sleep(delay)

    capture.release()

    if frame is None:
        print("\nERROR: No valid frame was received; snapshot was not saved.")
        print(last_error)
        print_rtsp_help()
        return 1

    snapshot_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_path = snapshot_dir / f"rtsp_snapshot_{timestamp}.jpg"
    saved = cv2.imwrite(str(snapshot_path), frame)

    if not saved:
        print(f"ERROR: Frame was received, but snapshot could not be saved: {snapshot_path}")
        return 1

    print(f"Snapshot saved: {snapshot_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
