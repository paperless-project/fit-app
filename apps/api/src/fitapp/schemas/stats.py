"""Schemas Pydantic para los endpoints de estadísticas."""
from __future__ import annotations

from pydantic import BaseModel


class StatsSummary(BaseModel):
    total_activities: int
    total_km: float
    total_hours: float
    total_ascent_m: float


class CalendarDay(BaseModel):
    count: int
    km: float


class CalendarResponse(BaseModel):
    year: int
    days: dict[str, CalendarDay]


class TimelineEntry(BaseModel):
    period: str
    count: int
    km: float
    hours: float
    ascent_m: float
