from __future__ import annotations

import json
from pathlib import Path

from app.db.database import PROJECT_ROOT

STORAGE_ROOT = PROJECT_ROOT / "storage"
ZONES_CONFIG_PATH = STORAGE_ROOT / "config" / "zones.json"


def load_zones(channel: int | str) -> list[dict[str, object]]:
    if not ZONES_CONFIG_PATH.exists():
        return []

    data = json.loads(ZONES_CONFIG_PATH.read_text(encoding="utf-8"))
    zones = data.get(str(channel), [])
    if not isinstance(zones, list):
        return []
    return [zone for zone in zones if isinstance(zone, dict)]


def point_in_polygon(
    point: list[int] | tuple[int, int], polygon: list[list[int]]
) -> bool:
    x, y = point
    inside = False
    if len(polygon) < 3:
        return False

    previous_x, previous_y = polygon[-1]
    for current_x, current_y in polygon:
        crosses = (current_y > y) != (previous_y > y)
        if crosses:
            slope_x = (previous_x - current_x) * (y - current_y) / (
                (previous_y - current_y) or 1e-9
            ) + current_x
            if x < slope_x:
                inside = not inside
        previous_x, previous_y = current_x, current_y
    return inside


def get_object_zones(
    channel: int | str, center: list[int] | tuple[int, int]
) -> list[str]:
    zone_ids: list[str] = []
    for zone in load_zones(channel):
        polygon = zone.get("polygon", [])
        zone_id = zone.get("id")
        if (
            isinstance(zone_id, str)
            and isinstance(polygon, list)
            and point_in_polygon(center, polygon)
        ):
            zone_ids.append(zone_id)
    return zone_ids


def get_zones_by_id(channel: int | str) -> dict[str, dict[str, object]]:
    zones_by_id: dict[str, dict[str, object]] = {}
    for zone in load_zones(channel):
        zone_id = zone.get("id")
        if isinstance(zone_id, str):
            zones_by_id[zone_id] = zone
    return zones_by_id


def get_zone_name(channel: int | str, zone_id: str) -> str:
    zone = get_zones_by_id(channel).get(zone_id, {})
    return str(zone.get("name") or zone_id)


def get_zone_type(channel: int | str, zone_id: str) -> str | None:
    zone_type = get_zones_by_id(channel).get(zone_id, {}).get("type")
    return str(zone_type) if zone_type is not None else None


def ensure_default_zones_config() -> Path:
    if ZONES_CONFIG_PATH.exists():
        return ZONES_CONFIG_PATH

    ZONES_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    ZONES_CONFIG_PATH.write_text(
        json.dumps(
            {
                "101": [
                    {
                        "id": "entrance",
                        "name": "Entrance",
                        "type": "entry",
                        "polygon": [[10, 10], [300, 10], [300, 300], [10, 300]],
                    },
                    {
                        "id": "cashier",
                        "name": "Cashier",
                        "type": "cashier",
                        "polygon": [[400, 100], [700, 100], [700, 400], [400, 400]],
                    },
                    {
                        "id": "restricted",
                        "name": "Restricted zone",
                        "type": "restricted",
                        "polygon": [[800, 100], [1100, 100], [1100, 500], [800, 500]],
                    },
                ]
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return ZONES_CONFIG_PATH
