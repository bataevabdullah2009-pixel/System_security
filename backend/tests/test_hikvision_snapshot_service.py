import logging

from fastapi.testclient import TestClient

from app.main import app
from app.services import camera_service
from app.services.hikvision_snapshot_service import (
    build_snapshot_url,
    mask_url,
    validate_snapshot,
)


def test_build_snapshot_url() -> None:
    assert (
        build_snapshot_url("192.168.0.102", 80, "101")
        == "http://192.168.0.102:80/ISAPI/Streaming/channels/101/picture"
    )


def test_mask_url_hides_credentials() -> None:
    masked = mask_url(
        "http://admin:secret-password@192.168.0.102:80/ISAPI/Streaming/channels/101/picture"
    )

    assert "secret-password" not in masked
    assert "admin:***@" in masked


def test_validate_snapshot_rejects_invalid_bytes() -> None:
    result = validate_snapshot(b"not-a-jpeg", min_size_bytes=1)

    assert result.ok is False
    assert result.error is not None


def test_masked_url_does_not_log_password(caplog) -> None:
    caplog.set_level(logging.WARNING)
    password = "secret-password"

    logging.getLogger("app.services.hikvision_snapshot_service").warning(
        "URL=%s",
        mask_url(
            f"http://admin:{password}@192.168.0.102:80/ISAPI/Streaming/channels/101/picture"
        ),
    )

    assert password not in caplog.text


def test_hikvision_diagnose_api_route_exists(monkeypatch) -> None:
    def fake_diagnose_all_channels() -> list[dict[str, object]]:
        return [
            {
                "channel": 101,
                "status": "online",
                "source_type": "hikvision_isapi_snapshot",
                "snapshot_path": "storage/snapshots/test.jpg",
                "error": None,
            }
        ]

    monkeypatch.setattr(camera_service, "diagnose_all_channels", fake_diagnose_all_channels)

    client = TestClient(app)
    response = client.get("/api/cameras/hikvision/diagnose")

    assert response.status_code == 200
    assert response.json()[0]["status"] == "online"
