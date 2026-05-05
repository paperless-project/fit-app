"""Esquemas Pydantic para actividades."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    file_name: str
    sport: str | None
    started_at: datetime
    duration_s: int | None
    moving_time_s: int | None
    distance_m: float | None
    ascent_m: float | None
    descent_m: float | None
    avg_speed_mps: float | None
    max_speed_mps: float | None
    avg_hr: int | None
    max_hr: int | None
    avg_cadence: int | None
    avg_power: int | None
    calories: int | None
    created_at: datetime
