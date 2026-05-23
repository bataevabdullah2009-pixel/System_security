from __future__ import annotations

import json

from app.services import zone_service


def test_point_in_polygon() -> None:
    polygon = [[10, 10], [100, 10], [100, 100], [10, 100]]

    assert zone_service.point_in_polygon([50, 50], polygon) is True
    assert zone_service.point_in_polygon([150, 50], polygon) is False


def test_object_gets_zone_id(monkeypatch, tmp_path) -> None:
    config_path = tmp_path / "zones.json"
    config_path.write_text(
        json.dumps(
            {
                "101": [
                    {
                        "id": "entrance",
                        "name": "Entrance",
                        "polygon": [[10, 10], [100, 10], [100, 100], [10, 100]],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(zone_service, "ZONES_CONFIG_PATH", config_path)

    assert zone_service.get_object_zones("101", [50, 50]) == ["entrance"]
