from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

import cv2
import httpx
import numpy as np
from dotenv import load_dotenv


logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
STORAGE_ROOT = PROJECT_ROOT / "storage"
SNAPSHOT_DIR = STORAGE_ROOT / "snapshots"
LATEST_DIR = STORAGE_ROOT / "latest"
DEFAULT_MIN_IMAGE_BYTES = 1024


class HikvisionSnapshotError(RuntimeError):
    pass


@dataclass(frozen=True)
class HikvisionSnapshotConfig:
    host: str
    user: str
    password: str
    port: int


@dataclass(frozen=True)
class SnapshotValidationResult:
    ok: bool
    error: str | None = None


def load_config() -> HikvisionSnapshotConfig:
    load_dotenv(PROJECT_ROOT / ".env")

    host = os.getenv("HIKVISION_HOST", "").strip()
    user = os.getenv("HIKVISION_USER", "").strip()
    password = os.getenv("HIKVISION_PASSWORD", "")
    port_raw = os.getenv("HIKVISION_HTTP_PORT", "80").strip()

    missing = [
        key
        for key, value in (
            ("HIKVISION_HOST", host),
            ("HIKVISION_USER", user),
            ("HIKVISION_PASSWORD", password),
        )
        if not value
    ]
    if missing:
        raise HikvisionSnapshotError(f"Missing required env values: {', '.join(missing)}")

    try:
        port = int(port_raw)
    except ValueError as exc:
        raise HikvisionSnapshotError("HIKVISION_HTTP_PORT must be an integer") from exc

    return HikvisionSnapshotConfig(host=host, user=user, password=password, port=port)


def build_snapshot_url(host: str, port: int | str, channel: int | str) -> str:
    return f"http://{host}:{port}/ISAPI/Streaming/channels/{channel}/picture"


def mask_url(url: str) -> str:
    parts = urlsplit(url)
    if "@" not in parts.netloc:
        return url

    credentials, host = parts.netloc.rsplit("@", 1)
    if ":" in credentials:
        user, _password = credentials.split(":", 1)
        masked_credentials = f"{user}:***"
    else:
        masked_credentials = "***"

    return urlunsplit((parts.scheme, f"{masked_credentials}@{host}", parts.path, parts.query, parts.fragment))


def _snapshot_url_for_config(config: HikvisionSnapshotConfig, channel: int | str) -> str:
    return build_snapshot_url(config.host, config.port, channel)


def _short_response_reason(response: httpx.Response) -> str:
    content_type = response.headers.get("content-type", "unknown")
    body = response.text.strip().replace("\r", " ").replace("\n", " ")
    if len(body) > 160:
        body = body[:157] + "..."
    if body:
        return f"status={response.status_code}; content-type={content_type}; body={body}"
    return f"status={response.status_code}; content-type={content_type}"


def validate_snapshot(
    image_bytes: bytes,
    min_size_bytes: int = DEFAULT_MIN_IMAGE_BYTES,
) -> SnapshotValidationResult:
    if not image_bytes:
        return SnapshotValidationResult(ok=False, error="empty response body")
    if len(image_bytes) < min_size_bytes:
        return SnapshotValidationResult(
            ok=False,
            error=f"image is too small: {len(image_bytes)} bytes",
        )
    if not image_bytes.startswith(b"\xff\xd8"):
        return SnapshotValidationResult(ok=False, error="response is not a JPEG")

    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    decoded = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if decoded is None:
        return SnapshotValidationResult(ok=False, error="OpenCV could not decode JPEG")

    return SnapshotValidationResult(ok=True)


def fetch_snapshot(channel: int | str) -> bytes:
    config = load_config()
    url = _snapshot_url_for_config(config, channel)
    masked = mask_url(
        build_snapshot_url(
            f"{quote(config.user, safe='')}:***@{config.host}",
            config.port,
            channel,
        )
    )

    auth_attempts = (
        ("Digest", httpx.DigestAuth(config.user, config.password)),
        ("Basic", httpx.BasicAuth(config.user, config.password)),
    )

    last_error = "no response"
    with httpx.Client(timeout=10.0) as client:
        for auth_name, auth in auth_attempts:
            try:
                response = client.get(url, auth=auth)
            except httpx.HTTPError as exc:
                last_error = f"{auth_name} network error: {exc}"
                logger.warning("Hikvision snapshot request failed for %s: %s", masked, last_error)
                continue

            content_type = response.headers.get("content-type", "").lower()
            if response.status_code == 200 and "image/jpeg" in content_type:
                validation = validate_snapshot(response.content)
                if not validation.ok:
                    raise HikvisionSnapshotError(
                        f"Invalid snapshot for channel {channel}: {validation.error}"
                    )
                return response.content

            last_error = f"{auth_name} {_short_response_reason(response)}"
            if response.status_code not in (401, 403):
                break

    raise HikvisionSnapshotError(f"Failed to fetch channel {channel}: {last_error}")


def save_snapshot(channel: int | str) -> Path:
    image_bytes = fetch_snapshot(channel)
    return save_snapshot_bytes(channel, image_bytes)


def save_snapshot_bytes(channel: int | str, image_bytes: bytes) -> Path:
    validation = validate_snapshot(image_bytes)
    if not validation.ok:
        raise HikvisionSnapshotError(f"Invalid snapshot for channel {channel}: {validation.error}")

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_path = SNAPSHOT_DIR / f"hikvision_ch{channel}_{timestamp}.jpg"
    snapshot_path.write_bytes(image_bytes)
    return snapshot_path


def save_latest_snapshot(channel: int | str, image_bytes: bytes) -> Path:
    LATEST_DIR.mkdir(parents=True, exist_ok=True)
    latest_path = LATEST_DIR / f"hikvision_ch{channel}_latest.jpg"
    latest_path.write_bytes(image_bytes)
    return latest_path
