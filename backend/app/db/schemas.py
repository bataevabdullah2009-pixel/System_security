from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EventStatusUpdate(BaseModel):
    status: str = Field(..., examples=["acknowledged"])


class EventRead(BaseModel):
    id: int
    event_type: str
    status: str
    channel: str
    source: str
    title: str
    description: str
    confidence: float | None
    snapshot_path: str | None
    annotated_snapshot_path: str | None
    detections: list[dict[str, object]]
    event_key: str
    created_at: datetime
    updated_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
