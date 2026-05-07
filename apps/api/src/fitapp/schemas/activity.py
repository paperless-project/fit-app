"""Esquemas Pydantic para actividades."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ActivityPatch(BaseModel):
    name: str | None = None
    sport: str | None = None
    notes: str | None = None


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    file_name: str
    name: str | None
    sport: str | None
    notes: str | None
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
    normalized_power: int | None
    calories: int | None
    created_at: datetime


class RecordOut(BaseModel):
    ts: datetime
    lat: float | None = None
    lon: float | None = None
    altitude_m: float | None = None
    distance_m: float | None = None
    speed_mps: float | None = None
    heart_rate: int | None = None
    cadence: int | None = None
    power: int | None = None


class LapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    lap_index: int
    start_time: datetime
    duration_s: int | None = None
    distance_m: float | None = None
    avg_speed_mps: float | None = None
    avg_hr: int | None = None
    ascent_m: float | None = None


class ActivityDetailOut(ActivityOut):
    records: list[RecordOut] = []
    laps: list[LapOut] = []


class ActivityPage(BaseModel):
    items: list[ActivityOut]
    total: int
    page: int
    size: int
    pages: int
