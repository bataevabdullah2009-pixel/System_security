from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import httpx
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = PROJECT_ROOT / "storage" / "snapshots"
CHANNELS = ("101", "102", "201", "202")
REQUEST_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class HikvisionHttpConfig:
    host: str
    user: str
    password: str
    port: int


def load_config() -> HikvisionHttpConfig | None:
    load_dotenv(PROJECT_ROOT / ".env")

    host = os.getenv("HIKVISION_HOST", "").strip()
    user = os.getenv("HIKVISION_USER", "").strip()
    password = os.getenv("HIKVISION_PASSWORD", "")
    port_raw = os.getenv("HIKVISION_HTTP_PORT", "80").strip()

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
        print(f"ERROR: HIKVISION_HTTP_PORT must be an integer, got: {port_raw!r}")
        return None

    return HikvisionHttpConfig(host=host, user=user, password=password, port=port)


def print_env_example() -> None:
    print(
        "\nAdd these values to .env:\n"
        "HIKVISION_HOST=192.168.0.102\n"
        "HIKVISION_USER=admin\n"
        "HIKVISION_PASSWORD=your_password_here\n"
        "HIKVISION_HTTP_PORT=80\n"
    )


def build_snapshot_url(config: HikvisionHttpConfig, channel: str) -> str:
    return (
        f"http://{config.host}:{config.port}"
        f"/ISAPI/Streaming/channels/{channel}/picture"
    )


def masked_url(config: HikvisionHttpConfig, channel: str) -> str:
    user = quote(config.user, safe="")
    return (
        f"http://{user}:***@{config.host}:{config.port}"
        f"/ISAPI/Streaming/channels/{channel}/picture"
    )


def short_reason(response: httpx.Response) -> str:
    content_type = response.headers.get("content-type", "unknown")
    body = response.text.strip().replace("\r", " ").replace("\n", " ")
    if len(body) > 160:
        body = body[:157] + "..."
    if body:
        return f"{response.reason_phrase}; content-type={content_type}; body={body}"
    return f"{response.reason_phrase}; content-type={content_type}"


def request_snapshot(
    client: httpx.Client,
    url: str,
    config: HikvisionHttpConfig,
) -> tuple[str, httpx.Response | None, str | None]:
    auth_attempts = (
        ("Digest", httpx.DigestAuth(config.user, config.password)),
        ("Basic", httpx.BasicAuth(config.user, config.password)),
    )

    last_response = None
    for auth_name, auth in auth_attempts:
        try:
            response = client.get(url, auth=auth)
        except httpx.HTTPError as exc:
            return auth_name, None, str(exc)

        last_response = response
        if response.status_code == 200:
            return auth_name, response, None

        if response.status_code not in (401, 403):
            return auth_name, response, None

    return "Basic", last_response, None


def save_snapshot(channel: str, image_bytes: bytes) -> Path:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_path = SNAPSHOT_DIR / f"hikvision_isapi_ch{channel}_{timestamp}.jpg"
    snapshot_path.write_bytes(image_bytes)
    return snapshot_path


def diagnose_channel(
    client: httpx.Client,
    config: HikvisionHttpConfig,
    channel: str,
) -> bool:
    url = build_snapshot_url(config, channel)
    print(f"\nChecking channel {channel}")
    print(f"URL: {masked_url(config, channel)}")

    auth_name, response, error = request_snapshot(client, url, config)

    if error is not None:
        print(f"FAILED channel {channel} status=network_error auth={auth_name} reason={error}")
        return False

    if response is None:
        print(f"FAILED channel {channel} status=no_response auth={auth_name}")
        return False

    content_type = response.headers.get("content-type", "").lower()
    if response.status_code == 200 and "image/jpeg" in content_type:
        snapshot_path = save_snapshot(channel, response.content)
        print(f"OK channel {channel} saved to {snapshot_path} auth={auth_name}")
        return True

    print(
        f"FAILED channel {channel} status={response.status_code} "
        f"auth={auth_name} reason={short_reason(response)}"
    )
    return False


def main() -> int:
    config = load_config()
    if config is None:
        return 2

    print("SmartGuard AI Hikvision ISAPI snapshot diagnostics")
    print(f"Device: {config.host}:{config.port}")
    print(f"User: {config.user}")
    print("Auth: Digest first, Basic fallback")

    ok_count = 0
    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        for channel in CHANNELS:
            if diagnose_channel(client, config, channel):
                ok_count += 1

    print(f"\nSummary: {ok_count}/{len(CHANNELS)} snapshot endpoints returned image/jpeg.")
    return 0 if ok_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
